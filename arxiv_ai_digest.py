import os
import json
import arxiv
import re
import logging
import time
import random
from google import genai
from google.genai import types
from datetime import date, timedelta

# --- 0. 依赖检查 ---
try:
    import json5 
except ImportError:
    import json as json5
    logger.warning("未找到 json5 库，正在使用标准 json 库。")

# --- 1. 配置 Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. 核心配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

# 3个超级核心配置 (V19)
YOUR_DOMAINS_OF_INTEREST = {
    "phd_foundations": {
        "name_zh": "AI 理论与统计基础",
        "name_en": "AI Theory & Statistical Foundations",
        "categories": ['stat.ML', 'cs.LG', 'stat.ME', 'math.ST', 'cs.AI', 'cs.CY', 'math.OC', 'stat.TH', 'cs.CV'],
        "search_query": (
            '("statistical learning theory" OR "nonparametric regression" OR "model selection" OR "high-dimensional inference" OR "uncertainty quantification") OR '
            '("causal inference" OR "fairness" OR "explainable AI" OR "interpretability" OR "treatment effect") OR '
            '("generalization bound" OR "optimization landscape" OR "convergence analysis" OR "deep neural network theory") OR '
            '("high-dimensional statistics" OR "nonparametric estimation" OR "minimax rate" OR "statistical guarantees") OR '
            '("representation learning" OR "metric learning" OR "contrastive learning" OR "self-supervised learning" OR "information bottleneck")'
        ),
        "ai_preference_prompt": """
        我是一名数理统计博士生，专注于将严谨的数学逻辑应用于现代 AI 系统。
        我寻求的论文必须具备**强大的理论基础**（如统计保证、优化收敛性、因果逻辑）和**清晰的数学推导**。
        """
    },
    "phd_methods": {
        "name_zh": "前沿 AI 模型与应用",
        "name_en": "Frontier AI Models & Applications",
        "categories": ['cs.LG', 'cs.AI', 'cs.SY', 'cs.CL', 'stat.AP', 'cs.CV', 'eess.IV', 'cs.AR'],
        "search_query": (
            '("Offline Reinforcement Learning" OR "Safe RL" OR "exploration" OR "Multi-Agent" OR "Model-Based RL") OR '
            '("Large Language Model" OR "prompt engineering" OR "RAG system" OR "in-context learning" OR "LLM for data analysis") OR '
            '("Vision Transformer" OR "Diffusion Model" OR "Graph Neural Network" OR "multimodal learning") OR '
            '("efficient AI" OR "model compression" OR "knowledge distillation" OR "on-device inference" OR "low-resource ML")'
        ),
        "ai_preference_prompt": """
        我是一名数理统计博士生，专注于 AI 的前沿算法和架构。
        我寻求的论文必须**逻辑清晰**，并能**解决实际应用瓶颈**（如数据效率、模型压缩、LLM 应用）。
        我**不**喜欢纯粹的工程堆砌，方法必须具有**理论创新性**。
        """
    },
    "quant_crypto": {
        "name_zh": "量化金融 (Crypto)",
        "name_en": "Quantitative Finance (Crypto)",
        "categories": ['q-fin.ST', 'q-fin.CP', 'q-fin.PM', 'cs.CE', 'stat.ML'],
        "search_query": '("cryptocurrency" OR "digital asset" OR "factor investing" OR "algorithmic trading" OR "market microstructure")',
        "ai_preference_prompt": """
        我正在帮助同学**构造加密货币市场的量化因子**。
        我需要对**这个具体任务**（因子构造、回测、策略设计）**最有帮助**的论文。
        """
    }
}

# --------------------------------------------------------------------------
# 抓取函数 (V20 - 抗限流增强)
# --------------------------------------------------------------------------
def fetch_papers_for_domain(domain_name, categories, extra_query, target_date):
    logger.info(f"--- 正在为领域 {domain_name} (日期 {target_date}) 抓取论文 ---")
    
    date_str = target_date.strftime("%Y%m%d")
    date_filter = f"submittedDate:[{date_str}0000 TO {date_str}2359]"
    
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    full_query = f"({category_query}) AND ({extra_query}) AND {date_filter}"
    
    search = arxiv.Search(
        query=full_query,
        max_results=120, # 维持 120 篇
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers_list = []
    try:
        # --- 关键修复：配置 Client 增加延迟和重试 ---
        client = arxiv.Client(
            page_size=100,
            delay_seconds=8.0,  # 关键：每次 API 请求等待 8 秒
            num_retries=5       # 增加重试次数
        )
        # ----------------------------------------------
        
        for result in client.results(search):
            papers_list.append({
                'id': result.entry_id,
                'title': result.title,
                'summary': result.summary.replace("\n", " "),
                'authors': ", ".join([a.name for a in result.authors]),
                'url': result.entry_id,
                'pdf_url': result.pdf_url
            })
        logger.info(f"为 {domain_name} 抓取到 {len(papers_list)} 篇论文。")
        return papers_list
    except Exception as e:
        logger.error(f"抓取 arXiv 失败: {e}")
        return []

# --------------------------------------------------------------------------
# (V19) AI 分析函数 - 带智能重试机制 (Top 10-15)
# --------------------------------------------------------------------------
def get_ai_editor_pick(papers, domain_name, user_preference_prompt):
    if not papers:
        logger.info("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        logger.error("未找到 GEMINI_API_KEY。")
        return None

    client = genai.Client()
    
    prompt_papers = "\n".join(
        [f"--- 论文 {i+1} ---\nID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
         for i, p in enumerate(papers)]
    )

    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手。
    我的个人偏好："{user_preference_prompt}"
    
    下面是 {len(papers)} 篇论文。
    你的任务是“批量评分和筛选”：
    
    1. **评分：** 根据以下 4 个标准（1-5分）为每一篇论文打分：
        - Novelty (创新性): 提出新方法或新视角 (1-5分)
        - Rigor (理论严谨性): 数学/统计推导是否严谨 (1-5分)
        - Impact (实践影响力): 是否可落地、能提高效果 (1-5分)
        - Clarity (清晰度): 是否深入浅出、逻辑脉络清晰 (1-5分)
    2. **优选 Top 15**：请根据我的偏好，挑选出**总分最高的 10 到 15 篇**论文。
    3. **评分**：为每篇选中的论文打分 (Novelty, Rigor, Impact, Clarity)。
    
    请返回一个 JSON **列表**。如果实在没有值得读的，返回 `null`。
    
    JSON 格式示例:
    [
      {{
        "id": "论文ID",
        "scores": {{ "Novelty": 5, "Rigor": 4, "Impact": 5, "Clarity": 4 }},
        "reason_zh": "推荐理由..."
      }}
    ]
    """
    
    full_prompt = f"{system_prompt}\n\n--- 论文列表 ---\n{prompt_papers}"

    # --- (V19) 增强的重试逻辑 ---
    max_retries = 5
    base_delay = 10

    for attempt in range(max_retries):
        try:
            logger.info(f"🚀 请求 AI 分析 (第 {attempt + 1}/{max_retries} 次尝试)...")
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            
            cleaned = response.text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```\w*\n", "", cleaned)
                cleaned = re.sub(r"\n```$", "", cleaned)
            cleaned = cleaned.strip()

            if cleaned.lower() == 'null':
                logger.info("AI 明确表示没有推荐 (NULL)。")
                return None

            match = re.search(r'(\[.*\])', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1)
            
            # 使用 json5 宽容解析
            ai_picks_list = json5.loads(cleaned)
            
            logger.info(f"✅ AI 成功选出 {len(ai_picks_list)} 篇今日最佳。")
            return ai_picks_list

        except Exception as e:
            logger.warning(f"⚠️ 第 {attempt + 1} 次尝试失败: {e}")
            if attempt < max_retries - 1:
                # 指数退避
                wait_time = base_delay * (2 ** attempt) + random.uniform(0, 3)
                logger.info(f"⏳ 等待 {wait_time:.1f} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error("❌ 所有重试均失败。")
                return None

# --------------------------------------------------------------------------
# 写入 JSON
# --------------------------------------------------------------------------
def write_to_json(data_to_save, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            if data_to_save:
                logger.info(f"成功将 {len(data_to_save)} 篇“精选”写入 {file_path}")
            else:
                logger.info(f"标记 {file_path} 为“无精选”。")
    except Exception as e:
        logger.error(f"写入 JSON 文件失败: {e}")

# --------------------------------------------------------------------------
# 主函数
# --------------------------------------------------------------------------
if __name__ == "__main__":
    target_date = date.today() - timedelta(days=1)
    
    logger.info(f"--- 脚本开始运行 (V20 抗限流版)，目标日期: {target_date.isoformat()} ---")

    for domain_key, config in YOUR_DOMAINS_OF_INTEREST.items():
        logger.info(f"\n--- 处理领域: {config['name_en']} ---")
        
        papers = fetch_papers_for_domain(
            domain_name=config["name_en"],
            categories=config["categories"], 
            extra_query=config["search_query"], 
            target_date=target_date
        )
        
        picks_list_json = get_ai_editor_pick(papers, config["name_en"], config["ai_preference_prompt"])

        final_data_list = []
        if picks_list_json:
            for pick_item in picks_list_json:
                full_paper = next((p for p in papers if p['id'] == pick_item.get('id')), None)
                if full_paper:
                    final_data_list.append({**full_paper, **pick_item})
        
        if not final_data_list:
             final_data_list = None 

        output_path = os.path.join(ARCHIVE_DIR, domain_key, f"{target_date.isoformat()}.json")
        write_to_json(final_data_list, output_path)

    logger.info(f"\n--- 所有领域处理完毕: {target_date.isoformat()} ---")

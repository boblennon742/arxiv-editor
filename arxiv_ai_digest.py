import os
import json
import json5  # <--- 1. 新增导入
import arxiv
import re
import logging
import time
import random
from google import genai
from datetime import date, timedelta

# --- 1. 配置 Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. 核心配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

# --------------------------------------------------------------------------
# (V17.1) 3 个超级核心
# --------------------------------------------------------------------------
YOUR_DOMAINS_OF_INTEREST = {
    # 核心 1: AI 理论与统计基础
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
    
    # 核心 2: 前沿 AI 模型与应用
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
    # 核心 3: 量化金融 (Crypto)
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
# (V17.3) 抓取函数
# --------------------------------------------------------------------------
def fetch_papers_for_domain(domain_name, categories, extra_query, target_date):
    logger.info(f"--- 正在为领域 {domain_name} (日期 {target_date}) 抓取论文 ---")
    
    date_str = target_date.strftime("%Y%m%d")
    date_filter = f"submittedDate:[{date_str}0000 TO {date_str}2359]"
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    full_query = f"({category_query}) AND ({extra_query}) AND {date_filter}"
    
    search = arxiv.Search(
        query=full_query,
        max_results=200,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    papers_list = []
    try:
        client = arxiv.Client()
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
# (V17) AI 分析函数 (评分引擎) —— <修改点：使用 json5>
# --------------------------------------------------------------------------
def get_ai_editor_pick(papers, domain_name, user_preference_prompt, max_retries=5):
    if not papers:
        logger.info("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        logger.error("未找到 GEMINI_API_KEY。")
        return None

    prompt_papers = "\n".join(
        [f"--- 论文 {i+1} ---\nID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
         for i, p in enumerate(papers)]
    )
    system_prompt = f"""
你是我（统计学博士生）的私人研究助手，“AI 总编辑”。
今天任务是分析 "{domain_name}" 领域。
我的偏好是：{user_preference_prompt}

请严格按以下 JSON 格式返回（只返回 JSON，不要任何解释）：
如果今天没有好论文 → 直接返回 null
否则返回最多 10 篇最符合我偏好的论文（如果确实有10篇都极好就全给我！）：

[
  {{"id": "2411.12345", "scores": {{"Novelty":5,"Rigor":5,"Impact":4,"Clarity":5}}, "reason_zh": "详细中文理由..."}}
] # 最多10篇，宁多勿少！

现在开始分析：
"""
    full_prompt = system_prompt + "\n" + prompt_papers

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"正在请求 Gemini（第 {attempt} 次）→ {domain_name}")
            client = genai.Client()
            response = client.models.generate_content(
                model='gemini-1.5-flash',  # 或 gemini-1.5-pro
                contents=full_prompt
            )
            text = response.text.strip()

            # 去除代码块
            text = re.sub(r'^```json\s*|```$', '', text, flags=re.MULTILINE).strip()

            # 处理 "null" 字符串
            if text.lower() == "null":
                logger.info("AI 认为今天无优质论文")
                return None

            # 先尝试 json5（最宽容）
            try:
                result = json5.loads(text)
            except:
                result = json.loads(text)  # 兜底

            if isinstance(result, list):
                logger.info(f"成功挑选 {len(result)} 篇论文")
                return result
            else:
                raise ValueError("返回的不是列表")

        except Exception as e:
            logger.warning(f"第 {attempt} 次失败: {e}")
            if attempt == max_retries:
                logger.error("已达最大重试次数，放弃本次分析")
                return None
            sleep_time = (2 ** attempt) + random.random()
            logger.info(f"{sleep_time:.1f}s 后重试...")
            time.sleep(sleep_time)

    )
# --------------------------------------------------------------------------
# 写入 JSON (保持标准 json dump，因为输出文件需要标准格式兼容其他程序)
# --------------------------------------------------------------------------
def write_to_json(data_to_save, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # 这里依然使用标准 json 库，确保生成的文件是严格的 JSON 标准
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
    
    logger.info(f"--- 脚本开始运行 (V17.5 json5增强版)，目标日期: {target_date.isoformat()} ---")
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

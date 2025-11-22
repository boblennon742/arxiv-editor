import os
import json
import json5  # 确保已安装 pip install json5
import arxiv
import re
import logging
from google import genai
from google.genai import types # 引入 types 以支持 JSON 模式设置
from datetime import date, timedelta

# --- 1. 配置 Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. 核心配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

# 配置抓取和推荐数量
FETCH_LIMIT = 200  # <--- 修改点：抓取数量改为 200
TOP_N_PICKS = 10   # <--- 修改点：推荐数量改为 10

# --------------------------------------------------------------------------
# (V17.1) 3 个超级核心
# --------------------------------------------------------------------------
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
        max_results=FETCH_LIMIT, # <--- 修改点：使用配置的 200
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
# (V18) AI 分析函数 - 强制 JSON 模式 + 10篇 + json5 解析
# --------------------------------------------------------------------------
def get_ai_editor_pick(papers, domain_name, user_preference_prompt):
    if not papers:
        logger.info("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        logger.error("未找到 GEMINI_API_KEY。")
        return None
    
    logger.info(f"正在请求 AI 总编辑为 {domain_name} 领域从 {len(papers)} 篇中挑选 {TOP_N_PICKS} 篇...")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 构建 Prompt
    prompt_papers = "\n".join(
        [f"--- 论文 {i+1} ---\nID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
         for i, p in enumerate(papers)]
    )
    
    # <--- 修改点：Prompt 中明确 10 篇，并且要求空列表返回
    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手，一个“AI 总编辑”。
    我今天的任务是分析 "{domain_name}" 领域。
    我的个人偏好/任务是：
    "{user_preference_prompt}"
    
    下面是为该领域抓取的 {len(papers)} 篇论文。
    你的任务是“批量评分和筛选”：
    1. **评分：** 根据以下 4 个标准（1-5分）为每一篇论文打分：
        - Novelty (创新性): 提出新方法或新视角 (1-5分)
        - Rigor (理论严谨性): 数学/统计推导是否严谨 (1-5分)
        - Impact (实践影响力): 是否可落地、能提高效果 (1-5分)
        - Clarity (清晰度): 是否深入浅出、逻辑脉络清晰 (1-5分)
    2. **排序：** 根据我的个人偏好，结合上述 4 个维度的分数，计算一个**总分**。
    3. **筛选：** 挑选出**总分最高的 {TOP_N_PICKS} 篇（最多 {TOP_N_PICKS} 篇）**论文。
    4. **返回：** - 如果找到了值得推荐的论文，请返回一个 JSON 对象列表。
       - 如果没有任何一篇论文值得推荐，请返回一个空列表 `[]`。
       - **绝对不要**返回 `null` 或其他文本，必须是 JSON 列表。
    
    JSON 列表格式示例：
    [
      {{
        "id": "论文ID",
        "scores": {{ "Novelty": 5, "Rigor": 4, "Impact": 5, "Clarity": 4 }},
        "reason_zh": "中文推荐理由"
      }}
    ]
    """
    
    full_prompt = f"{system_prompt}\n\n--- 论文列表开始 ---\n{prompt_papers}\n--- 论文列表结束 ---"
    
    try:
        # <--- 修改点：启用 response_mime_type 为 application/json，强制 AI 输出 JSON
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json" 
            )
        )
        
        cleaned = response.text.strip()
        
        # 调试日志：查看 AI 到底返回了什么
        # logger.info(f"AI Raw Response prefix: {cleaned[:100]}")

        # 解析逻辑
        ai_picks_list = []
        
        # 1. 优先尝试直接解析（因为我们启用了 application/json 模式）
        try:
            ai_picks_list = json5.loads(cleaned)
        except Exception:
            # 2. 如果直接解析失败，尝试提取 []
            match = re.search(r'(\[.*?\])', cleaned, re.DOTALL)
            if match:
                try:
                    ai_picks_list = json5.loads(match.group(1))
                except Exception as e:
                    logger.error(f"提取后的 JSON 解析依然失败: {e}")
                    return None
            else:
                # 3. 检查是否是空列表的变体或 null
                if "[]" in cleaned:
                    return []
                if "null" in cleaned.lower():
                    logger.info("AI 返回了 null，表示无推荐。")
                    return None
                
                logger.error(f"无法从 AI 输出中提取 JSON 列表。原始内容前100字符: {cleaned[:100]}")
                return None

        if not isinstance(ai_picks_list, list):
            logger.error(f"AI 返回的不是列表，而是: {type(ai_picks_list)}")
            return None

        logger.info(f"AI 编辑已选出 {len(ai_picks_list)} 篇今日最佳。")
        return ai_picks_list

    except Exception as e:
        logger.error(f"AI 总编辑分析失败: {e}")
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
    
    logger.info(f"--- 脚本开始运行 (V18 稳定增强版)，目标日期: {target_date.isoformat()} ---")
    logger.info(f"--- 配置: 抓取上限 {FETCH_LIMIT} 篇，推荐上限 {TOP_N_PICKS} 篇 ---")

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
            # 确保 picks_list_json 是列表
            for pick_item in picks_list_json:
                if not isinstance(pick_item, dict): continue
                # 匹配原始论文信息
                full_paper = next((p for p in papers if p['id'] == pick_item.get('id')), None)
                if full_paper:
                    final_data_list.append({**full_paper, **pick_item})
        
        if not final_data_list:
             final_data_list = None
             
        output_path = os.path.join(ARCHIVE_DIR, domain_key, f"{target_date.isoformat()}.json")
        write_to_json(final_data_list, output_path)
        
    logger.info(f"\n--- 所有领域处理完毕: {target_date.isoformat()} ---")

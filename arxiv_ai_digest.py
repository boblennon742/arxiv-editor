import os
import json
import arxiv
# import argparse # <-- 已移除
from google import genai
from datetime import date, timedelta

# --- 1. 配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

# --------------------------------------------------------------------------
# 你的“私人定制”十核 AI 编辑 (V12 - 最终版)
# --------------------------------------------------------------------------
YOUR_DOMAINS_OF_INTEREST = {
    # 核心 1: 统计机器学习基础
    "stat_ml_foundations": {
        "name_zh": "统计/ML基础理论",
        "name_en": "Statistical ML Foundations",
        "categories": ['stat.ML', 'cs.LG', 'stat.ME', 'math.ST', 'cs.AI'],
        "search_query": '("statistical learning theory" OR "nonparametric regression" OR "model selection" OR "high-dimensional inference" OR "uncertainty quantification")',
        "ai_preference_prompt": """
        我是一名致力于将统计学严谨性应用于现代机器学习的博士生。
        请从列表中，为我挑选 1 篇**最具强统计理论基础**，能为现代机器学习算法提供**可靠性、可解释性或置信区间**的论文。我尤其关注具有清晰数学证明和理论界限的工作。
        """
    },
    # 核心 2: 因果推断与可解释性
    "causal_theory": {
        "name_zh": "因果推断/可解释性",
        "name_en": "Causal Inference & XAI",
        "categories": ['stat.ML', 'cs.LG', 'cs.AI', 'cs.CY'],
        "search_query": '("causal inference" OR "fairness" OR "explainable AI" OR "interpretability" OR "treatment effect")',
        "ai_preference_prompt": """
        我的研究兴趣是因果推断及其与深度学习的结合。
        请从列表中，为我挑选 1 篇关于**因果推断在复杂 AI 模型中的应用**（如反事实分析、公平性、因果表示学习）的**新方法论文**。
        """
    },
    # 核心 3: 深度模型理论与优化
    "deep_model_theory": {
        "name_zh": "深度模型理论与优化",
        "name_en": "Deep Model Theory & Optimization",
        "categories": ['cs.LG', 'math.OC', 'stat.ML'],
        "search_query": '("generalization bound" OR "optimization landscape" OR "convergence analysis" OR "deep neural network theory")',
        "ai_preference_prompt": """
        我专注于深度学习模型的理论分析。
        请从列表中，为我挑选 1 篇专注于**深度学习模型收敛性、泛化能力、或训练效率**的数学/理论分析论文。我需要对算法稳定性或界限有深入理解。
        """
    },
    # 核心 4: 高级强化学习
    "advanced_rl": {
        "name_zh": "高级强化学习",
        "name_en": "Advanced Reinforcement Learning",
        "categories": ['cs.LG', 'cs.AI', 'cs.SY'],
        "search_query": '("Offline Reinforcement Learning" OR "Safe RL" OR "exploration" OR "Multi-Agent" OR "Model-Based RL")',
        "ai_preference_prompt": """
        我关注强化学习的前沿算法。
        请从列表中，为我挑选 1 篇旨在解决 **RL 实际应用瓶颈**（如数据效率低、安全问题、离线数据利用）的**创新算法论文**。
        """
    },
    # 核心 5: 大模型与数据科学
    "llm_ds": {
        "name_zh": "大模型与数据科学",
        "name_en": "LLM & Data Science",
        "categories": ['cs.LG', 'cs.CL', 'cs.AI', 'stat.AP'],
        "search_query": '("Large Language Model" OR "prompt engineering" OR "RAG system" OR "in-context learning" OR "LLM for data analysis")',
        "ai_preference_prompt": """
        我研究如何利用大模型提升数据科学流程。
        请从列表中，为我挑选 1 篇关于 **LLM 在数据科学任务中**（如分析自动化、数据生成、复杂推理）的**创新应用、评测或优化方法**的论文。
        """
    },
    # 核心 6: 前沿架构与应用
    "dl_architecture": {
        "name_zh": "前沿架构与应用",
        "name_en": "DL Architectures & Applications",
        "categories": ['cs.CV', 'cs.LG', 'eess.IV'],
        "search_query": '("Vision Transformer" OR "Diffusion Model" OR "Graph Neural Network" OR "multimodal learning" OR "representation learning")',
        "ai_preference_prompt": """
        我对新型模型架构的原理和应用非常感兴趣。
        请从列表中，为我挑选 1 篇关于**新型或跨领域模型架构**（如 GNN、Diffusion 模型）的**结构创新**或在特定任务上的**突破性应用**论文。
        """
    },
    # 应用 7: 量化金融 (Crypto)
    "quant_crypto": {
        "name_zh": "量化金融 (Crypto)",
        "name_en": "Quantitative Finance (Crypto)",
        "categories": ['q-fin.ST', 'q-fin.CP', 'q-fin.PM', 'cs.CE', 'stat.ML'],
        "search_query": '("cryptocurrency" OR "digital asset" OR "factor investing" OR "algorithmic trading" OR "market microstructure")',
        "ai_preference_prompt": """
        我正在帮助同学**构造加密货币市场的量化因子**。
        请从列表中，为我挑选 1 篇对**构建加密货币市场量化因子**（包括数据处理、回测或策略设计）**最有帮助**的论文。我需要直接可应用于实践的见解。
        """
    },
    # 新增 8: 高维统计与泛化
    "high_dim_stats": {
        "name_zh": "高维统计与泛化",
        "name_en": "High-Dimensional Stats & Guarantees",
        "categories": ['stat.TH', 'stat.ML', 'cs.LG', 'math.ST'],
        "search_query": '("high-dimensional statistics" OR "nonparametric estimation" OR "minimax rate" OR "statistical guarantees")',
        "ai_preference_prompt": """
        我专注于高维设置下的统计推断。
        请从列表中，为我挑选 1 篇针对**高维数据**，给出**严谨统计界限、最优估计量或泛化性能保证**的论文。我要求论文理论深度高，并且能应用于现代 ML 模型。
        """
    },
    # 新增 9: 表示学习与度量
    "representation_learning": {
        "name_zh": "表示学习与度量",
        "name_en": "Representation & Metric Learning",
        "categories": ['cs.LG', 'cs.CV', 'stat.ML'],
        "search_query": '("representation learning" OR "metric learning" OR "contrastive learning" OR "self-supervised learning" OR "information bottleneck")',
        "ai_preference_prompt": """
        我关注如何构建具有统计意义的高质量特征。
        请从列表中，为我挑选 1 篇专注于**构建更具统计意义或可分离性的特征表示**的论文，要求理论能明确解释效果提升的原因，而不是纯粹的工程技巧。
        """
    },
    # 新增 10: 高效/边缘计算 AI
    "efficient_ai": {
        "name_zh": "高效/边缘计算 AI",
        "name_en": "Efficient & Edge AI",
        "categories": ['cs.LG', 'cs.CV', 'cs.AR'],
        "search_query": '("efficient AI" OR "model compression" OR "knowledge distillation" OR "on-device inference" OR "low-resource ML")',
        "ai_preference_prompt": """
        我对 AI 模型的实用化和效率提升感兴趣。
        请从列表中，为我挑选 1 篇旨在解决**模型部署和效率问题**（如模型剪枝、量化、低功耗计算）的工程或理论论文。我需要方法能实际落地并显著提高效率。
        """
    }
}

# --------------------------------------------------------------------------
# 抓取函数
# (V12) 关键修复：修改 fetch_papers_for_domain 函数签名，传入 domain_name
def fetch_papers_for_domain(domain_name, categories, extra_query, target_date):
    # (V12) 关键修复：使用更安全的 domain_name 打印
    print(f"--- 正在为领域 {domain_name} (日期 {target_date}) 抓取论文 ---")
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    full_query = f"({category_query}) AND ({extra_query})"

    search = arxiv.Search(
        query=full_query,
        max_results=75,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers_list = []
    try:
        client = arxiv.Client()
        for result in client.results(search):
            paper_date = result.published.date()
            if paper_date < target_date:
                break
            if paper_date == target_date:
                papers_list.append({
                    'id': result.entry_id,
                    'title': result.title,
                    'summary': result.summary.replace("\n", " "),
                    'authors': ", ".join([a.name for a in result.authors]),
                    'url': result.entry_id,
                    'pdf_url': result.pdf_url
                })
        # (V12) 关键修复：使用更安全的 domain_name 打印（这就是之前报错的第158行）
        print(f"为 {domain_name} 抓取到 {len(papers_list)} 篇论文。")
        return papers_list
    except Exception as e:
        print(f"抓取 arXiv 失败: {e}")
        return []

# --------------------------------------------------------------------------
# AI 分析函数
def get_ai_editor_pick(papers, domain_name, user_preference_prompt):
    if not papers:
        print("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        print("未找到 GEMINI_API_KEY。")
        return None

    print(f"正在请求 AI 总编辑为 {domain_name} 领域挑选 1 篇...")
    client = genai.Client()

    prompt_papers = "\n".join(
        [f"--- 论文 {i+1} ---\nID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
         for i, p in enumerate(papers)]
    )

    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手，一个“AI 总编辑”。
    我今天的任务是分析 "{domain_name}" 领域。

    我的个人偏好/任务是：
    "{user_preference_prompt}"
    下面是为该领域抓取的 {len(papers)} 篇论文。
    你的任务是“精中选精”：
    1. 严格根据我的个人偏好/任务，从这些论文中挑选出 **1 篇（最多 1 篇）** 最值得我阅读的论文。
    2. 如果**没有一篇**论文足够好或符合我的需求，请**必须**返回 `null`。
    3. 如果你找到了 1 篇，请以严格的 JSON 格式返回，不要有任何其他文字。
    JSON 格式如下：
    {{
      "id": "被选中论文的 ID",
      "reason_zh": "（中文）详细说明为什么这篇论文**完全符合**我的偏好/任务。",
      "reason_en": "(English) A detailed justification of why this paper **perfectly fits** my preference/task."
    }}
    如果返回 `null`，就只返回 `null` 这个词。
    """

    full_prompt = f"{system_prompt}\n\n--- 论文列表开始 ---\n{prompt_papers}\n--- 论文列表结束 ---"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        cleaned = response.text.strip().lstrip("```json").rstrip("```")

        if cleaned.lower() == 'null':
            print("AI 编辑认为今天没有值得推荐的。")
            return None

        ai_pick = json.loads(cleaned)
        print("AI 编辑已选出今日最佳。")
        return ai_pick
    except Exception as e:
        print(f"AI 总编辑分析失败: {e}")
        return None

# --------------------------------------------------------------------------
# 写入 JSON
def write_to_json(data_to_save, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            if data_to_save:
                print(f"成功将“精选”写入 {file_path}")
            else:
                print(f"标记 {file_path} 为“无精选”。")
    except Exception as e:
        print(f"写入 JSON 文件失败: {e}")

# --------------------------------------------------------------------------
# 主函数
if __name__ == "__main__":
    # (V12) 关键修改：移除 argparse，恢复硬编码日期
    target_date = date.today() - timedelta(days=1)
    
    print(f"--- 脚本开始运行，目标日期: {target_date.isoformat()} ---")

    for domain_key, config in YOUR_DOMAINS_OF_INTEREST.items():
        print(f"\n--- 处理领域: {config['name_en']} ---")
        
        # (V12) 关键修复：传入 domain_name 以修复 print 错误
        papers = fetch_papers_for_domain(
            domain_name=config["name_en"],
            categories=config["categories"], 
            extra_query=config["search_query"], 
            target_date=target_date
        )
        
        pick_json = get_ai_editor_pick(papers, config["name_en"], config["ai_preference_prompt"])

        final_data = None
        if pick_json:
            full_paper = next((p for p in papers if p['id'] == pick_json['id']), None)
            if full_paper:
                final_data = {**full_paper, **pick_json}

        output_path = os.path.join(ARCHIVE_DIR, domain_key, f"{target_date.isoformat()}.json")
        write_to_json(final_data, output_path)

    print(f"\n--- 所有领域处理完毕: {target_date.isoformat()} ---")

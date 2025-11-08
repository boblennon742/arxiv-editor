import os
import json
import arxiv
import argparse # 优化：导入 argparse
from google import genai
from datetime import date, timedelta

# --- 1. 配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

# --------------------------------------------------------------------------
# 你的“私人定制”十核 AI 编辑 (V11 - 最终版)
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
def fetch_papers_for_domain(categories, extra_query, target_date):
    print(f"--- 正在为领域 {extra_query[:50]}... (日期 {target_date}) 抓取论文 ---")
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    full_query = f"({category_query}) AND ({extra_query})"

    search = arxiv.Search(
        query=full_query,
        max_results=75, # 10核方案使用 75
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
        print(f"为 {extra_query

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
# 你的“私人定制”十核 AI 编辑 (V10 - 理论驱动效果提升)
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
        "

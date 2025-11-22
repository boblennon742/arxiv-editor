import os
import json
import json5
import arxiv
import re
import time
import random
import logging
from datetime import date, timedelta

from google import genai

# ============================= 配置 =============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError("请设置环境变量 GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

ARCHIVE_DIR = "archive"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# ============================= 三大领域 =============================
YOUR_DOMAINS_OF_INTEREST = {
    "phd_foundations": {
        "name_zh": "AI 理论与统计基础",
        "name_en": "AI Theory & Statistical Foundations",
        "categories": ['stat.ML', 'cs.LG', 'stat.ME', 'math.ST', 'cs.AI', 'cs.CY', 'math.OC', 'stat.TH', 'cs.CV'],
        "search_query": (
            '("statistical learning theory" OR "nonparametric regression" OR "model selection" OR '
            '"high-dimensional inference" OR "uncertainty quantification") OR '
            '("causal inference" OR "fairness" OR "explainable AI" OR "interpretability" OR "treatment effect") OR '
            '("generalization bound" OR "optimization landscape" OR "convergence analysis" OR '
            '"deep neural network theory") OR '
            '("high-dimensional statistics" OR "nonparametric estimation" OR "minimax rate" OR '
            '"statistical guarantees") OR '
            '("representation learning" OR "metric learning" OR "contrastive learning" OR '
            '"self-supervised learning" OR "information bottleneck")'
        ),
        "ai_preference_prompt": """
        我是一名数理统计博士生，专注于将严谨的数学逻辑应用于现代 AI 系统。
        我寻求的论文必须具备强大的理论基础（如统计保证、优化收敛性、因果逻辑）和清晰的数学推导。
        """
    },

    "phd_methods": {
        "name_zh": "前沿 AI 模型与应用",
        "name_en": "Frontier AI Models & Applications",
        "categories": ['cs.LG', 'cs.AI', 'cs.SY', 'cs.CL', 'stat.AP', 'cs.CV', 'eess.IV', 'cs.AR'],
        "search_query": (
            '("Offline Reinforcement Learning" OR "Safe RL" OR "exploration" OR "Multi-Agent" OR "Model-Based RL") OR '
            '("Large Language Model" OR "prompt engineering" OR "RAG system" OR "in-context learning" OR '
            'OR "LLM for data analysis") OR '
            '("Vision Transformer" OR "Diffusion Model" OR "Graph Neural Network" OR "multimodal learning") OR '
            '("efficient AI" OR "model compression" OR "knowledge distillation" OR '
            '"on-device inference" OR "low-resource ML")'
        ),
        "ai_preference_prompt": """
        我是一名数理统计博士生，专注于 AI 的前沿算法和架构。
        我寻求的论文必须逻辑清晰，并能解决实际应用瓶颈。我不喜欢纯粹的工程堆砌，方法必须具有理论创新性。
        """
    },

    "quant_crypto": {
        "name_zh": "量化金融 (Crypto)",
        "name_en": "Quantitative Finance (Crypto)",
        "categories": ['q-fin.ST', 'q-fin.CP', 'q-fin.PM', 'cs.CE', 'stat.ML'],
        "search_query": '("cryptocurrency" OR "digital asset" OR "factor investing" OR '
                       '"algorithmic trading" OR "market microstructure")',
        "ai_preference_prompt": """
        我正在帮助同学构造加密货币市场的量化因子。
        我需要对因子构造、回测、策略设计最有帮助的论文。
        """
    }
}

# ============================= 1. 抓取论文 =============================
def fetch_papers_for_domain(domain_name, categories, extra_query, target_date):
    logger.info(f"抓取 {domain_name} | 日期 {target_date}")
    date_str = target_date.strftime("%Y%m%d")
    date_filter = f"submittedDate:[{date_str}0000 TO {date_str}2359]"
    category_query = " OR ".join(f"cat:{cat}" for cat in categories)
    full_query = f"({category_query}) AND ({extra_query}) AND {date_filter}"

    search = arxiv.Search(
        query=full_query,
        max_results=300,                                   # 加大到 300
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []
    try:
        client = arxiv.Client()
        for result in client.results(search):
            arxiv_id = result.entry_id.split("/")[-1]      # 只存纯 ID，方便匹配
            papers.append({
                "id": arxiv_id,                            # 2411.12345v1
                "title": result.title.strip(),
                "summary": result.summary.replace("\n", " ").strip(),
                "authors": ", ".join(a.name for a in result.authors),
                "url": result.entry_id,                    # 完整链接给人看
                "pdf_url": result.pdf_url,
            })
        logger.info(f"抓取完成 → {len(papers)} 篇")
        return papers
    except Exception as e:
        logger.error(f"arXiv 抓取失败: {e}")
        return []

# ============================= 2. AI 总编辑（带重试 + json5） =============================
def get_ai_editor_pick(papers, domain_name, preference_prompt, max_retries=5):
    if not papers:
        logger.info("无论文可分析")
        return None

    papers_text = "\n".join(
        f"论文 {i+1} | ID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
        for i, p in enumerate(papers)
    )

    system_prompt = f"""
你是我私人 AI 总编辑，今天负责筛选领域：{domain_name}
我的学术偏好如下：
{preference_prompt.strip()}

请严格只返回纯 JSON，不要任何解释文字：
- 如果今天没有好论文 → 返回 null
- 否则返回最多 10 篇最硬核、最符合我偏好的论文（如果真有 10 篇神作就全给我！）

格式：
[
  {{"id": "2411.12345v1", "scores": {{"Novelty":5,"Rigor":5,"Impact":5,"Clarity":5}}, "reason_zh": "详细中文理由"}}
]

开始分析：
""".strip()

    full_prompt = system_prompt + "\n\n" + papers_text

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Gemini 请求中… ({attempt}/{max_retries}) → {domain_name}")
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                )
            )
            text = response.text.strip()

            # 去掉代码块
            text = re.sub(r"^```json\s*|```$", "", text, flags=re.MULTILINE).strip()

            if text.lower() == "null":
                logger.info("AI 认为今天无优质论文")
                return None

            # json5 超宽容解析
            try:
                result = json5.loads(text)
            except:
                result = json.loads(text)

            if isinstance(result, list):
                logger.info(f"成功挑选 {len(result)} 篇神作！")
                return result
            else:
                raise ValueError("返回的不是列表")

        except Exception as e:
            logger.warning(f"第 {attempt} 次失败: {e}")
            if attempt == max_retries:
                logger.error("全部重试失败，放弃该领域")
                return None
            sleep_sec = (2 ** attempt) + random.random()
            logger.info(f"{sleep_sec:.1f}s 后重试...")
            time.sleep(sleep_sec)

    return None

# ============================= 3. 保存结果 =============================
def save_results(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    count = len(data) if data else 0
    logger.info(f"已保存 {filepath} ({count} 篇)")

# ============================= 主程序 =============================
if __name__ == "__main__":
    # ==================== 手动调试时改这里 ====================
    # 想测哪天就改哪天，跑完记得删掉或改回来
    target_date = date(2025, 11, 17)        # 今晚强烈推荐这个日期，神作爆棚！

    # 正式每天自动运行时使用下面这行（现在先注释掉）：
    # target_date = date.today() - timedelta(days=1)

    logger.info(f"ArXiv AI Daily Digest 启动！目标日期：{target_date.isoformat()}")

    for key, cfg in YOUR_DOMAINS_OF_INTEREST.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"正在处理：{cfg['name_zh']} ({cfg['name_en']})")
        logger.info(f"{'='*60}")

        papers = fetch_papers_for_domain(
            domain_name=cfg["name_en"],
            categories=cfg["categories"],
            extra_query=cfg["search_query"],
            target_date=target_date
        )

        picks = get_ai_editor_pick(
            papers=papers,
            domain_name=cfg["name_en"],
            preference_prompt=cfg["ai_preference_prompt"]
        )

        # 合并完整信息
        final = []
        if picks and papers:
            paper_map = {p["id"]: p for p in papers}
            for item in picks:
                pid = item.get("id")
                if pid in paper_map:
                    final.append({**paper_map[pid], **item})

        # 保存（没选中的日子也存 null，方便统计）
        path = os.path.join(ARCHIVE_DIR, key, f"{target_date.isoformat()}.json")
        save_results(final or None, path)

    logger.info("\n全部完成！去 archive/ 目录里看今天的神作吧！")

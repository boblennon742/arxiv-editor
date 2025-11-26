import os
import json
import arxiv
import logging 
import re
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

# --- 1. 配置 Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. 核心配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

ARXIV_CATEGORIES = ['stat.ML', 'cs.LG', 'math.OC', 'cs.NE', 'cs.AI', 'math.NA']
TUTORIAL_KEYWORDS = ['tutorial', 'survey', '"lecture notes"', 'review', '"book chapter"']

# --- 3. 抓取函数 (保持 V19 标准) ---
def fetch_weekly_tutorials(target_date):
    logger.info(f"--- 正在为 {target_date} 所在周抓取教程 (非金融) ---")
    
    one_week_ago = target_date - timedelta(days=6)
    start_str = one_week_ago.strftime("%Y%m%d")
    end_str = target_date.strftime("%Y%m%d")
    date_filter = f"submittedDate:[{start_str}0000 TO {end_str}2359]"
    
    category_query = " OR ".join([f"cat:{cat}" for cat in ARXIV_CATEGORIES])
    keyword_query = " OR ".join([f'(ti:{kw} OR abs:{kw})' for kw in TUTORIAL_KEYWORDS])
    full_query = f"({category_query}) AND ({keyword_query}) AND {date_filter}"
    
    search = arxiv.Search(
        query=full_query,
        max_results=80, #稍微增加一点抓取量以确保有足够的基础内容
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
        logger.info(f"本周共抓取到 {len(papers_list)} 篇教程/综述。")
        return papers_list
    except Exception as e:
        logger.error(f"抓取教程失败: {e}")
        return []

# --- 4. AI 教程总编辑 (V20 - 混合策略 3+3) ---
def get_ai_tutorial_pick(papers, user_preference_prompt):
    if not papers:
        logger.info("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        logger.error("未找到 GEMINI_API_KEY。")
        return None

    client = genai.Client()
    prompt_papers = "\n".join([
        f"--- 教程 {i+1} ---\nID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
        for i, p in enumerate(papers)
    ])

    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手，一个“AI 总编辑”。
    我今天的任务是分析 "本周教程与综述" 领域。
    个人偏好："{user_preference_prompt}"
    
    下面是 {len(papers)} 篇教程。
    
    **任务：请为我精选 Top 10 篇教程，必须严格遵循以下“混合配比”：**
    
    1.  **前沿/深度类 (5 篇):** 针对高维统计、RL、LLM 等领域的最新、最深入的综述。要求理论深度高。
    2.  **基础/入门类 (5 篇):** 针对某一具体数学概念或算法的“入门教程 (Tutorial)”或“讲义 (Lecture Notes)”。要求逻辑极其清晰，适合夯实基础。
    
    **评分标准 (1-5分):**
    - Novelty (创新性)
    - Rigor (理论严谨性)
    - Clarity (清晰度 - 基础类教程此项权重最高)
    - Utility (实用性 - 是否适合学习)

    请返回一个 JSON **列表**。如果找不到足够的，请尽可能多选，但不要凑数。
    
    JSON 格式示例:
    [
      {{
        "id": "论文ID",
        "type": "基础入门" 或 "前沿深度", 
        "scores": {{ "Novelty": 3, "Rigor": 5, "Clarity": 5, "Utility": 5 }},
        "core_value_zh": "一句话核心价值...",
        "reason_zh": "详细推荐理由..."
      }}
    ]
    """
    
    full_prompt = f"{system_prompt}\n\n--- 教程列表 ---\n{prompt_papers}"

    max_retries = 5
    base_delay = 10

    for attempt in range(max_retries):
        try:
            logger.info(f"🚀 请求 AI 教程分析 (混合策略, 第 {attempt + 1}/{max_retries} 次)...")
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(temperature=0.4) # 稍微提高温度以增加多样性
            )
            
            cleaned = response.text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```\w*\n", "", cleaned)
                cleaned = re.sub(r"\n```$", "", cleaned)
            cleaned = cleaned.strip()

            match = re.search(r'(\[.*\])', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1)
            
            ai_picks_list = json5.loads(cleaned)
            logger.info(f"✅ AI 成功选出 {len(ai_picks_list)} 篇混合教程。")
            return ai_picks_list

        except Exception as e:
            logger.warning(f"⚠️ 第 {attempt + 1} 次尝试失败: {e}")
            if attempt < max_retries - 1:
                wait_time = base_delay * (2 ** attempt) + random.uniform(0, 3)
                time.sleep(wait_time)
            else:
                return None

# --- 5. 写入 JSON ---
def write_to_json(data_to_save, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"写入教程 JSON 失败: {e}")

# --- 6. 主函数 ---
if __name__ == "__main__":
    target_date = date.today()
    logger.info(f"--- 教程脚本开始运行，目标周: {target_date.isoformat()} ---")

    # (V21) 偏好升级：将“基础”明确定义为“研究生核心课”
    my_tutorial_preference = """
    我是一名数理统计博士生，我的学习需求分为两类（请各选 5 篇）：
    
    1. **前沿研究 (Research Frontier):** - 关注高维统计、因果推断、Offline RL、LLM 理论机制、加密货币量化等领域的最新综述。
       - 要求：视野开阔，能指引未来的研究方向。
    
    2. **研究生核心基础 (Graduate Core Foundations):** - 我需要针对**统计学与数据科学研究生**的**基础核心课程**级别的教程 (Tutorials) 或讲义 (Lecture Notes)。
       - **核心主题：** 矩阵分析 (Matrix Analysis)、凸优化 (Convex Optimization)、高等概率论/随机过程、贝叶斯推断基础、信息论等。
       - **要求：** 必须具有**数学严谨性 (Mathematical Rigor)**，文笔流畅，逻辑清晰。**不要**科普读物，我要的是能帮我补全博士数学拼图的硬核资料。
    
    请务必严格按照 50% 前沿 + 50% 核心基础的比例进行筛选。
    """
   
    papers = fetch_weekly_tutorials(target_date)
    pick_json_list = get_ai_tutorial_pick(papers, my_tutorial_preference)
   
    final_data_to_save = []
    if pick_json_list:
        for pick_item in pick_json_list:
            full_paper = next((p for p in papers if p['id'] == pick_item['id']), None)
            if full_paper:
                final_data_to_save.append({**full_paper, **pick_item})
    
    if not final_data_to_save:
         final_data_to_save = None
           
    week_number = target_date.isocalendar()[1]
    year = target_date.isocalendar()[0]
    output_filename = f"{year}-W{week_number:02d}.json"
    output_path = os.path.join(ARCHIVE_DIR, "tutorials", output_filename)
   
    write_to_json(final_data_to_save, output_path)
    logger.info(f"\n--- 教程脚本处理完毕 ---")

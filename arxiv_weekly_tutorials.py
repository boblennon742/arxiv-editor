#!/usr/bin/env python3
import os
import json
import arxiv
import logging 
import re
from google import genai
from datetime import date, timedelta

# --- 1. 配置 Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. 核心配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

ARXIV_CATEGORIES = ['stat.ML', 'cs.LG', 'math.OC', 'cs.NE', 'cs.AI', 'math.NA']
TUTORIAL_KEYWORDS = ['tutorial', 'survey', '"lecture notes"', 'review', '"book chapter"']

# --- 3. 抓取函数（已修复：submittedDate 过滤一周）---
def fetch_weekly_tutorials(target_date):
    logger.info(f"--- 正在为 {target_date} 所在周抓取教程 (非金融) ---")
    
    # 计算一周前（包含今天，共 7 天）
    one_week_ago = target_date - timedelta(days=6)
    
    # 关键：API 端精确日期过滤
    start_str = one_week_ago.strftime("%Y%m%d")
    end_str = target_date.strftime("%Y%m%d")
    date_filter = f"submittedDate:[{start_str}0000 TO {end_str}2359]"
    
    category_query = " OR ".join([f"cat:{cat}" for cat in ARXIV_CATEGORIES])
    keyword_query = " OR ".join([f'(ti:"{kw}" OR abs:"{kw}")' for kw in TUTORIAL_KEYWORDS])
    full_query = f"({category_query}) AND ({keyword_query}) AND {date_filter}"
    
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

# --------------------------------------------------------------------------
# (V17.1) AI 教程总编辑 (重构为“评分引擎”)
# --------------------------------------------------------------------------
def get_ai_tutorial_pick(papers, user_preference_prompt):
    if not papers:
        logger.info("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        logger.error("未找到 GEMINI_API_KEY。")
        return None

    logger.info("正在请求 AI 教程总编辑挑选 Top 2 篇并评分...")
    client = genai.Client()
    prompt_papers = "\n".join([
        f"--- 教程 {i+1} ---\nID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
        for i, p in enumerate(papers)
    ])

    # (V17.1) 关键修改：使用与每日脚本一致的评分提示词
    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手，一个“AI 总编辑”。
    我今天的任务是分析 "本周教程与综述" 领域。

    我的个人偏好/任务是：
    "{user_preference_prompt}"
    
    下面是为该领域抓取的 {len(papers)} 篇教程或综述。
    你的任务是“批量评分和筛选”：
    1.  **评分：** 根据以下 4 个标准（1-5分）为每一篇论文打分：
        - Novelty (创新性): 提出新方法或新视角 (1-5分)
        - Rigor (理论严谨性): 数学/统计推导是否严谨 (1-5分)
        - Impact (实践影响力): 是否可落地、能提高效果 (1-5分)
        - Clarity (清晰度): 是否深入浅出、逻辑脉络清晰 (1-5分)
    2.  **排序：** 根据我的个人偏好（特别是 Clarity 和 Rigor），结合上述 4 个维度的分数，计算一个**总分**。
    3.  **筛选：** 挑选出**总分最高的 2 篇（最多 2 篇）**教程。
    4.  **返回：** 如果没有一篇论文足够好，请**必须**返回 `null`。如果你找到了，请以严格的 JSON **列表** 格式返回。
    
    JSON 格式如下：
    [
      {{
        "id": "被选中论文1的 ID",
        "scores": {{
          "Novelty": 5,
          "Rigor": 4,
          "Impact": 5,
          "Clarity": 4
        }},
        "reason_zh": "（中文）详细说明为什么这篇教程**总分最高**并**完全符合**我的偏好/任务。"
      }},
      ... (最多 2 篇)
    ]
    如果返回 `null`，就只返回 `null` 这个词。
    """
    
    full_prompt = f"{system_prompt}\n\n--- 教程列表开始 ---\n{prompt_papers}\n--- 教程列表结束 ---"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        
        # (V17.1) 鲁棒性 JSON 清理 (查找列表)
        cleaned = response.text.strip().lstrip("```json").rstrip("```").strip()
        match = re.search(r'(\[.*?\])', cleaned, re.DOTALL) 

        if not match:
             if cleaned.lower() == 'null':
                 logger.info("AI 教程编辑认为本周没有值得推荐的。")
                 return None
             
             logger.error(f"AI 输出的文本中找不到 JSON 列表结构。输出：{response.text[:200]}...")
             raise json.JSONDecodeError("JSON 列表结构缺失", response.text, 0)
        
        json_string = match.group(1) 
        
        ai_picks_list = json.loads(json_string) 
        logger.info(f"AI 教程编辑已选出 {len(ai_picks_list)} 篇本周最佳。")
        return ai_picks_list

    except json.JSONDecodeError as e:
        logger.error(f"AI 总编辑分析失败: 无法解析 JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"AI 总编辑分析失败: {e}")
        return None

# --- 5. 写入 JSON ---
def write_to_json(data_to_save, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            if data_to_save:
                logger.info(f"成功将 {len(data_to_save)} 篇“本周教程精选”写入 {file_path}")
            else:
                logger.info(f"标记 {file_path} 为“无教程精选”。")
    except Exception as e:
        logger.error(f"写入教程 JSON 失败: {e}")

# --- 6. 主函数 ---
if __name__ == "__main__":
    target_date = date.today()
    
    logger.info(f"--- 教程脚本开始运行 (V17 评分版)，目标周 (基于日期): {target_date.isoformat()} ---")

    # (V17.1) 保留您最终确定的、包含“文笔与结构”要求的偏好文本
    my_tutorial_preference = """
    我是一名数理统计博士生，专注于将严谨的数学逻辑应用于现代 AI 系统，以提升其鲁棒性和效果。
    
    我寻求的教程/综述必须满足以下兴趣点，且能够深入浅出地解释原理：
    
    1.  **统计基础与保证：** 专注于高维统计、因果推断、模型泛化界限的数学基础。
    2.  **现代方法论：** 解决深度学习优化、高级强化学习（Offline/Safe RL）、表示学习的理论瓶颈。
    3.  **前沿应用：** 涉及 LLM 在数据科学中的应用，或高效 AI（模型压缩）的原理和实践。
    4.  **文笔与结构：** 文章的**逻辑脉络必须清晰**、**文笔流畅**，且能够**循序渐进**、深入浅出地解释复杂的数学和技术概念。
    
    **【关键排除项】**
    我**不**喜欢：过于抽象、缺乏应用场景验证的纯概率论、纯随机分析、假设检验或“空中楼阁”式的理论。我追求逻辑性强、可落地的知识。
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
    
    logger.info(f"\n--- 教程脚本处理完毕: {output_filename} ---")

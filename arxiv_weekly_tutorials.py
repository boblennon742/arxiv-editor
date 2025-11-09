import os
import json
import arxiv
# import argparse # <-- 已移除
from google import genai
from datetime import date, timedelta

# --- 1. 配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

ARXIV_CATEGORIES = ['stat.ML', 'cs.LG', 'math.OC', 'cs.NE', 'cs.AI', 'math.NA']
TUTORIAL_KEYWORDS = ['tutorial', 'survey', '"lecture notes"', 'review', '"book chapter"']

# --- 2. 抓取函数 ---
def fetch_weekly_tutorials(target_date):
    print(f"--- 正在为 {target_date} 所在周抓取教程 (非金融) ---")
    one_week_ago = target_date - timedelta(days=7)
   
    category_query = " OR ".join([f"cat:{cat}" for cat in ARXIV_CATEGORIES])
    keyword_query = " OR ".join([f'(ti:{kw} OR abs:{kw})' for kw in TUTORIAL_KEYWORDS])
    full_query = f"({category_query}) AND ({keyword_query})"
   
    search = arxiv.Search(
        query=full_query,
        max_results=50,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
   
    papers_list = []
    try:
        client = arxiv.Client()
        for result in client.results(search):
            paper_date = result.published.date()
            if paper_date < one_week_ago:
                break
            if one_week_ago <= paper_date <= target_date:
                papers_list.append({
                    'id': result.entry_id,
                    'title': result.title,
                    'summary': result.summary.replace("\n", " "),
                    'authors': ", ".join([a.name for a in result.authors]),
                    'url': result.entry_id,
                    'pdf_url': result.pdf_url
                })
        print(f"本周共抓取到 {len(papers_list)} 篇教程/综述。")
        return papers_list
    except Exception as e:
        print(f"抓取教程失败: {e}")
        return []

# --- 3. AI 教程总编辑 (优选 2 篇) ---
def get_ai_tutorial_pick(papers, user_preference_prompt):
    if not papers:
        print("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        print("未找到 GEMINI_API_KEY。")
        return None

    print("正在请求 AI 教程总编辑挑选 2 篇...")
    client = genai.Client()
    prompt_papers = "\n".join([
        f"--- ID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n"
        for p in papers
    ])

    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手，一个“AI 总编辑”。
    我今天的任务是分析 "本周教程与综述" 领域。

    我的个人偏好/任务是：
    "{user_preference_prompt}"
    
    下面是为该领域抓取的 {len(papers)} 篇教程或综述。
    你的任务是“优中选优”：
    1. 严格根据我的个人偏好/任务，从这些论文中挑选出 **2 篇（最多 2 篇）** 最值得我阅读的教程/综述。
    2. 如果只有 1 篇符合，则只返回 1 篇。
    3. 如果**没有一篇**论文足够好或符合我的需求，请**必须**返回 `null`。
    4. 如果你找到了，请以严格的 JSON **列表** 格式返回，即使只有 1 篇，也要放在列表里。
    JSON 格式如下：
    [
      {{
        "id": "被选中论文1的 ID",
        "reason_zh": "（中文）详细说明为什么这篇教程**完全符合**我的偏好/任务。",
        "reason_en": "(English) A detailed justification of why this tutorial **perfectly fits** my preference/task."
      }},
      {{
        "id": "被选中论文2的 ID",
        "reason_zh": "（中文）详细说明为什么这篇教程**完全符合**我的偏好/任务。",
        "reason_en": "(English) A detailed justification of why this tutorial **perfectly fits** my preference/task."
      }}
    ]
    如果返回 `null`，就只返回 `null` 这个词。
    """

    full_prompt = f"{system_prompt}\n\n--- 教程列表开始 ---\n{prompt_papers}\n--- 教程列表结束 ---"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        cleaned = response.text.strip().lstrip("```json").rstrip("```")

        if cleaned.lower() == 'null':
            print("AI 教程编辑认为本周没有值得推荐的。")
            return None

        ai_picks_list = json.loads(cleaned)
        print(f"AI 教程编辑已选出 {len(ai_picks_list)} 篇本周最佳。")
        return ai_picks_list
    except Exception as e:
        print(f"AI 教程编辑分析失败: {e}")
        return None

# --- 4. 写入 JSON ---
def write_to_json(data_to_save, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            if data_to_save:
                print(f"成功将 {len(data_to_save)} 篇“本周教程精选”写入 {file_path}")
            else:
                print(f"标记 {file_path} 为“无教程精选”。")
    except Exception as e:
        print(f"写入教程 JSON 失败: {e}")

# --- 5. 主函数 ---
if __name__ == "__main__":
    # (V12) 关键修改：移除 argparse，恢复硬编码日期
    target_date = date.today()
    
    print(f"--- 教程脚本开始运行，目标周 (基于日期): {target_date.isoformat()} ---")

    my_tutorial_preference = """
    我是一名数理统计博士生，专注于将严谨的数学逻辑应用于现代 AI 系统，以提升其鲁棒性和效果。
    
    我寻求的教程/综述必须满足以下兴趣点，且能够深入浅出地解释原理：
    
    1.  **统计基础与保证：** 专注于高维统计、因果推断、模型泛化界限的数学基础。
    2.  **现代方法论：** 解决深度学习优化、高级强化学习（Offline/Safe RL）、表示学习的理论瓶颈。
    3.  **前沿应用：** 涉及 LLM 在数据科学中的应用，或高效 AI（模型压缩）的原理和实践。
    4.  **跨领域能力：** 对我的量化金融项目（加密货币因子构造）有直接指导作用。
    
    **【关键排除项】**
    我**不**喜欢：过于抽象、缺乏应用场景验证的纯概率论、纯随机分析或“空中楼阁”式的理论。我追求逻辑性强、可落地的知识。
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
    
    print(f"\n--- 教程脚本处理完毕: {output_filename} ---")

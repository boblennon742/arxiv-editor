import os
import json
import arxiv
from google import genai
from datetime import date, timedelta

# --- 1. 配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"
# V8 更新：排除了 q-fin，因为金融每天都看
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
        max_results=30,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    papers_list = []
    try:
        # ------------------- 关键修改区域 -------------------
        # 实例化新的 Client
        client = arxiv.Client()
        
        # 使用 client.results(search) 替代 search.results()
        for result in client.results(search):
        # ----------------------------------------------------
            paper_date = result.published.date()
            
            # 由于是降序排列，一旦超过时间范围即可停止
            if paper_date < one_week_ago:
                break
            
            # 过滤掉未来的日期（尽管不常见）和精确到目标日期的论文
            if paper_date >= one_week_ago and paper_date <= target_date:
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

# --- 3. AI 教程总编辑 (V8 版) ---
def get_ai_tutorial_pick(papers, user_preference_prompt):
    if not papers: return None
    if not GEMINI_API_KEY: return None
    
    print("正在请求 AI 教程总编辑挑选 1 篇...")
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt_papers = "\n".join([f"--- ID: {p['id']}\n标题: {p['title']}\n摘要: {p['summary']}\n" for p in papers])
    
    # V8 核心：个性化的教程 AI 指令
    system_prompt = f"""
    你是我（统计学硕士）的“AI 总编辑”。
    我的个人兴趣是：{user_preference_prompt}

    下面是本周发布的 {len(papers)} 篇教程(Tutorials)或综述(Surveys)。
    你的任务是“精中选精”：
    1.  从列表中挑选 **1 篇（最多 1 篇）** 最值得我阅读的教程。
    2.  如果**没有一篇**足够好，请**必须**返回 `null`。
    3.  如果你找到了 1 篇，请以严格的 JSON 格式返回。
    JSON 格式如下：
    {{
      "id": "被选中论文的 ID",
      "reason_zh": "（中文）详细说明为什么这篇教程是‘精中选精’，它如何深入浅出？",
      "reason_en": "(English) A detailed justification of why this tutorial is the 'best of the best' and 'insightful'."
    }}
    如果返回 `null`，就只返回 `null` 这个词。
    """
    
    full_prompt = f"{system_prompt}\n\n--- 教程列表开始 ---\n{prompt_papers}\n--- 教程列表结束 ---"
    
    try:
        response = model.generate_content(full_prompt)
        cleaned_response = response.text.strip().lstrip("```json").rstrip("```")
        
        if cleaned_response.lower() == 'null':
            print("AI 教程编辑认为本周没有值得推荐的。")
            return None
        
        ai_pick_json = json.loads(cleaned_response)
        print("AI 教程编辑已选出本周最佳。")
        return ai_pick_json
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
                print(f"成功将“本周教程精选”写入 {file_path}")
            else:
                print(f"标记 {file_path} 为“无教程精选”。")
    except Exception as e:
        print(f"写入教程 JSON 失败: {e}")

# --- 5. 主函数 ---
if __name__ == "__main__":
    target_date = date.today()
    # V8 教程偏好
    my_tutorial_preference = """
    我喜欢深入浅出、可落地的前沿技术（如强化学习、优化方法），也喜欢扎实的数学基础（如矩阵代数）。
    我**不**喜欢过于抽象、无法应用的“空中楼阁”式纯理论。
    """
    
    papers = fetch_weekly_tutorials(target_date)
    pick_json = get_ai_tutorial_pick(papers, my_tutorial_preference)
    
    final_data_to_save = None
    if pick_json:
        full_paper = next((p for p in papers if p['id'] == pick_json['id']), None)
        if full_paper:
            final_data_to_save = {**full_paper, **pick_json}
            
    week_number = target_date.isocalendar()[1]
    year = target_date.isocalendar()[0]
    output_filename = f"{year}-W{week_number:02d}.json"
    output_path = os.path.join(ARCHIVE_DIR, "tutorials", output_filename)
    
    write_to_json(final_data_to_save, output_path)

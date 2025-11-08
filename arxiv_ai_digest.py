import os
import json
import arxiv
import google.generativeai as genai
from datetime import date, timedelta, datetime

# --- 1. 配置 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ARCHIVE_DIR = "archive"

# --------------------------------------------------------------------------
# 你的“私人定制”双核 AI 编辑 (V8 最终版)
# --------------------------------------------------------------------------
YOUR_DOMAINS_OF_INTEREST = {
    "bayes_ml": {
        "name_zh": "ML/贝叶斯/DS",
        "name_en": "ML/Bayes/DS",
        "categories": ['stat.ML', 'cs.LG', 'stat.ME', 'cs.AI', 'math.OC'],
        "search_query": '("machine learning" OR "bayesian" OR "data science" OR optimization)',
        "ai_preference_prompt": """
        我是一名数理统计硕士。我喜欢应用贝叶斯、机器学习、数据科学项目，以及它们背后逻辑性强、可落地的数学理论（如优化方法）。
        我**不**喜欢纯概率论或随机分析。
        请从列表中，为我挑选 1 篇**最具有启发性、逻辑性强、且可应用**的论文。
        """
    },
    "quant_crypto": {
        "name_zh": "量化金融 (Crypto)",
        "name_en": "Quantitative Finance (Crypto)",
        "categories": ['q-fin.ST', 'q-fin.CP', 'q-fin.PM', 'cs.CE', 'stat.ML'],
        "search_query": '("quantitative finance" OR "crypto" OR "cryptocurrency" OR "digital asset" OR "factor investing" OR "algorithmic trading")',
        "ai_preference_prompt": """
        我正在帮助同学**构造加密货币市场的量化因子**。
        请从列表中，为我挑选 1 篇对**这个具体任务**（因子构造、回测、加密货币市场分析、算法交易策略）**最有帮助**的论文。
        """
    }
}
# --------------------------------------------------------------------------

# 抓取函数
def fetch_papers_for_domain(categories, extra_query, target_date):
    print(f"--- 正在为领域 {extra_query} (日期 {target_date}) 抓取论文 ---")
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    full_query = f"({category_query}) AND ({extra_query})"
    
    search = arxiv.Search(
        query=full_query,
        max_results=50, # 每个领域抓 50 篇来筛选
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    papers_list = []
    try:
        # ------------------- 关键修改区域 -------------------
        # 1. 实例化一个新的 Client (修复 DeprecationWarning)
        client = arxiv.Client()
        
        # 2. 使用 client.results(search) 替代 search.results()
        for result in client.results(search):
        # ----------------------------------------------------
            paper_date = result.published.date()
            
            # 由于 arXiv 搜索结果不保证严格按日期排序，我们使用 Python 过滤
            if paper_date < target_date:
                # 因为是按Descending顺序排序，一旦日期小于目标日期，就可以停止了
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
        print(f"为 {extra_query} 抓取到 {len(papers_list)} 篇论文。")
        return papers_list
    except Exception as e:
        print(f"抓取 arXiv 失败: {e}")
        return []

# AI 分析函数 (V8)
def get_ai_editor_pick(papers, domain_name, user_preference_prompt):
    if not papers:
        print("没有论文可供 AI 分析。")
        return None
    if not GEMINI_API_KEY:
        print("未找到 GEMINI_API_KEY。")
        return None
        
    print(f"正在请求 AI 总编辑为 {domain_name} 领域挑选 1 篇...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt_papers = []
    for i, paper in enumerate(papers):
        prompt_papers.append(f"--- 论文 {i+1} ---\nID: {paper['id']}\n标题: {paper['title']}\n摘要: {paper['summary']}\n")
    papers_string = "\n".join(prompt_papers)

    # V8 核心：个性化的 AI 指令
    system_prompt = f"""
    你是我（统计学硕士）的私人研究助手，一个“AI 总编辑”。
    我今天的任务是分析 "{domain_name}" 领域。
    
    我的个人偏好/任务是：
    "{user_preference_prompt}"

    下面是为该领域抓取的 {len(papers)} 篇论文。
    你的任务是“精中选精”：
    1.  严格根据我的个人偏好/任务，从这些论文中挑选出 **1 篇（最多 1 篇）** 最值得我阅读的论文。
    2.  如果**没有一篇**论文足够好或符合我的需求，请**必须**返回 `null`。
    3.  如果你找到了 1 篇，请以严格的 JSON 格式返回，不要有任何其他文字。
    JSON 格式如下：
    {{
      "id": "被选中论文的 ID",
      "reason_zh": "（中文）详细说明为什么这篇论文**完全符合**我的偏好/任务。",
      "reason_en": "(English) A detailed justification of why this paper **perfectly fits** my preference/task."
    }}
    如果返回 `null`，就只返回 `null` 这个词。
    """
    
    full_prompt = f"{system_prompt}\n\n--- 论文列表开始 ---\n{papers_string}\n--- 论文列表结束 ---"

    try:
        response = model.generate_content(full_prompt)
        cleaned_response = response.text.strip().lstrip("```json").rstrip("```")
        
        if cleaned_response.lower() == 'null':
            print("AI 编辑认为今天没有值得推荐的。")
            return None
        
        ai_pick_json = json.loads(cleaned_response)
        print("AI 编辑已选出今日最佳。")
        return ai_pick_json
    except Exception as e:
        print(f"AI 总编辑分析失败: {e}")
        return None

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

# --- 主函数 ---
if __name__ == "__main__":
    target_date = date.today() - timedelta(days=1)
    
    for domain_key, config in YOUR_DOMAINS_OF_INTEREST.items():
        # 1. 抓取
        papers = fetch_papers_for_domain(config["categories"], config["search_query"], target_date)
        
        # 2. AI 挑选 (传入个性化指令)
        pick_json = get_ai_editor_pick(papers, config["name_en"], config["ai_preference_prompt"])
        
        # 3. 准备存档数据
        final_data_to_save = None
        if pick_json:
            full_paper = next((p for p in papers if p['id'] == pick_json['id']), None)
            if full_paper:
                final_data_to_save = {**full_paper, **pick_json} 
        
        # 4. 存档
        output_filename = f"{target_date.isoformat()}.json"
        output_path = os.path.join(ARCHIVE_DIR, domain_key, output_filename)
        write_to_json(final_data_to_save, output_path)

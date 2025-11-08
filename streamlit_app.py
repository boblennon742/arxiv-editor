import streamlit as st
import json
import os
from datetime import date, timedelta

# --- 1. 配置 ---
ARCHIVE_DIR = "archive"

st.set_page_config(page_title="私人 AI 总编辑", layout="wide")

# (V11) 关键修改：使用 10 核配置
YOUR_DOMAINS_OF_INTEREST = {
    "stat_ml_foundations": {
        "name_zh": "统计/ML基础理论",
        "name_en": "Statistical ML Foundations"
    },
    "causal_theory": {
        "name_zh": "因果推断/可解释性",
        "name_en": "Causal Inference & XAI"
    },
    "deep_model_theory": {
        "name_zh": "深度模型理论与优化",
        "name_en": "Deep Model Theory & Optimization"
    },
    "advanced_rl": {
        "name_zh": "高级强化学习",
        "name_en": "Advanced Reinforcement Learning"
    },
    "llm_ds": {
        "name_zh": "大模型与数据科学",
        "name_en": "LLM & Data Science"
    },
    "dl_architecture": {
        "name_zh": "前沿架构与应用",
        "name_en": "DL Architectures & Applications"
    },
    "quant_crypto": {
        "name_zh": "量化金融 (Crypto)",
        "name_en": "Quantitative Finance (Crypto)"
    },
    "high_dim_stats": {
        "name_zh": "高维统计与泛化",
        "name_en": "High-Dimensional Stats & Guarantees"
    },
    "representation_learning": {
        "name_zh": "表示学习与度量",
        "name_en": "Representation & Metric Learning"
    },
    "efficient_ai": {
        "name_zh": "高效/边缘计算 AI",
        "name_en": "Efficient & Edge AI"
    }
}
TUTORIAL_DOMAIN = {
    "tutorials": "每周教程精选"
}

# --- 2. 语言选择器 ---
lang = st.radio(
    "选择语言 / Select Language",
    ["简体中文", "English"],
    horizontal=True,
    label_visibility="collapsed"
)

if lang == "简体中文":
    st.title("🤖 私人 AI 总编辑")
    st.caption("由 AI 每日为我精选的博士研究必读论文")
else:
    st.title("🤖 Personal AI Editor")
    st.caption("Daily 'Must-Read' papers for my PhD research, curated by AI.")

# --- 3. 标签页设计 ---
tab_daily, tab_weekly = st.tabs([
    "📅 " + ("每日精选 (10核)" if lang == "简体中文" else "Daily Picks (10-Core)"), 
    "🏆 " + ("每周教程 (优选 2)" if lang == "简体中文" else "Weekly Tutorials (Top 2)")
])

# --- (V11) 每日精选标签页 (10 核动态布局) ---
with tab_daily:
    if lang == "简体中文":
        selected_date = st.date_input("选择一个日期", date.today() - timedelta(days=1))
    else:
        selected_date = st.date_input("Select a date", date.today() - timedelta(days=1))
    
    st.divider()
    
    # 动态生成列以显示所有领域
    num_columns = 3 # 每行显示 3 个
    domain_keys = list(YOUR_DOMAINS_OF_INTEREST.keys())
    cols = st.columns(num_columns)
    
    # 循环遍历所有领域，并将它们分配到列中
    for i, domain_key in enumerate(domain_keys):
        with cols[i % num_columns]: # 使用取余 (%) 动态分配
            
            domain_config = YOUR_DOMAINS_OF_INTEREST[domain_key]
            domain_name = domain_config["name_zh"] if lang == "简体中文" else domain_config["name_en"]
            st.subheader(domain_name, divider="rainbow")
            
            file_path = os.path.join(ARCHIVE_DIR, domain_key, f"{selected_date.isoformat()}.json")
            
            # 渲染逻辑 (用于单个 pick)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    pick = json.load(f) # 每日精选仍然是单个对象
                
                if pick:
                    st.markdown(f"**[{pick['title']}]({pick['url']})**")
                    authors_label = "作者" if lang == "简体中文" else "Authors"
                    st.caption(f"**{authors_label}:** {pick['authors']}")
                    
                    if lang == "简体中文":
                        reason, reason_label = pick.get('reason_zh', 'N/A'), "AI 编辑推荐理由"
                    else:
                        reason, reason_label = pick.get('reason_en', 'N/A'), "AI Editor's Justification"
                    st.info(f"**🤖 {reason_label}:** {reason}")
                    
                    expander_label = "查看摘要" if lang == "简体中文" else "View Abstract"
                    with st.expander(expander_label):
                        st.write(pick['summary'])
                    pdf_label = "下载 PDF ➔" if lang == "简体中文" else "Download PDF ➔"
                    st.link_button(pdf_label, pick['pdf_url'])
                else:
                    no_pick_text = "今日 AI 编辑未发现值得一读的论文。" if lang == "简体中文" else "The AI Editor found no 'must-reads' today."
                    st.write(no_pick_text)
            except FileNotFoundError:
                st.write("尚无数据。" if lang == "简体中文" else "No data yet.")

# --- (V11) 每周教程标签页 (循环渲染 2 篇) ---
with tab_weekly:
    today = date.today()
    year = today.isocalendar()[0]
    week_number = today.isocalendar()[1]
    
    week_options = {}
    if lang == "简体中文":
        week_options[f"{year}-W{week_number:02d}"] = f"{year}-W{week_number:02d} (本周)"
        week_options[f"{year}-W{week_number-1:02d}"] = f"{year}-W{week_number-1:02d} (上周)"
    else:
        week_options[f"{year}-W{week_number:02d}"] = f"{year}-W{week_number:02d} (This Week)"
        week_options[f"{year}-W{week_number-1:02d}"] = f"{year}-W{week_number-1:02d} (Last Week)"
        
    week_str_display = st.selectbox("选择周" if lang == "简体中文" else "Select week", options=week_options.values())
    week_str = [k for k, v in week_options.items() if v == week_str_display][0]

    st.divider()
    
    st.header(TUTORIAL_DOMAIN["tutorials"], divider="rainbow")
    file_path = os.path.join(ARCHIVE_DIR, "tutorials", f"{week_str}.json")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            picks_list = json.load(f) # <--- 关键修改：读取列表
        
        if picks_list: # <--- 关键修改：检查列表是否非空
            
            # (V11) 循环渲染列表中的每一篇教程
            for i, pick in enumerate(picks_list):
                
                st.markdown(f"**{i+1}. [{pick['title']}]({pick['url']})**")
                authors_label = "作者" if lang == "简体中文" else "Authors"
                st.caption(f"**{authors_label}:** {pick['authors']}")
                
                if lang == "简体中文":
                    reason, reason_label = pick.get('reason_zh', 'N/A'), "AI 编辑推荐理由"
                else:
                    reason, reason_label = pick.get('reason_en', 'N/A'), "AI Editor's Justification"
                st.info(f"**🏆 {reason_label}:** {reason}")
                
                expander_label = "查看摘要" if lang == "简体中文" else "View Abstract"
                with st.expander(expander_label):
                    st.write(pick['summary'])
                pdf_label = "下载 PDF ➔" if lang == "简体中文" else "Download PDF ➔"
                st.link_button(pdf_label, pick['pdf_url'])
                
                if i < len(picks_list) - 1: # 如果不是最后一篇，添加分隔线
                    st.divider()

        else:
            no_pick_text = "本周 AI 编辑未发现值得一读的教程。" if lang == "简体中文" else "The AI Editor found no 'must-read' tutorials this week."
            st.write(no_pick_text)
    except FileNotFoundError:
        st.write("尚无本周数据。" if lang == "简体中文" else "No data yet for this week.")

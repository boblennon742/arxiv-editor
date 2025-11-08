import streamlit as st
import json
import os
from datetime import date, timedelta

# --- 1. 配置 ---
ARCHIVE_DIR = "archive"

st.set_page_config(page_title="私人 AI 总编辑", layout="wide")

# (V8) 从 arxiv_ai_digest.py 复制过来，确保两边一致
YOUR_DOMAINS_OF_INTEREST = {
    "bayes_ml": {
        "name_zh": "ML/贝叶斯/DS",
        "name_en": "ML/Bayes/DS"
    },
    "quant_crypto": {
        "name_zh": "量化金融 (Crypto)",
        "name_en": "Quantitative Finance (Crypto)"
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
    st.caption("由 AI 每日为我精选的“ML/DS”与“量化金融”必读论文")
else:
    st.title("🤖 Personal AI Editor")
    st.caption("Daily 'Must-Read' ML/DS & Quant Finance papers, curated for me by AI.")

# --- 3. 标签页设计 ---
tab_daily, tab_weekly = st.tabs([
    "📅 " + ("每日双核精选" if lang == "简体中文" else "Daily Dual-Core Picks"), 
    "🏆 " + ("每周教程" if lang == "简体中文" else "Weekly Tutorial")
])

# --- 每日精选标签页 ---
with tab_daily:
    if lang == "简体中文":
        selected_date = st.date_input("选择一个日期", date.today() - timedelta(days=1))
    else:
        selected_date = st.date_input("Select a date", date.today() - timedelta(days=1))
    
    st.divider()
    
    # (V8) 创建 2 个分栏
    col1, col2 = st.columns(2)
    
    # 从配置中获取两个域的 key
    domain_key_1 = list(YOUR_DOMAINS_OF_INTEREST.keys())[0]
    domain_key_2 = list(YOUR_DOMAINS_OF_INTEREST.keys())[1]

    # --- 渲染第 1 栏 (ML/Bayes) ---
    with col1:
        domain_config = YOUR_DOMAINS_OF_INTEREST[domain_key_1]
        domain_name = domain_config["name_zh"] if lang == "简体中文" else domain_config["name_en"]
        st.subheader(domain_name, divider="rainbow")
        
        file_path = os.path.join(ARCHIVE_DIR, domain_key_1, f"{selected_date.isoformat()}.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pick = json.load(f)
            
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

    # --- 渲染第 2 栏 (Quant/Crypto) ---
    with col2:
        domain_config = YOUR_DOMAINS_OF_INTEREST[domain_key_2]
        domain_name = domain_config["name_zh"] if lang == "简体中文" else domain_config["name_en"]
        st.subheader(domain_name, divider="rainbow")
        
        file_path = os.path.join(ARCHIVE_DIR, domain_key_2, f"{selected_date.isoformat()}.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pick = json.load(f)
            
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

# --- 每周教程标签页 ---
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
            pick = json.load(f)
        
        if pick:
            st.markdown(f"**[{pick['title']}]({pick['url']})**")
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
        else:
            no_pick_text = "本周 AI 编辑未发现值得一读的教程。" if lang == "简体中文" else "The AI Editor found no 'must-read' tutorials this week."
            st.write(no_pick_text)
    except FileNotFoundError:
        st.write("尚无本周数据。" if lang == "简体中文" else "No data yet for this week.")

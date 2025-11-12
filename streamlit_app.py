import streamlit as st
import json
import os
from datetime import date, timedelta
# import pandas as pd # (目前不需要，但未来分析可能需要)

# --- 1. 配置 (V17.1 - 3核评分版 + 新命名) ---
ARCHIVE_DIR = "archive"

st.set_page_config(page_title="私人 AI 总编辑", layout="wide")

# (V17.1) 关键修改：更新为 3 核配置和新名称
YOUR_DOMAINS_OF_INTEREST = {
    "phd_foundations": {
        "name_zh": "AI 理论与统计基础",
        "name_en": "AI Theory & Statistical Foundations"
    },
    "phd_methods": {
        "name_zh": "前沿 AI 模型与应用",
        "name_en": "Frontier AI Models & Applications"
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
    st.caption("由 AI 每日为我评分精选的研究论文")
else:
    st.title("🤖 Personal AI Editor")
    st.caption("Daily 'Must-Read' papers, scored and curated by AI.")

# --- 3. 标签页设计 ---
tab_daily, tab_weekly = st.tabs([
    "📅 " + ("每日精选" if lang == "简体中文" else "Daily Picks"), 
    "🏆 " + ("每周教程" if lang == "简体中文" else "Weekly Tutorials")
])

# --------------------------------------------------------------------------
# (V17.1) 关键修改：重写每日精选标签页
# --------------------------------------------------------------------------
with tab_daily:
    if lang == "简体中文":
        selected_date = st.date_input("选择一个日期", date.today() - timedelta(days=1))
    else:
        selected_date = st.date_input("Select a date", date.today() - timedelta(days=1))
    
    st.divider()
    
    num_columns = 3 # 完美匹配 3 个超级核心
    domain_keys = list(YOUR_DOMAINS_OF_INTEREST.keys())
    cols = st.columns(num_columns)
    
    # (V17.1) 修改：直接遍历 3 个核心并分配到 3 列
    for i, domain_key in enumerate(domain_keys):
        with cols[i]:
            domain_config = YOUR_DOMAINS_OF_INTEREST[domain_key]
            domain_name = domain_config["name_zh"] if lang == "简体中文" else domain_config["name_en"]
            st.subheader(domain_name, divider="rainbow")
            
            file_path = os.path.join(ARCHIVE_DIR, domain_key, f"{selected_date.isoformat()}.json")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # (V17) 关键修改：读取论文列表
                    picks_list = json.load(f) 
                
                if picks_list and isinstance(picks_list, list):
                    
                    # (V17) 关键修改：循环渲染列表中的每一篇论文
                    for j, pick in enumerate(picks_list):
                        if not isinstance(pick, dict): continue 
                        
                        st.markdown(f"**{j+1}. [{pick.get('title', 'No Title')}]({pick.get('url', '#')})**")
                        authors_label = "作者" if lang == "简体中文" else "Authors"
                        st.caption(f"**{authors_label}:** {pick.get('authors', 'N/A')}")
                        
                        # (V17) 新增：显示 AI 评分表
                        scores = pick.get('scores')
                        if scores and isinstance(scores, dict):
                            score_expander_label = "AI 评分卡 (1-5分)" if lang == "简体中文" else "AI Scorecard (1-5)"
                            with st.expander(score_expander_label, expanded=False):
                                score_cols = st.columns(4)
                                score_cols[0].metric(label="创新性 (Novelty)", value=scores.get('Novelty', 'N/A'))
                                score_cols[1].metric(label="严谨性 (Rigor)", value=scores.get('Rigor', 'N/A'))
                                score_cols[2].metric(label="影响力 (Impact)", value=scores.get('Impact', 'N/A'))
                                score_cols[3].metric(label="清晰度 (Clarity)", value=scores.get('Clarity', 'N/A'))

                        # AI 推荐理由
                        if lang == "简体中文":
                            reason, reason_label = pick.get('reason_zh', 'N/A'), "AI 编辑推荐理由"
                        else:
                            reason, reason_label = pick.get('reason_en', 'N/A'), "AI Editor's Justification"
                        st.info(f"**🤖 {reason_label}:** {reason}")
                        
                        # 摘要
                        expander_label = "查看摘要" if lang == "简体中文" else "View Abstract"
                        with st.expander(expander_label):
                            st.write(pick.get('summary', 'N/A'))
                        
                        pdf_label = "下载 PDF ➔" if lang == "简体中文" else "Download PDF ➔"
                        st.link_button(pdf_label, pick.get('pdf_url', '#'))
                        
                        if j < len(picks_list) - 1:
                            st.divider()

                else:
                    no_pick_text = "今日 AI 编辑未发现值得一读的论文。" if lang == "简体中文" else "The AI Editor found no 'must-reads' today."
                    st.write(no_pick_text)
                    
            except FileNotFoundError:
                st.write("尚无数据。" if lang == "简体中文" else "No data yet.")
            except json.JSONDecodeError:
                st.error("JSON 文件损坏或格式错误。")

# --------------------------------------------------------------------------
# (V17) 每周教程标签页 (保持 V12/V16 的逻辑不变)
# (它已经支持列表渲染，所以无需修改)
# --------------------------------------------------------------------------
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
            picks_data = json.load(f)

        # (V12 修复) 检查数据类型，确保 picks_list 始终是列表
        picks_list = None
        if isinstance(picks_data, list):
            picks_list = picks_data
        elif isinstance(picks_data, dict):
            picks_list = [picks_data] # 将旧的单个对象包装成列表

        if picks_list:
            for i, pick in enumerate(picks_list):
                if isinstance(pick, dict):
                    st.markdown(f"**{i+1}. [{pick.get('title', 'No Title')}]({pick.get('url', '#')})**")
                    
                    authors_label = "作者" if lang == "简体中文" else "Authors"
                    st.caption(f"**{authors_label}:** {pick.get('authors', 'N/A')}")
                    
                    # (V16/V17 兼容) 教程理由
                    if lang == "简体中文":
                        core_value = pick.get('core_value_zh', None) 
                        reason, reason_label = pick.get('reason_zh', 'N/A'), "AI 编辑推荐理由"
                    else:
                        core_value = pick.get('core_value_en', None)
                        reason, reason_label = pick.get('reason_en', 'N/A'), "AI Editor's Justification"
                    
                    if core_value: 
                        st.success(f"**💡核心价值（AI一句话总结）：** {core_value}")

                    expander_title = reason_label + (" (点击展开)" if core_value else "") 
                    with st.expander(expander_title):
                        st.info(f"**🏆{reason_label}:** {reason}")
                    
                    expander_label = "查看摘要" if lang == "简体中文" else "View Abstract"
                    with st.expander(expander_label):
                        st.write(pick.get('summary', 'No summary available.'))
                    pdf_label = "下载 PDF ➔" if lang == "简体中文" else "Download PDF ➔"
                    st.link_button(pdf_label, pick.get('pdf_url', '#'))
                    
                    if i < len(picks_list) - 1: 
                        st.divider()
                else:
                    st.error("数据格式错误：pick 不是一个字典。")
        else:
            no_pick_text = "本周 AI 编辑未发现值得一读的教程。" if lang == "简体中文" else "The AI Editor found no 'must-read' tutorials this week."
            st.write(no_pick_text)
    except FileNotFoundError:
        st.write("尚无本周数据。" if lang == "简体中文" else "No data yet for this week.")
    except json.JSONDecodeError:
        st.error("无法解析 JSON 文件，文件可能已损坏。")

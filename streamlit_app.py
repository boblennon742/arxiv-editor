import streamlit as st
import json
import os
from datetime import date, timedelta

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
    st.title("私人 AI 总编辑")
    st.caption("由 AI 每日为我评分精选的研究论文")
else:
    st.title("Personal AI Editor")
    st.caption("Daily 'Must-Read' papers, scored and curated by AI.")

# --- 3. 标签页设计 ---
tab_daily, tab_weekly = st.tabs([
    "每日精选" if lang == "简体中文" else "Daily Picks",
    "每周教程" if lang == "简体中文" else "Weekly Tutorials"
])

# --------------------------------------------------------------------------
# (V18) 每周教程标签页 —— 自动扫描所有历史周 + AI 评分卡
# --------------------------------------------------------------------------
with tab_weekly:
    tutorial_dir = os.path.join(ARCHIVE_DIR, "tutorials")
    
    # 自动获取所有已存在的周文件
    if os.path.exists(tutorial_dir):
        all_files = os.listdir(tutorial_dir)
        week_files = []
        import re
        for f in all_files:
            match = re.match(r"(\d{4}-W\d{2})\.json", f)
            if match:
                week_files.append(match.group(1))
        
        # 按年-周倒序排序（最新在前）
        week_files.sort(
            reverse=True,
            key=lambda x: (int(x.split('-')[0]), int(x.split('-W')[1]))
        )
    else:
        week_files = []

    if not week_files:
        st.warning(
            "尚未生成任何每周教程数据，请先运行抓取脚本。" 
            if lang == "简体中文" 
            else "No weekly tutorial data generated yet. Please run the fetching script first."
        )
        st.stop()

    # 计算当前周，用于标注“本周”“上周”
    today = date.today()
    current_year, current_week, _ = today.isocalendar()

    # 生成下拉选项和映射
    display_options = []
    week_mapping = {}  # display_text -> week_str
    
    for week_str in week_files:
        year = int(week_str.split('-')[0])
        week_num = int(week_str.split('-W')[1])
        
        if year == current_year and week_num == current_week:
            label = f"{week_str} (本周)" if lang == "简体中文" else f"{week_str} (This Week)"
        elif year == current_year and week_num == current_week - 1:
            label = f"{week_str} (上周)" if lang == "简体中文" else f"{week_str} (Last Week)"
        else:
            label = week_str
        
        display_options.append(label)
        week_mapping[label] = week_str

    # 周选择器
    selected_display = st.selectbox(
        "选择周" if lang == "简体中文" else "Select week",
        options=display_options,
        index=0  # 默认选中最新的周
    )
    
    selected_week_str = week_mapping[selected_display]

    st.divider()
    st.header(TUTORIAL_DOMAIN["tutorials"], divider="rainbow")

    file_path = os.path.join(tutorial_dir, f"{selected_week_str}.json")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            picks_data = json.load(f)
        
        # 兼容旧数据格式
        picks_list = picks_data if isinstance(picks_data, list) else \
                     [picks_data] if isinstance(picks_data, dict) else []
        
        if picks_list:
            for i, pick in enumerate(picks_list):
                if not isinstance(pick, dict):
                    continue
                
                st.markdown(f"**{i+1}. [{pick.get('title', 'No Title')}]({pick.get('url', '#')})**")
                authors_label = "作者" if lang == "简体中文" else "Authors"
                st.caption(f"**{authors_label}:** {pick.get('authors', 'N/A')}")
                
                # ---------- 核心价值 ----------
                if lang == "简体中文":
                    core_value = pick.get('core_value_zh')
                    reason = pick.get('reason_zh', 'N/A')
                    reason_label = "AI 编辑推荐理由"
                else:
                    core_value = pick.get('core_value_en')
                    reason = pick.get('reason_en', 'N/A')
                    reason_label = "AI Editor's Justification"
                
                if core_value:
                    st.success(f"**核心价值（AI一句话总结）：** {core_value}")
                
                # ---------- AI 评分卡 ----------
                scores = pick.get('scores')
                if scores and isinstance(scores, dict):
                    score_expander_label = "AI 评分卡 (1-5分)" if lang == "简体中文" else "AI Scorecard (1-5)"
                    with st.expander(score_expander_label, expanded=False):
                        score_cols = st.columns(4)
                        score_cols[0].metric("创新性 (Novelty)", scores.get('Novelty', 'N/A'))
                        score_cols[1].metric("严谨性 (Rigor)", scores.get('Rigor', 'N/A'))
                        score_cols[2].metric("影响力 (Impact)", scores.get('Impact', 'N/A'))
                        score_cols[3].metric("清晰度 (Clarity)", scores.get('Clarity', 'N/A'))
                
                # ---------- 推荐理由 ----------
                expander_title = reason_label + (" (点击展开)" if core_value else "")
                with st.expander(expander_title):
                    st.info(f"**{reason_label}:** {reason}")
                
                # ---------- 摘要 ----------
                expander_label = "查看摘要" if lang == "简体中文" else "View Abstract"
                with st.expander(expander_label):
                    st.write(pick.get('summary', 'No summary available.'))
                
                # ---------- PDF 下载 ----------
                pdf_label = "下载 PDF" if lang == "简体中文" else "Download PDF"
                pdf_url = pick.get('pdf_url', '#')
                if pdf_url and pdf_url != '#':
                    st.markdown(
                        f'<a href="{pdf_url}" target="_blank" '
                        f'style="color: #1f77b4; text-decoration: none; font-weight: bold;">'
                        f'{pdf_label}</a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(f"*{pdf_label}*")
                
                if i < len(picks_list) - 1:
                    st.divider()
        else:
            no_pick_text = "本周 AI 编辑未发现值得一读的教程。" if lang == "简体中文" else "The AI Editor found no 'must-read' tutorials this week."
            st.write(no_pick_text)
    
    except FileNotFoundError:
        st.write("所选周暂无数据。" if lang == "简体中文" else "No data for the selected week.")
    except json.JSONDecodeError:
        st.error("无法解析 JSON 文件，文件可能已损坏。")

# -*- coding: utf-8 -*-
"""
🏭 產業AI分析頁面 - 選擇產業族群進行分析
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import urllib.parse

# 設定頁面配置
st.set_page_config(
    page_title="產業AI分析 | Alpha-Refinery",
    layout="wide",
    page_icon="🏭"
)

# 添加自訂CSS
st.markdown("""
    <style>
    .sector-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .sector-header {
        background: linear-gradient(135deg, #2196F3 0%, #21CBF3 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .ai-section { background-color: #fff3cd; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; }
    </style>
""", unsafe_allow_html=True)

# ========== 導入共享功能 ==========
# 添加父目錄到路徑，讓 Python 能找到 utils 包
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # 專案根目錄

# 將專案根目錄添加到路徑
sys.path.insert(0, parent_dir)

try:
    # 從 utils 包導入
    from utils import (
        init_connections, 
        fetch_today_data, 
        call_ai_safely
    )
except ImportError as e:
    st.error(f"導入共享功能失敗: {e}")
    st.error(f"當前工作目錄: {os.getcwd()}")
    st.error(f"Python 路徑: {sys.path}")
    st.error(f"目錄內容: {os.listdir(parent_dir)}")
    st.stop()

# 初始化連線
supabase, gemini_model = init_connections()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 密碼保護機制 ==========
if 'gemini_authorized' not in st.session_state:
    st.session_state.gemini_authorized = False

# ========== 頁面標題 ==========
st.markdown("""
    <div class="sector-header">
        <h1 style="margin: 0;">🏭 產業AI分析</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">選擇今日漲停產業，進行趨勢分析</p>
    </div>
""", unsafe_allow_html=True)

# 檢查連線
if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查設定")
    st.stop()

# ========== 載入今日漲停股票數據 ==========
df_limit_ups = fetch_today_data("individual_stock_analysis", today)

if df_limit_ups.empty:
    st.info("📊 今日尚未有漲停股票數據，請稍後再試。")
    st.stop()

# ========== 計算產業分佈 ==========
if 'sector' not in df_limit_ups.columns:
    st.error("❌ 數據中缺少產業欄位")
    st.stop()

df_limit_ups['sector'] = df_limit_ups['sector'].fillna('未分類')
sector_counts = df_limit_ups['sector'].value_counts().reset_index()
sector_counts.columns = ['產業別', '漲停家數']

# 計算產業統計
sector_stats = {}
for sector in df_limit_ups['sector'].unique():
    sector_stocks = df_limit_ups[df_limit_ups['sector'] == sector]
    avg_seq = sector_stocks['consecutive_days'].mean() if 'consecutive_days' in sector_stocks.columns else 1
    sector_stats[sector] = {
        'count': len(sector_stocks),
        'avg_seq': round(avg_seq, 1),
        'stocks': sector_stocks[['symbol', 'stock_name', 'consecutive_days']].to_dict('records')
    }

# ========== 產業分析主體 ==========
st.divider()
st.subheader("📊 漲停產業別分析")

col1, col2 = st.columns([1.5, 1])

with col1:
    # ========== 產業分佈圖 ==========
    st.markdown("<div class='ai-section'>", unsafe_allow_html=True)
    st.subheader("🤖 產業AI分析")
    
    selected_sector = st.selectbox(
        "選擇產業進行AI分析：",
        options=sector_counts['產業別'].tolist(),
        key="sector_selector"
    )
    
    if selected_sector:
        # 自動生成該產業的AI提示詞
        sector_data = sector_stats[selected_sector]
        sector_stocks_list = df_limit_ups[df_limit_ups['sector'] == selected_sector]
        
        # 建立產業股票表格 - 不使用 to_markdown()
        sector_table_df = sector_stocks_list[['symbol', 'stock_name', 'consecutive_days']].copy()
        sector_table_df.columns = ['代碼', '股票名稱', '連板天數']
        
        # 將 DataFrame 轉換為 markdown 格式的字符串
        def df_to_markdown_table(df):
            """將 DataFrame 轉換為 markdown 表格字符串"""
            # 創建表頭
            headers = "| " + " | ".join(df.columns) + " |\n"
            # 創建分隔線
            separators = "| " + " | ".join(["---"] * len(df.columns)) + " |\n"
            # 創建數據行
            rows = ""
            for _, row in df.iterrows():
                rows += "| " + " | ".join(str(val) for val in row.values) + " |\n"
            return headers + separators + rows
        
        sector_table = df_to_markdown_table(sector_table_df)
        
        # 建立產業AI提示詞
        sector_prompt = f"""請擔任專業市場分析師，分析台灣股市的{selected_sector}產業：

## 產業概況
- **產業名稱**: {selected_sector}
- **今日漲停家數**: {sector_data['count']}家 (佔總漲停數 {round(sector_data['count']/len(df_limit_ups)*100, 1)}%)
- **平均連板天數**: {sector_data['avg_seq']}天

## 漲停個股詳情
{sector_table}

## 市場背景
- 分析日期: {today}
- 總漲停家數: {len(df_limit_ups)}家
- 市場代號: TW

## 分析問題
1. **產業熱度分析**:
   - 從漲停家數和連板天數來看，此產業目前處於什麼週期位置？
   - 是否有龍頭股帶動效應？（觀察連板天數最高的股票）

2. **資金流向解讀**:
   - 為什麼資金集中在此產業？可能的催化劑是什麼？
   - 此產業的漲停股票是否有共同特徵？（市值、成交額、技術形態等）

3. **風險評估**:
   - 此產業的連板效應是否過熱？回調風險有多高？
   - 歷史上類似產業集體漲停後，後續表現如何？

4. **投資建議**:
   - 對於已持有此產業股票的投資者，建議的操作策略？
   - 對於想追價的投資者，建議的進場時機和風險控制？
   
5. **產業聯動**:
   - 此產業的上游/下游是否有聯動效應？
   - 在當前市場環境下，此產業的持續性如何判斷？

請提供具體、可操作的投資建議。"""
        
        # 顯示提示詞和AI平台連結
        st.write(f"### 📋 {selected_sector} 產業分析提示詞")
        st.code(sector_prompt, language="text")
        
        # 一鍵帶入AI分析平台
        encoded_sector_prompt = urllib.parse.quote(sector_prompt)
        st.link_button(
            f"🔥 一鍵帶入 ChatGPT 分析 {selected_sector}",
            f"https://chatgpt.com/?q={encoded_sector_prompt}",
            use_container_width=True,
            help="自動在ChatGPT中打開此產業分析"
        )
        
        # 其他AI平台按鈕
        col_ai1, col_ai2, col_ai3 = st.columns(3)
        
        with col_ai1:
            st.link_button(
                "🔍 複製到 DeepSeek 分析",
                "https://chat.deepseek.com/",
                use_container_width=True,
                help="請複製上方提示詞貼到DeepSeek"
            )
        
        with col_ai2:
            st.link_button(
                "📘 複製到 Claude 分析",
                "https://claude.ai/",
                use_container_width=True,
                help="請複製上方提示詞貼到Claude"
            )
        
        with col_ai3:
            # Gemini內建診斷（密碼保護）
            if st.session_state.gemini_authorized:
                if st.button("🤖 Gemini 分析", use_container_width=True):
                    with st.spinner("Gemini正在分析中..."):
                        ai_response = call_ai_safely(sector_prompt, gemini_model)
                        if ai_response:
                            st.session_state.gemini_sector_report = ai_response
                            st.rerun()
            else:
                st.markdown('<div class="password-protected">', unsafe_allow_html=True)
                auth_pw = st.text_input("授權密碼：", type="password", key="sector_gemini_pw")
                if st.button("解鎖 Gemini", key="sector_gemini_auth"):
                    if auth_pw == st.secrets.get("AI_ASK_PASSWORD", "default_password"):
                        st.session_state.gemini_authorized = True
                        st.rerun()
                    else:
                        st.error("密碼錯誤")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # === Gemini 產業報告獨立顯示 ===
    if 'gemini_sector_report' in st.session_state:
        st.divider()
        with st.expander(f"🤖 Gemini 產業分析報告：{selected_sector}", expanded=True):
            ai_response = st.session_state.gemini_sector_report
            st.markdown(
                f"""
                <div style="
                    background-color: #f8f9fa !important;
                    padding: 30px !important;
                    border-radius: 15px !important;
                    border-left: 8px solid #28a745 !important;
                    box-shadow: 0 6px 20px rgba(0,0,0,0.12) !important;
                    line-height: 2 !important;
                    font-size: 17px !important;
                    white-space: pre-wrap !important;
                    word-wrap: break-word !important;
                    max-width: 100% !important;
                    width: 100% !important;
                    box-sizing: border-box !important;
                    margin: 10px 0 !important;
                ">
                {ai_response.replace('\n', '<br>')}
                </div>
                """,
                unsafe_allow_html=True
            )
            report_text = f"# {selected_sector} 產業AI分析報告\n\n日期：{today}\n\n{ai_response}"
            st.download_button(
                label="📥 下載分析報告 (.md)",
                data=report_text.encode('utf-8'),
                file_name=f"{selected_sector}_analysis_{today}.md",
                mime="text/markdown",
                use_container_width=True
            )
            if st.button("🗑️ 清除此報告", type="secondary"):
                del st.session_state.gemini_sector_report
                st.rerun()

with col2:
    st.subheader("📋 今日強勢清單")
    
    # 顯示簡化的股票列表
    display_df = df_limit_ups[['symbol', 'stock_name', 'sector', 'consecutive_days']].copy()
    display_df.columns = ['代碼', '股票名稱', '產業', '連板天數']
    
    st.dataframe(
        display_df.head(15),  # 只顯示前15檔
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # 快速統計
    st.markdown("---")
    total_stocks = len(df_limit_ups)
    if 'consecutive_days' in df_limit_ups.columns:
        avg_lu = df_limit_ups['consecutive_days'].mean()
        max_lu = df_limit_ups['consecutive_days'].max()
    else:
        avg_lu = 1
        max_lu = 1
    
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.metric("總漲停家數", f"{total_stocks}家")
    with col_stat2:
        st.metric("最高連板", f"{max_lu}天")

# ========== 市場整體AI分析 ==========
st.divider()
st.subheader("🌐 市場整體AI分析")

# 自動生成市場整體分析提示詞 - 修改 to_markdown() 的使用
def series_to_markdown_table(series, index_name='項目', value_name='數值'):
    """將 Series 轉換為 markdown 表格字符串"""
    df = series.reset_index()
    df.columns = [index_name, value_name]
    return df_to_markdown_table(df)

# 處理產業分佈
sector_distribution = df_to_markdown_table(sector_counts)

# 處理連板天數分佈
if 'consecutive_days' in df_limit_ups.columns:
    consecutive_series = df_limit_ups['consecutive_days'].value_counts().sort_index()
    # 將 Series 轉換為 DataFrame 再轉為 markdown
    consecutive_df = consecutive_series.reset_index()
    consecutive_df.columns = ['連板天數', '家數']
    consecutive_distribution = df_to_markdown_table(consecutive_df)
else:
    consecutive_distribution = "| 連板天數 | 家數 |\n| --- | --- |\n| N/A | N/A |"

market_summary = f"""
## 台灣股市 今日漲停整體分析

### 市場概況
- 分析日期: {today}
- 總漲停家數: {len(df_limit_ups)}家
- 平均連板天數: {avg_lu:.1f}天
- 最高連板: {max_lu}天

### 產業分佈
{sector_distribution}

### 連板天數分佈
{consecutive_distribution}

### 市場分析問題
1. **市場熱度評估**：從漲停家數看，當前市場處於什麼情緒週期？
2. **產業輪動分析**：哪些產業是今日主流？是否有持續性？
3. **連板效應**：連板股票的分佈顯示什麼市場結構？
4. **風險提示**：市場過熱跡象有哪些？回調風險多高？
5. **策略建議**：在當前市場環境下，最佳交易策略為何？

請提供專業的市場分析與投資建議。"""

with st.expander("📊 市場整體AI分析提示詞", expanded=False):
    st.code(market_summary, language="text")
    
    encoded_market = urllib.parse.quote(market_summary)
    st.link_button(
        "🌐 分析整體市場情緒 (ChatGPT)",
        f"https://chatgpt.com/?q={encoded_market}",
        use_container_width=True
    )

# ========== 側邊欄設定 ==========
with st.sidebar:
    st.header("⚙️ 設定")
    st.subheader("🔧 系統狀態")
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Supabase", "✅" if supabase else "❌")
    with status_col2:
        st.metric("Gemini", "✅" if gemini_model else "❌")
    with status_col3:
        st.metric("漲停股票", f"{len(df_limit_ups)}" if not df_limit_ups.empty else "0")
    
    st.divider()
    
    st.subheader("🔐 AI 授權設定")
    if not st.session_state.gemini_authorized:
        with st.expander("Gemini API 授權", expanded=True):
            password_input = st.text_input("授權密碼：", type="password", key="sidebar_pw")
            if st.button("🔓 授權解鎖", use_container_width=True):
                if password_input == st.secrets.get("AI_ASK_PASSWORD", "default_password"):
                    st.session_state.gemini_authorized = True
                    st.success("✅ 授權成功！")
                    st.rerun()
                else:
                    st.error("❌ 密碼錯誤")
            st.caption("💡 授權後在同次會話中有效，關閉瀏覽器後需重新授權")
    else:
        st.success("✅ Gemini API 已授權")
        if st.button("🔒 撤銷授權", type="secondary", use_container_width=True):
            st.session_state.gemini_authorized = False
            st.rerun()
    
    st.divider()
    
    st.subheader("🔗 快速連結")
    st.page_link("https://chatgpt.com/", label="ChatGPT", icon="🤖")
    st.page_link("https://chat.deepseek.com/", label="DeepSeek", icon="🔍")
    st.page_link("https://claude.ai/", label="Claude", icon="📘")
    
    st.divider()
    
    st.subheader("🛠️ 除錯與維護工具")
    if st.button("🔄 強制清除所有快取並重新載入"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("所有快取已清除！正在重新載入最新資料...")
        st.rerun()

# ========== 頁面底部 ==========
st.divider()
st.caption(f"產業AI分析頁面 | 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

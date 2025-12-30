# -*- coding: utf-8 -*-
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
import sys

# ========== 檢查必要套件 ==========
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly 套件未安裝，圖表功能將被禁用。請運行：pip install plotly")

# 設定頁面配置
st.set_page_config(page_title="Alpha-Refinery 漲停戰情室 2.0", layout="wide")

# 自訂CSS樣式
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .ai-section { background-color: #fff3cd; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; }
    .stock-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; margin: 8px 0; background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%); }
    .password-protected { border: 2px solid #ff6b6b; border-radius: 8px; padding: 15px; background-color: #fff5f5; }
    </style>
""", unsafe_allow_html=True)

# ========== 1. 初始化連線 ==========
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Supabase 連線失敗: {e}")
        return None

@st.cache_resource
def init_gemini():
    """自動偵測可用模型，解決 404 與 429 錯誤處理"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        candidates = ['models/gemini-1.5-flash', 'gemini-1.5-flash', 'models/gemini-1.5-pro']
        target_model = next((c for c in candidates if c in available_models), available_models[0] if available_models else 'gemini-pro')
        return genai.GenerativeModel(target_model)
    except Exception as e:
        st.error(f"AI 初始化失敗: {e}")
        return None

supabase = init_supabase()
gemini_model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# ========== 2. 輔助函式 ==========
@st.cache_data(ttl=600)
def fetch_today_data(table_name, date_str):
    try:
        res = supabase.table(table_name).select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入數據失敗: {e}")
        return pd.DataFrame()

# ========== 3. 數據載入 ==========
if supabase:
    df_limit_ups = fetch_today_data("individual_stock_analysis", today)
    summary_df = fetch_today_data("daily_market_summary", today)
else:
    df_limit_ups = pd.DataFrame()
    summary_df = pd.DataFrame()

# ========== 4. 側邊欄設定 ==========
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
    st.subheader("📊 分析選項")
    show_advanced = st.checkbox("顯示進階分析", value=True)
    show_history = st.checkbox("顯示歷史趨勢", value=True and PLOTLY_AVAILABLE)
    show_sector_analysis = st.checkbox("顯示產業分析", value=True and PLOTLY_AVAILABLE)

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

# ========== 5. 主介面呈現 ==========
st.title("🚀 Alpha-Refinery 漲停戰情室 2.0")
st.caption(f"📅 分析日期：{today} | 🕐 最後更新：{datetime.now().strftime('%H:%M:%S')}")

if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查 Supabase 設定")
    st.stop()

# --- 區塊一：今日大盤總結 ---
with st.expander("📊 今日大盤總結", expanded=True):
    if not summary_df.empty:
        summary_content = summary_df.iloc[0]['summary_content']
        st.info(summary_content)
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤總結記錄。")
        st.info("💡 系統將於掃描完成後自動生成總結，請稍後刷新或點擊側邊欄「清除快取」按鈕。")

# --- 區塊二：今日漲停板概覽 ---
st.divider()
st.header("🔥 今日漲停板概覽")

if not df_limit_ups.empty:
    # 顯示簡單的統計
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("總漲停家數", f"{len(df_limit_ups)}家")
    with col2:
        rotc_count = len(df_limit_ups[df_limit_ups['is_rotc'] == True])
        st.metric("興櫃漲停", f"{rotc_count}家")
    with col3:
        if 'consecutive_days' in df_limit_ups.columns:
            avg_days = df_limit_ups['consecutive_days'].mean()
            st.metric("平均連板", f"{avg_days:.1f}天")
        else:
            st.metric("平均連板", "N/A")
    with col4:
        if 'return_rate' in df_limit_ups.columns:
            avg_return = df_limit_ups['return_rate'].mean()
            st.metric("平均漲幅", f"{avg_return:.2%}")
        else:
            st.metric("平均漲幅", "N/A")

    # 顯示前10檔股票
    st.subheader("📈 漲停股票列表（前10檔）")
    display_df = df_limit_ups.head(10)[['stock_name', 'symbol', 'sector', 'return_rate', 'price']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業', '漲幅', '價格']
    display_df['漲幅'] = display_df['漲幅'].apply(lambda x: f"{x:.2%}" if x else "N/A")
    display_df['價格'] = display_df['價格'].apply(lambda x: f"{x:.2f}" if x else "N/A")
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    # 提供導航到其他頁面的按鈕
    st.divider()
    st.header("🎯 進階分析功能")
    col_adv1, col_adv2, col_adv3 = st.columns(3)
    with col_adv1:
        if st.button("📈 個股AI分析", use_container_width=True):
            st.switch_page("pages/1_個股AI分析.py")
    with col_adv2:
        if st.button("🏭 產業AI分析", use_container_width=True):
            st.switch_page("pages/2_產業AI分析.py")
    with col_adv3:
        if st.button("🌐 市場總覽AI分析", use_container_width=True):
            st.switch_page("pages/3_市場總覽AI分析.py")

else:
    st.info("📊 目前尚未偵測到今日強勢標的。")
    st.markdown("""
    ### 💡 可能原因：
    1. 今日市場無漲停股票
    2. 數據尚未更新
    3. 市場交易清淡

    ### 🔍 建議行動：
    - 檢查系統數據更新時間
    - 查看其他交易日的數據
    - 分析市場整體狀況
    """)

# ========== 6. 底部導覽列 ==========
st.divider()
st.markdown("### 🔗 快速資源與工具")
col_tool1, col_tool2, col_tool3, col_tool4 = st.columns(4)
with col_tool1:
    st.page_link("https://www.wantgoo.com/", label="玩股網", icon="📈")
with col_tool2:
    st.page_link("https://goodinfo.tw/", label="Goodinfo!", icon="📊")
with col_tool3:
    st.page_link("https://www.cnyes.com/", label="鉅亨網", icon="📰")
with col_tool4:
    st.page_link("https://tw.stock.yahoo.com/", label="Yahoo股市", icon="💹")
st.caption(f"Alpha-Refinery 漲停戰情室 2.0 | 版本：{datetime.now().strftime('%Y.%m.%d')} | 數據僅供參考，投資有風險")

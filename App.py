# -*- coding: utf-8 -*-
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from io import StringIO

# 設定頁面配置
st.set_page_config(page_title="Alpha-Refinery 漲停戰情室", layout="wide")

# ========== 1. 初始化連線 ==========
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 解決 404 問題：直接使用字串名稱，SDK 會自動處理
        # 如果還是 404，請確認你的 API Key 是否支援 1.5 系列
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"AI 啟動失敗: {e}")
        return None

supabase = init_supabase()
model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 2. 數據獲取函式 ==========

@st.cache_data(ttl=600)
def fetch_limit_ups(date_str):
    """從 Supabase 讀取今日漲停分析"""
    try:
        res = supabase.table("individual_stock_analysis").select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_all_stock_metadata():
    """
    獲取全市場股票與產業清單。
    如果你的 Supabase 還沒存這張表，這裏提供一個從 CSV 或 API 讀取的邏輯預留位。
    """
    try:
        # 假設你有一個 stock_metadata 資料表儲存全市場股票代號、名稱、產業
        res = supabase.table("stock_metadata").select("symbol, name, sector").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame(columns=['symbol', 'name', 'sector'])

# 載入數據
df_limit_ups = fetch_limit_ups(today)
df_all_metadata = fetch_all_stock_metadata()

# ========== 3. 介面呈現 ==========

st.title("🚀 Alpha-Refinery 漲停戰情室")

# --- 區塊一：大盤總結 ---
with st.container():
    st.header("📊 今日大盤 AI 總結")
    try:
        summary = supabase.table("daily_market_summary").select("*").eq("analysis_date", today).execute()
        if summary.data:
            st.info(summary.data[0]['summary_content'])
        else:
            st.warning(f"📅 尚未找到 {today} 的大盤分析記錄。")
    except:
        st.error("大盤總結數據讀取失敗")

# --- 區塊二：強勢股偵測 ---
st.divider()
st.header("🔥 今日強勢股偵測")

if not df_limit_ups.empty:
    # 顯示主表
    display_df = df_limit_ups[['stock_name', 'symbol', 'sector', 'ai_comment']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業別', 'AI 即時點評']
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # --- 區塊三：產業補漲挖掘機 ---
    st.subheader("📂 產業族群補漲研究")
    
    col_l, col_r = st.columns([1, 1])
    
    with col_l:
        # 1. 選擇一檔今日漲停股
        selected_stock_name = st.selectbox("1. 選擇今日漲停股：", df_limit_ups['stock_name'].tolist())
        stock_info = df_limit_ups[df_limit_ups['stock_name'] == selected_stock_name].iloc[0]
        target_sector = stock_info['sector']
        st.markdown(f"當前選擇：**{selected_stock_name}** | 所屬產業：**{target_sector}**")

    with col_r:
        # 2. 自動找出同產業但「還沒漲停」的股票
        if not df_all_metadata.empty:
            # 找出同產業所有股票
            peers = df_all_metadata[df_all_metadata['sector'] == target_sector]
            # 排除已漲停的股票
            limit_up_list = df_limit_ups['stock_name'].tolist()
            not_limit_up_peers = peers[~peers['name'].isin(limit_up_list)]
            
            st.write(f"2. {target_sector} 族群中「尚未漲停」的觀察名單：")
            st.dataframe(not_limit_up_peers[['symbol', 'name']], height=150, use_container_width=True)
            potential_names = ", ".join(not_limit_up_peers['name'].tolist())
        else:
            potential_names = "（資料庫中缺少 stock_metadata 表，無法自動比對）"
            st.info("💡 提示：請在 Supabase 建立 stock_metadata 表來解鎖自動比對功能。")

    # --- 區塊四：AI 策略按鈕 ---
    st.subheader("🧠 補漲潛力分析")
    
    # 建立強化的提示詞
    sector_prompt = f"""
    你是台股資深產業分析師。
    
    【今日市況】
    在「{target_sector}」產業中，今天已有「{selected_stock_name}」強勢漲停。
    
    【同族群觀察名單（尚未漲停）】
    {potential_names}
    
    【分析任務】
    1. 簡述「{selected_stock_name}」漲停可能的產業利多題材。
    2. 根據觀察名單，哪些個股與該漲停股的業務連動性最高？
    3. 若資金持續流入，哪幾檔最具備「補漲」潛力？請說明具體原因。
    """

    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"🤖 AI 分析 {target_sector} 補漲潛力", type="primary"):
            if model:
                try:
                    with st.spinner("AI 正在挖掘黑馬..."):
                        response = model.generate_content(sector_prompt)
                        st.markdown("### AI 分析報告")
                        st.write(response.text)
                except Exception as e:
                    st.error(f"API 呼叫失敗。錯誤代碼: {e}")
            else:
                st.error("AI 客戶端未啟動，請檢查 API Key 設定。")
                
    with c2:
        if st.button("📋 產生提示詞 (複製到 ChatGPT/Claude)"):
            st.text_area("請複製以下內容：", value=sector_prompt, height=300)

else:
    st.write("目前尚未偵測到今日強勢標的。")

st.divider()
st.caption(f"Alpha-Refinery | 最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

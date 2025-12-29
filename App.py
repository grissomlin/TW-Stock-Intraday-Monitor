# -*- coding: utf-8 -*-
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import google.generativeai as genai

# 設定頁面配置
st.set_page_config(page_title="Alpha-Refinery 漲停戰情室", layout="wide")

# ========== 1. 初始化連線 ==========
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    """自動偵測可用模型，解決 404 問題"""
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
model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 2. 輔助函式 ==========

def get_wantgoo_url(symbol):
    """將代碼 (例如 2330.TW 或 7763.TWO) 轉為玩股網 K 線連結"""
    code = symbol.split('.')[0]
    return f"https://www.wantgoo.com/stock/{code}/technical-chart"

@st.cache_data(ttl=600)
def fetch_today_data(table_name, date_str):
    try:
        res = supabase.table(table_name).select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_all_metadata():
    try:
        res = supabase.table("stock_metadata").select("symbol, name, sector").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

# 載入數據
df_limit_ups = fetch_today_data("individual_stock_analysis", today)
df_all_metadata = fetch_all_metadata()

# ========== 3. 介面呈現 ==========

st.title("🚀 Alpha-Refinery 漲停戰情室")

# --- 區塊一：大盤總結 ---
with st.expander("📊 今日大盤 AI 總結", expanded=True):
    summary_df = fetch_today_data("daily_market_summary", today)
    if not summary_df.empty:
        st.info(summary_df.iloc[0]['summary_content'])
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤分析記錄。")

# --- 區塊二：強勢股偵測 (新增超連結與總結按鈕) ---
st.divider()
st.header("🔥 今日強勢股偵測")

if not df_limit_ups.empty:
    # 建立 WantGoo 連結欄位
    df_limit_ups['K線圖'] = df_limit_ups['symbol'].apply(get_wantgoo_url)
    
    # 顯示主表，使用 LinkColumn 讓網址變點擊
    display_df = df_limit_ups[['stock_name', 'symbol', 'sector', 'K線圖', 'ai_comment']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業別', '玩股網連結', 'AI 即時點評']
    
    st.dataframe(
        display_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={"玩股網連結": st.column_config.LinkColumn("📈 K線圖", display_text="查看圖表")}
    )
    
    # 新增：強勢股「全部一次問」按鈕
    st.subheader("💡 強勢標的一鍵總結")
    all_limit_names = ", ".join(df_limit_ups['stock_name'].tolist())
    all_prompt = f"今日台股大漲漲停的強勢股包含：{all_limit_names}。請根據這些股票的產業分佈，分析今日市場主流資金在哪個板塊，並推測後市連動性。"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 AI 總結今日強勢族群", type="primary"):
            if model:
                with st.spinner("正在分析資金流向..."):
                    res = model.generate_content(all_prompt)
                    st.write(res.text)
    with c2:
        if st.button("📋 複製強勢股 Prompt"):
            st.text_area("複製 Prompt：", value=all_prompt, height=100)
    
    # --- 區塊三：產業補漲挖掘機 (新增觀察名單超連結) ---
    st.divider()
    st.subheader("📂 產業族群補漲研究")
    
    col_l, col_r = st.columns([1, 1.2])
    
    with col_l:
        selected_stock_name = st.selectbox("1. 選擇今日漲停股：", df_limit_ups['stock_name'].tolist())
        stock_info = df_limit_ups[df_limit_ups['stock_name'] == selected_stock_name].iloc[0]
        target_sector = stock_info['sector']
        st.markdown(f"當前選擇：**{selected_stock_name}** | 產業：**{target_sector}**")

    with col_r:
        if not df_all_metadata.empty:
            peers = df_all_metadata[df_all_metadata['sector'] == target_sector]
            current_limit_up_names = df_limit_ups['stock_name'].tolist()
            not_limit_up_peers = peers[~peers['name'].isin(current_limit_up_names)].copy()
            
            st.write(f"2. {target_sector} 族群中「尚未漲停」的觀察名單：")
            if not not_limit_up_peers.empty:
                # 加入連結
                not_limit_up_peers['K線圖'] = not_limit_up_peers['symbol'].apply(get_wantgoo_url)
                st.dataframe(
                    not_limit_up_peers[['symbol', 'name', 'K線圖']], 
                    height=200, 
                    use_container_width=True,
                    column_config={"K線圖": st.column_config.LinkColumn("📈 查看圖表", display_text="玩股網")}
                )
                potential_names = ", ".join(not_limit_up_peers['name'].tolist())
            else:
                st.write("該產業今日全數漲停。")
                potential_names = "無"
        else:
            potential_names = "（未匯入資料）"

    # --- 區塊四：補漲潛力 AI 分析 ---
    st.subheader("🧠 補漲潛力分析")
    sector_prompt = f"在「{target_sector}」產業中，{selected_stock_name} 已漲停。名單 {potential_names} 尚未漲停。請分析誰最有補漲潛力？"

    c3, c4 = st.columns(2)
    with c3:
        if st.button(f"🧬 分析 {target_sector} 補漲潛力"):
            if model:
                with st.spinner("AI 分析中..."):
                    response = model.generate_content(sector_prompt)
                    st.write(response.text)
    with c4:
        if st.button("📋 複製產業 Prompt"):
            st.text_area("複製 Prompt：", value=sector_prompt, height=100)

else:
    st.write("目前尚未偵測到今日強勢標的。")

st.caption(f"Alpha-Refinery | 最後更新：{datetime.now().strftime('%H:%M:%S')}")

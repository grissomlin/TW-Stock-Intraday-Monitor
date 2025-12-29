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
model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 2. 輔助函式 ==========

def get_wantgoo_url(symbol):
    """將代碼 (如 2330.TW 或 7763.TWO) 轉為玩股網 K 線連結"""
    code = str(symbol).split('.')[0]
    return f"https://www.wantgoo.com/stock/{code}/technical-chart"

def call_ai_safely(prompt):
    """安全呼叫 AI，處理額度耗盡 (429) 的情況"""
    if not model:
        st.error("AI 客戶端未啟動")
        return
    try:
        with st.spinner("AI 正在深度思考中..."):
            res = model.generate_content(prompt)
            st.markdown("### 🤖 AI 分析報告")
            st.write(res.text)
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "ResourceExhausted" in err_msg:
            st.error("⚠️ AI 額度已耗盡 (Rate Limit Reached)。\n\n由於您使用的是免費版 API，請稍候 1 分鐘再試，或直接點擊旁邊的「📋 複製 Prompt」按鈕手動貼至 ChatGPT / Claude 獲取答案。")
        else:
            st.error(f"❌ AI 呼叫失敗: {e}")

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

# --- 區塊二：強勢股偵測 ---
st.divider()
st.header("🔥 今日強勢股偵測")

if not df_limit_ups.empty:
    # 建立 WantGoo 連結欄位
    df_limit_ups['K線圖'] = df_limit_ups['symbol'].apply(get_wantgoo_url)
    
    # 顯示主表
    display_df = df_limit_ups[['stock_name', 'symbol', 'sector', 'K線圖', 'ai_comment']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業別', '📈 玩股網', 'AI 即時點評']
    
    st.dataframe(
        display_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={"📈 玩股網": st.column_config.LinkColumn("📈 查看圖表", display_text="點我觀看")}
    )
    
    # --- 強勢股一鍵分析雙按鈕 ---
    st.subheader("💡 強勢標的一鍵總結")
    all_limit_names = ", ".join([f"{n}({s})" for n, s in zip(df_limit_ups['股票名稱'], df_limit_ups['產業別'])])
    all_prompt = f"今日台股漲停的強勢股包含：{all_limit_names}。請分析今日市場資金主要集中在哪些族群？這些強勢股是否有共同利多題材？"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 AI 一鍵分析所有強勢股", type="primary"):
            call_ai_safely(all_prompt)
    with c2:
        if st.button("📋 複製強勢股 Prompt"):
            st.text_area("複製 Prompt 貼至其他 AI：", value=all_prompt, height=100)
    
    # --- 區塊三：產業補漲挖掘機 ---
    st.divider()
    st.subheader("📂 產業族群補漲研究")
    
    col_l, col_r = st.columns([1, 1.2])
    
    with col_l:
        selected_stock_name = st.selectbox("1. 選擇今日漲停股：", df_limit_ups['股票名稱'].tolist())
        # 根據選中的名稱找出對應的產業
        target_sector = df_limit_ups[df_limit_ups['股票名稱'] == selected_stock_name]['產業別'].values[0]
        st.markdown(f"當前選擇：**{selected_stock_name}** | 產業：**{target_sector}**")

    with col_r:
        if not df_all_metadata.empty:
            peers = df_all_metadata[df_all_metadata['sector'] == target_sector]
            current_limit_up_names = df_limit_ups['股票名稱'].tolist()
            not_limit_up_peers = peers[~peers['name'].isin(current_limit_up_names)].copy()
            
            st.write(f"2. {target_sector} 族群中「尚未漲停」的觀察名單：")
            if not not_limit_up_peers.empty:
                not_limit_up_peers['K線圖'] = not_limit_up_peers['symbol'].apply(get_wantgoo_url)
                st.dataframe(
                    not_limit_up_peers[['symbol', 'name', 'K線圖']], 
                    height=200, 
                    use_container_width=True,
                    column_config={"K線圖": st.column_config.LinkColumn("📈 查看圖表", display_text="玩股網")}
                )
                potential_names = ", ".join(not_limit_up_peers['name'].tolist())
            else:
                st.write("該產業今日全數漲停或無其他對應個股。")
                potential_names = "無"
        else:
            potential_names = "（未匯入 stock_metadata 資料）"

    # --- 區塊四：補漲分析雙按鈕 ---
    st.subheader(f"🧠 {target_sector} 補漲潛力分析")
    sector_prompt = f"在「{target_sector}」產業中，{selected_stock_name} 已漲停。其餘同業如 {potential_names} 尚未漲停。請根據產業面分析誰最有機會補漲？"

    c3, c4 = st.columns(2)
    with c3:
        if st.button(f"🧬 分析 {target_sector} 族群連動", type="primary"):
            call_ai_safely(sector_prompt)
    with c4:
        if st.button(f"📋 複製 {target_sector} Prompt"):
            st.text_area("複製 Prompt：", value=sector_prompt, height=100)

else:
    st.write("目前尚未偵測到今日強勢標的。")

st.caption(f"Alpha-Refinery | 最後更新：{datetime.now().strftime('%H:%M:%S')}")

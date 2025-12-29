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
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

supabase = init_supabase()
model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 2. 核心數據讀取 ==========
@st.cache_data(ttl=600)
def fetch_data(table_name):
    res = supabase.table(table_name).select("*").eq("analysis_date", today).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# 抓取漲停股與全市場清單 (假設全市場清單存在 'stock_metadata' 表中)
df_limit_ups = fetch_data("individual_stock_analysis")
# 如果你還沒把全市場清單存入 DB，可以先讀取本地 CSV 或透過 API 獲取
# df_all = fetch_data("stock_metadata") 

st.title("🚀 Alpha-Refinery 漲停戰情室")

# --- A. 今日大盤 AI 總結 ---
with st.expander("📊 今日大盤 AI 總結", expanded=True):
    try:
        summary_data = supabase.table("daily_market_summary").select("*").eq("analysis_date", today).execute()
        if summary_data.data:
            st.info(summary_data.data[0]['summary_content'])
        else:
            st.warning(f"📅 尚未找到 {today} 的大盤分析記錄。")
    except Exception as e:
        st.error(f"查詢總結失敗: {e}")

# --- B. 全市場強勢股分析 ---
st.header("🔥 今日強勢股偵測")
if not df_limit_ups.empty:
    # 顯示主表格
    display_df = df_limit_ups[['stock_name', 'symbol', 'sector', 'ai_comment']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業別', 'AI 即時點評']
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # 全市場分析按鈕
    st.subheader("💡 全市場板塊分析")
    names_str = ", ".join([f"{n}({s})" for n, s in zip(df_limit_ups['stock_name'], df_limit_ups['sector'])])
    all_prompt = f"今日台股漲停名單如下：{names_str}。請根據產業別分析今日資金流向，並指出哪些產業具有族群連動性？"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 詢問 Gemini (全市場)"):
            with st.spinner("分析中..."):
                st.write(model.generate_content(all_prompt).text)
    with c2:
        if st.button("📋 複製提示詞 (問其他 AI)"):
            st.code(all_prompt, language="markdown")

    # --- C. 產業深度研究區 (連動分析) ---
    st.divider()
    st.header("📂 產業族群連動研究")
    
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        # 下拉選單：從今日漲停股挑選
        selected_stock = st.selectbox("1️⃣ 選擇今日漲停股：", df_limit_ups['stock_name'].tolist())
        target_sector = df_limit_ups[df_limit_ups['stock_name'] == selected_stock]['sector'].values[0]
        st.write(f"該股所屬產業：**{target_sector}**")

    with col_r:
        # 這裡示範如何根據該產業找出「相關推薦」
        # 注意：你需要有全市場的清單才能過濾
        st.write(f"2️⃣ **{target_sector}** 族群今日觀察：")
        # 假設從 Supabase 抓取同產業的所有股票表現 (這裡僅為邏輯示意)
        # related_stocks = supabase.table("market_prices").select("*").eq("sector", target_sector)...
        st.write("> 💡 *此處可串接資料庫，列出同產業所有個股之今日漲跌幅，判斷是否為集團性噴發。*")

    # 產業專屬 Prompt
    sector_prompt = f"在台股中，{target_sector} 產業目前的發展趨勢為何？今日 {selected_stock} 漲停，請問該產業還有哪些上下游或同業標的值得關注？請分析其關聯性。"
    
    c3, c4 = st.columns(2)
    with c3:
        if st.button(f"🧬 分析 {target_sector} 產業鏈"):
            with st.spinner("AI 分析中..."):
                st.write(model.generate_content(sector_prompt).text)
    with c4:
        if st.button("📋 複製產業提示詞"):
            st.code(sector_prompt, language="markdown")

else:
    st.write("目前尚未偵測到強勢標的。")

# --- D. 頁尾 ---
st.caption(f"最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

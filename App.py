import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

# 初始化
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

st.title("🚀 Alpha-Refinery 漲停戰情室")

# --- 讀取大盤總結 ---
st.header("📊 今日大盤 AI 總結")
today = datetime.now().strftime("%Y-%m-%d")

try:
    summary_data = supabase.table("daily_market_summary").select("*").eq("analysis_date", today).execute()
    if summary_data.data:
        st.info(summary_data.data[0]['summary_content'])
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤分析記錄。")
except Exception as e:
    st.error(f"❌ 查詢總結表失敗：{e}")

# --- 讀取單股分析 ---
st.header("🔥 今日強勢股偵測")
try:
    stock_data = supabase.table("individual_stock_analysis").select("*").eq("analysis_date", today).execute()
    if stock_data.data:
        df = pd.DataFrame(stock_data.data)
        display_df = df[['stock_name', 'symbol', 'sector', 'ai_comment']]
        display_df.columns = ['股票名稱', '代碼', '產業別', 'AI 即時點評']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.write("目前尚未偵測到強勢標的。")
except Exception as e:
    st.error(f"❌ 查詢單股表失敗：{e}")

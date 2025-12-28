import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Alpha-Refinery 全球戰情室", layout="wide")

# 初始化 Supabase
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

st.title("🚀 Alpha-Refinery 漲停戰情室")

# 1. 顯示今日大盤總結
st.header("📊 今日大盤 AI 總結")
today = datetime.now().strftime("%Y-%m-%d")
summary_data = supabase.table("daily_market_summary").select("*").eq("analysis_date", today).execute()

if summary_data.data:
    st.info(summary_data.data[0]['summary_content'])
else:
    st.warning("📅 今日大盤分析尚未生成，請稍候。")

st.divider()

# 2. 顯示強勢股清單與單股分析
st.header("🔥 今日強勢股偵測")
stock_data = supabase.table("individual_stock_analysis").select("*").eq("analysis_date", today).execute()

if stock_data.data:
    df = pd.DataFrame(stock_data.data)
    # 格式化表格
    display_df = df[['stock_name', 'symbol', 'sector', 'ai_comment']]
    display_df.columns = ['股票名稱', '代碼', '產業別', 'AI 即時點評']
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.write("目前尚未偵測到強勢標的。")

st.sidebar.caption(f"數據最後更新: {today}")
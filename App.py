import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import google.generativeai as genai

# 設定頁面
st.set_page_config(page_title="Alpha-Refinery 漲停戰情室", layout="wide")

# ========== 1. 初始化連線 (加入錯誤處理) ==========
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 修正 NotFound 錯誤：嘗試使用完整路徑模型名稱
        # 建議優先使用 gemini-1.5-flash，因為它速度快且免費額度穩
        model = genai.GenerativeModel('models/gemini-1.5-flash') 
        return model
    except Exception as e:
        st.error(f"AI 模組啟動失敗: {e}")
        return None

supabase = init_supabase()
model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 2. 數據獲取與整合邏輯 ==========
# 這是你提到的：根據產業別找股票的功能
@st.cache_data(ttl=600)
def get_industry_peers(sector_name):
    """
    從資料庫中找出同產業的所有股票。
    這假設你有一張名為 stock_metadata 的表儲存全市場清單。
    """
    try:
        # 這裡需要根據你實際的資料表名稱修改
        res = supabase.table("stock_metadata").select("symbol, name, sector").eq("sector", sector_name).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# 獲取今日漲停數據
res_limit = supabase.table("individual_stock_analysis").select("*").eq("analysis_date", today).execute()
df_limit_ups = pd.DataFrame(res_limit.data) if res_limit.data else pd.DataFrame()

# ========== 3. 介面呈現 ==========
st.title("🚀 Alpha-Refinery 漲停戰情室")

# --- 區塊一：大盤總結 ---
with st.container():
    st.header("📊 今日大盤 AI 總結")
    summary = supabase.table("daily_market_summary").select("*").eq("analysis_date", today).execute()
    if summary.data:
        st.info(summary.data[0]['summary_content'])
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤分析記錄。")

# --- 區塊二：強勢股偵測與產業下拉 ---
st.divider()
st.header("🔥 今日強勢股偵測")

if not df_limit_ups.empty:
    # 顯示主表
    st.dataframe(df_limit_ups[['stock_name', 'symbol', 'sector', 'ai_comment']], use_container_width=True, hide_index=True)
    
    # --- 互動功能區 ---
    st.subheader("💡 產業連動分析器")
    
    col_select, col_peers = st.columns([1, 1])
    
    with col_select:
        # 下拉選單：選擇今日漲停股
        selected_stock = st.selectbox("1. 選擇漲停標的查看同族群：", df_limit_ups['stock_name'].tolist())
        stock_info = df_limit_ups[df_limit_ups['stock_name'] == selected_stock].iloc[0]
        target_sector = stock_info['sector']
        st.write(f"當前選擇：**{selected_stock}** | 產業：**{target_sector}**")
        
    with col_peers:
        # 顯示同產業個股 (需要有 stock_metadata 表)
        st.write(f"2. {target_sector} 族群其他標的：")
        peers_df = get_industry_peers(target_sector)
        if not peers_df.empty:
            st.dataframe(peers_df, height=150)
        else:
            st.caption("（請在資料庫中建立 stock_metadata 表以啟用此功能）")

    # --- 雙按鈕功能 (全市場與單一產業) ---
    st.subheader("🧠 AI 策略助手")
    
    # 產生 Prompt
    all_names = ", ".join(df_limit_ups['stock_name'].tolist())
    all_prompt = f"今日台股漲停股票包含：{all_names}。請根據這些標的的產業別（尤其是{target_sector}）分析資金流向與族群性。"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 執行 AI 深度分析", type="primary"):
            if model:
                try:
                    with st.spinner("AI 分析中..."):
                        response = model.generate_content(all_prompt)
                        st.markdown(f"### AI 分析結果\n{response.text}")
                except Exception as e:
                    st.error(f"API 呼叫失敗: {e}")
            else:
                st.error("AI 客戶端未正確初始化")
                
    with c2:
        if st.button("📋 產生提示詞 (手動複製)"):
            st.text_area("請複製下方文字至 ChatGPT / Claude：", value=all_prompt, height=150)

else:
    st.write("目前尚未偵測到強勢標的。")

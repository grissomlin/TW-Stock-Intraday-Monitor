# -*- coding: utf-8 -*-
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import google.generativeai as genai
import random

# 設定頁面配置
st.set_page_config(page_title="Alpha-Refinery 漲停戰情室", layout="wide")

# ========== 1. 初始化連線 ==========
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    """自動偵測可用模型，徹底解決 404 問題"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 列出所有支援生成內容的模型
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 優先級：1.5-flash > 1.5-pro > 任何可用模型
        target_model = None
        for m_name in ['models/gemini-1.5-flash', 'gemini-1.5-flash', 'models/gemini-1.5-pro']:
            if m_name in available_models:
                target_model = m_name
                break
        
        if not target_model:
            target_model = available_models[0] if available_models else 'gemini-pro'
            
        return genai.GenerativeModel(target_model)
    except Exception as e:
        st.error(f"AI 初始化失敗: {e}")
        return None

supabase = init_supabase()
model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 2. 數據獲取 ==========

@st.cache_data(ttl=600)
def fetch_data(table_name, date_str=None):
    query = supabase.table(table_name).select("*")
    if date_str:
        query = query.eq("analysis_date", date_str)
    res = query.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# 載入今日數據
df_limit_ups = fetch_data("individual_stock_analysis", today)
# 載入全市場清單 (確保您已執行過上傳 stock_metadata 的腳本)
df_all_metadata = fetch_data("stock_metadata")

# ========== 3. 介面呈現 ==========

st.title("🚀 Alpha-Refinery 漲停戰情室")

# --- 區塊一：大盤總結 ---
with st.expander("📊 今日大盤 AI 總結", expanded=True):
    summary_df = fetch_data("daily_market_summary", today)
    if not summary_df.empty:
        st.info(summary_df.iloc[0]['summary_content'])
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤分析記錄。")

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
        selected_stock = st.selectbox("1. 選擇今日漲停股：", df_limit_ups['stock_name'].tolist())
        stock_info = df_limit_ups[df_limit_ups['stock_name'] == selected_stock].iloc[0]
        target_sector = stock_info['sector']
        st.markdown(f"當前選擇：**{selected_stock}** | 所屬產業：**{target_sector}**")

    with col_r:
        if not df_all_metadata.empty:
            # 找出同產業所有股票
            peers = df_all_metadata[df_all_metadata['sector'] == target_sector]
            # 排除已漲停的股票名單
            limit_up_names = df_limit_ups['stock_name'].tolist()
            not_limit_up_peers = peers[~peers['name'].isin(limit_up_list)] if 'name' in peers.columns else pd.DataFrame()
            
            st.write(f"2. {target_sector} 族群中「尚未漲停」的觀察名單：")
            if not not_limit_up_peers.empty:
                st.dataframe(not_limit_up_peers[['symbol', 'name']], height=150, use_container_width=True)
                potential_names = ", ".join(not_limit_up_peers['name'].tolist())
            else:
                st.write("該產業今日集體漲停或無其他對應個股。")
                potential_names = "無"
        else:
            potential_names = "（缺少全市場資料）"
            st.info("💡 提示：請執行上傳 stock_metadata 的腳本以啟用自動比對。")

    # --- 區塊四：AI 策略分析 ---
    st.subheader("🧠 補漲潛力深度分析")
    
    sector_prompt = f"""
    你是台股資深產業分析師。
    
    【今日市況】
    在「{target_sector}」產業中，今天「{selected_stock}」已強勢漲停。
    
    【觀察名單（同產業尚未漲停個股）】
    {potential_names}
    
    【分析任務】
    1. 簡述「{selected_stock}」今日漲停的產業利多。
    2. 在觀察名單中，哪些個股與漲停股的業務連動性最高？
    3. 若資金持續輪動，哪幾檔最具備「補漲」潛力？請說明理由。
    """

    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"🤖 AI 分析 {target_sector} 補漲黑馬", type="primary"):
            if model:
                try:
                    with st.spinner("AI 正在比對族群連動性..."):
                        response = model.generate_content(sector_prompt)
                        st.markdown("### AI 分析報告")
                        st.write(response.text)
                except Exception as e:
                    st.error(f"API 呼叫失敗: {e}")
            else:
                st.error("AI 模組未啟動，請檢查 API Key。")
                
    with c2:
        if st.button("📋 產生提示詞 (複製至其他 AI)"):
            st.text_area("複製以下 Prompt：", value=sector_prompt, height=250)

else:
    st.write("目前尚未偵測到今日強勢標的。")

st.divider()
st.caption(f"Alpha-Refinery | 最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

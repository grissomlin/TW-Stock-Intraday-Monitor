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
    """自動偵測可用模型，徹底解決 404 問題"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 列出所有支援生成內容的模型名稱
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 優先順序邏輯
        target_model = None
        # 檢查常見的模型路徑格式
        candidates = [
            'models/gemini-1.5-flash', 
            'gemini-1.5-flash', 
            'models/gemini-1.5-pro',
            'models/gemini-pro'
        ]
        
        for cand in candidates:
            if cand in available_models:
                target_model = cand
                break
        
        if not target_model:
            # 如果都沒中，就拿第一個可用的
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
def fetch_today_data(table_name, date_str):
    try:
        res = supabase.table(table_name).select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_all_metadata():
    try:
        res = supabase.table("stock_metadata").select("symbol, name, sector").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# 載入今日數據
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
    # 顯示主表
    display_df = df_limit_ups[['stock_name', 'symbol', 'sector', 'ai_comment']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業別', 'AI 即時點評']
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # --- 區塊三：產業補漲挖掘機 ---
    st.subheader("📂 產業族群補漲研究")
    
    col_l, col_r = st.columns([1, 1])
    
    # 取得當前選擇的產業資訊
    with col_l:
        selected_stock_name = st.selectbox("1. 選擇今日漲停股：", df_limit_ups['stock_name'].tolist())
        stock_info = df_limit_ups[df_limit_ups['stock_name'] == selected_stock_name].iloc[0]
        target_sector = stock_info['sector']
        st.markdown(f"當前選擇：**{selected_stock_name}** | 所屬產業：**{target_sector}**")

    # 找出補漲觀察名單
    with col_r:
        if not df_all_metadata.empty:
            # 1. 找出同產業所有股票
            peers = df_all_metadata[df_all_metadata['sector'] == target_sector]
            # 2. 修正後的排除邏輯：排除掉「今日已漲停」的股票名單
            current_limit_up_names = df_limit_ups['stock_name'].tolist()
            # 確保欄位名稱正確 (symbol, name, sector)
            not_limit_up_peers = peers[~peers['name'].isin(current_limit_up_names)]
            
            st.write(f"2. {target_sector} 族群中「尚未漲停」的觀察名單：")
            if not not_limit_up_peers.empty:
                st.dataframe(not_limit_up_peers[['symbol', 'name']], height=150, use_container_width=True)
                potential_names = ", ".join(not_limit_up_peers['name'].tolist())
            else:
                st.write("該產業今日標的稀少或全數漲停。")
                potential_names = "無"
        else:
            potential_names = "（尚未匯入全市場資料）"
            st.info("💡 提示：請先完成 stock_metadata 的匯入以解鎖比對功能。")

    # --- 區塊四：AI 策略分析 ---
    st.subheader("🧠 補漲潛力深度分析")
    
    sector_prompt = f"""
    你是台股資深產業分析師。
    
    【今日市況】
    在「{target_sector}」產業中，今天「{selected_stock_name}」已強勢漲停。
    
    【觀察名單（同產業尚未漲停個股）】
    {potential_names}
    
    【分析任務】
    1. 簡述「{selected_stock_name}」今日漲停可能的推動因素。
    2. 在觀察名單中，哪些個股與該股業務關聯最緊密？
    3. 若資金持續流入，哪幾檔最具有補漲潛力？請說明具體原因。
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
                st.error("AI 模組未正確啟動，請檢查 Secrets 設定。")
                
    with c2:
        if st.button("📋 產生提示詞 (手動貼至 ChatGPT/Claude)"):
            st.text_area("複製以下 Prompt：", value=sector_prompt, height=250)

else:
    st.write("目前尚未偵測到今日強勢標的。")

st.divider()
st.caption(f"Alpha-Refinery | 最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

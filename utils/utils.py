# utils/utils.py
import streamlit as st
from supabase import create_client
import google.generativeai as genai
import pandas as pd
from datetime import datetime, timedelta

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

def init_connections():
    """初始化並返回資料庫和AI模型連線"""
    return init_supabase(), init_gemini()

@st.cache_data(ttl=600)
def fetch_today_data(supabase_client, table_name, date_str):
    try:
        res = supabase_client.table(table_name).select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入數據失敗: {e}")
        return pd.DataFrame()

def get_wantgoo_url(symbol):
    code = str(symbol).split('.')[0]
    return f"https://www.wantgoo.com/stock/{code}/technical-chart"

def get_goodinfo_url(symbol):
    code = str(symbol).split('.')[0]
    return f"https://goodinfo.tw/tw/StockBZPerformance.asp?STOCK_ID={code}"

def get_cnyes_url(symbol):
    code = str(symbol).split('.')[0]
    return f"https://www.cnyes.com/twstock/{code}/"

def get_stock_links(symbol):
    """返回所有相關連結的字典"""
    code = str(symbol).split('.')[0]
    return {
        "wantgoo": get_wantgoo_url(symbol),
        "goodinfo": get_goodinfo_url(symbol),
        "cnyes": get_cnyes_url(symbol),
        "yahoo": f"https://tw.stock.yahoo.com/quote/{code}.TW"
    }

def call_ai_safely(prompt, gemini_model):
    """安全地調用 AI API"""
    if not gemini_model:
        st.error("AI 客戶端未啟動")
        return None

    try:
        with st.spinner("🤖 AI 正在深度思考中..."):
            res = gemini_model.generate_content(prompt)
            return res.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "ResourceExhausted" in err_msg:
            st.error("⚠️ AI 額度已耗盡。請稍候 1 分鐘再試，或複製 Prompt 手動貼至 ChatGPT。")
        else:
            st.error(f"❌ AI 呼叫失敗: {e}")
        return None

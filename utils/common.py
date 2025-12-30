# -*- coding: utf-8 -*-
"""
共享功能模組
"""
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai

@st.cache_resource
def init_supabase():
    """初始化 Supabase 連線"""
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
    """初始化所有連線"""
    supabase = init_supabase()
    gemini_model = init_gemini()
    return supabase, gemini_model

@st.cache_data(ttl=600)
def fetch_today_data(table_name, date_str):
    """獲取今日數據"""
    try:
        res = supabase.table(table_name).select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入數據失敗: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_all_metadata():
    """獲取所有股票元數據"""
    try:
        res = supabase.table("stock_metadata").select("symbol, name, sector").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入元數據失敗: {e}")
        return pd.DataFrame()

def get_stock_links(symbol):
    """獲取股票相關連結"""
    code = str(symbol).split('.')[0]  # 取小數點左邊的字串
    
    return {
        '玩股網': f"https://www.wantgoo.com/stock/{code}/technical-chart",
        'Goodinfo': f"https://goodinfo.tw/tw/StockBZPerformance.asp?STOCK_ID={code}",
        '鉅亨網': f"https://www.cnyes.com/twstock/{code}/",
        'Yahoo股市': f"https://tw.stock.yahoo.com/quote/{code}.TW",
        '財報狗': f"https://statementdog.com/analysis/{code}/"
    }

def call_ai_safely(prompt, gemini_model):
    """安全呼叫 AI API"""
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

def create_individual_stock_prompt(stock_info):
    """創建個股分析提示詞"""
    code = stock_info['symbol'].split('.')[0]
    wantgoo_url = f"https://www.wantgoo.com/stock/{code}/technical-chart"
    
    prompt = f"""
    請以台灣股市專業分析師的身份，深度分析以下漲停板股票：

    ## 股票基本資訊
    - 股票名稱：{stock_info.get('stock_name', 'N/A')}
    - 股票代碼：{stock_info.get('symbol', 'N/A')}
    - 所屬產業：{stock_info.get('sector', '未分類')}
    - 當前價格：${stock_info.get('price', 'N/A')}
    - 今日漲幅：{stock_info.get('return_rate', 0):.2% if stock_info.get('return_rate') else 'N/A'}
    - 連續漲停天數：{stock_info.get('consecutive_days', 1)}天
    - 技術分析圖：{wantgoo_url}

    ## 請分析以下面向：

    ### 1. 技術面分析
    - 漲停板強度評估
    - 量價關係是否健康
    - K線型態與位置
    - 關鍵壓力與支撐位

    ### 2. 基本面考量
    - 所屬產業前景
    - 公司競爭優勢
    - 估值合理性分析

    ### 3. 籌碼面分析
    - 大戶與散戶動向
    - 法人買賣超情況
    - 融資融券變化

    ### 4. 風險評估
    - 短期過熱風險
    - 市場系統性風險
    - 流動性風險

    ### 5. 操作建議（請分不同風險偏好）
    - 保守型投資者：
    - 積極型投資者：
    - 短線交易者：

    ### 6. 後續觀察重點
    - 明日關鍵價位
    - 成交量變化監控
    - 相關產業新聞

    請以條列式重點摘要開始，然後詳細分析。
    分析請務實客觀，避免過度樂觀。
    """
    
    return prompt

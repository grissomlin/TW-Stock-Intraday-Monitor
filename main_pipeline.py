# -*- coding: utf-8 -*-
import os, io, requests, time, random
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from io import StringIO
from supabase import create_client
import google.generativeai as genai 
from tqdm import tqdm

# 強制載入當前目錄下的 .env
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

# ========== 1. 初始化設定 ==========
# 從環境變數讀取 (GitHub Secrets / Streamlit Secrets / .env)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 建立 Supabase 連線
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("❌ 警告: 找不到 Supabase URL 或 Key，資料庫功能將失效。")

def get_ai_model_client():
    """初始化 AI 客戶端並回傳模型實例"""
    if not GEMINI_API_KEY:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 失敗: 找不到 GEMINI_API_KEY。")
        return None, None
    
    # 遮罩顯示 Key 用於調試 (只顯示前 4 碼與後 4 碼)
    masked_key = f"{GEMINI_API_KEY[:4]}****{GEMINI_API_KEY[-4:]}"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔑 已讀取 API Key: {masked_key}")

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 獲取可用模型清單
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 優先選擇 flash 模型 (速度快、免費額度高)
        candidates = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.5-pro']
        target_model_name = next((c for c in candidates if c in all_models), all_models[0] if all_models else None)
        
        if target_model_name:
            model = genai.GenerativeModel(target_model_name)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ AI 啟動成功! 使用模型: {target_model_name}")
            return model, target_model_name
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 找不到支援的模型。")
        return None, None
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ AI 初始化異常: {str(e)}")
        return None, None

# 執行初始化
ai_client, active_model_name = get_ai_model_client()

def log(msg: str):
    tqdm.write(f"{datetime.now().strftime('%H:%M:%S')}: {msg}")

# ========== 2. 獲取全市場股票清單 ==========
def get_comprehensive_stock_list():
    url_configs = [
        {'name': '上市', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=1&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': '上櫃', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?market=2&issuetype=4&Page=1&chklike=Y', 'suffix': '.TWO'},
        {'name': '興櫃', 'is_rotc': True, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=E&issuetype=R&industry_code=&Page=1&chklike=Y', 'suffix': '.TWO'},
    ]
    all_stocks = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for cfg in url_configs:
        try:
            resp = requests.get(cfg['url'], timeout=20, headers=headers)
            resp.encoding = 'big5'
            dfs = pd.read_html(StringIO(resp.text), header=0)
            if not dfs: continue
            df = dfs[0]
            for _, row in df.iterrows():
                code = str(row.get('有價證券代號', '')).strip()
                name = str(row.get('有價證券名稱', '')).strip()
                sector = str(row.get('產業別', '其他')).strip()
                if 4 <= len(code) <= 6 and not any(x in name for x in ["購", "售", "牛", "熊"]):
                    all_stocks.append({
                        'symbol': f"{code}{cfg['suffix']}", 
                        'name': name, 
                        'sector': sector, 
                        'is_rotc': cfg['is_rotc']
                    })
        except Exception as e:
            log(f"⚠️ 讀取 {cfg['name']} 失敗: {e}")
            continue
    return pd.DataFrame(all_stocks).drop_duplicates(subset=['symbol'])

# ========== 3. AI 分析邏輯 ==========
def ai_single_stock_analysis(stock_name, symbol, sector):
    if not ai_client: 
        return "AI Client 未啟動"
    
    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        # 1. 檢查快取
        existing = supabase.table("individual_stock_analysis") \
            .select("ai_comment") \
            .eq("analysis_date", today_str) \
            .eq("symbol", symbol) \
            .execute()

        if existing.data and len(existing.data) > 0:
            cached_comment = existing.data[0]['ai_comment']
            if "額度已達上限" not in cached_comment:
                return cached_comment

        # 2. 呼叫 Gemini
        prompt = f"你是台股專家。請用30字內簡述「{stock_name}({symbol})」今日大漲可能原因。產業：{sector}。"
        response = ai_client.generate_content(prompt)
        ai_msg = response.text.strip()
        
        # 3. 儲存結果
        supabase.table("individual_stock_analysis").upsert({
            "analysis_date": today_str,
            "symbol": symbol,
            "stock_name": stock_name,
            "sector": sector,
            "ai_comment": ai_msg
        }, on_conflict="analysis_date,symbol").execute()
        
        return ai_msg

    except Exception as e:
        if "429" in str(e):
            return "API 限流中"
        return f"分析失敗: {str(e)[:20]}"

# ========== 4. 股價偵測 ==========
def process_single_stock(stock):
    symbol = stock['symbol']
    try:
        df = yf.download(symbol, period="2d", progress=False, threads=False, timeout=10)
        if df.empty or len(df) < 2: return None
        
        # 處理 yfinance 可能的多層索引
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        last_close = float(df['Close'].iloc[-2])
        curr_close = float(df['Close'].iloc[-1])
        curr_high = float(df['High'].iloc[-1])
        ret_vs_prev = (curr_close / last_close) - 1

        # 判定規則：興櫃無漲跌幅限制(設為10%)，上市櫃以9.8%為門檻
        is_strong = (stock['is_rotc'] and ret_vs_prev >= 0.1) or \
                    (not stock['is_rotc'] and ret_vs_prev >= 0.098)

        if is_strong:
            ai_comment = ai_single_stock_analysis(stock['name'], symbol, stock['sector'])
            return {**stock, 'pct': f"{ret_vs_prev:.2%}", 'ai_comment': ai_comment}
            
    except: return None
    return None

# ========== 5. 主程式 ==========
def run_monitor():
    start_ts = time.time()
    
    # 再次確認 AI 狀態
    if not ai_client:
        log("❌ 注意：AI 模組未啟動，將僅進行數據掃描。")
    
    stocks_df = get_comprehensive_stock_list()
    stocks_list = stocks_df.to_dict('records')
    
    limit_ups = []
    log(f"🚀 開始全市場掃描 ({len(stocks_list)} 檔)...")

    # 使用 tqdm 顯示進度條
    for s in tqdm(stocks_list, desc="掃描進度"):
        res = process_single_stock(s)
        if res:
            limit_ups.append(res)
            log(f"🔥 強勢股: {res['name']} | 漲幅: {res['pct']} | AI: {res['ai_comment']}")
        
        # 稍微延遲避免被 Yahoo 封鎖 IP
        time.sleep(0.05)

    log(f"🏁 任務結束。共發現 {len(limit_ups)} 檔強勢股。耗時: {(time.time() - start_ts)/60:.1f} 分鐘")

if __name__ == "__main__":
    run_monitor()

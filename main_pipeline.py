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
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_ai_model_client():
    if not GEMINI_API_KEY:
        return None, None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        candidates = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash']
        target_model_name = next((c for c in candidates if c in all_models), all_models[0] if all_models else None)
        
        if target_model_name:
            model = genai.GenerativeModel(target_model_name)
            return model, target_model_name
        return None, None
    except Exception as e:
        print(f"AI 初始化失敗: {e}")
        return None, None

ai_client, active_model_name = get_ai_model_client()

def log(msg: str):
    tqdm.write(f"{datetime.now().strftime('%H:%M:%S')}: {msg}")

# ========== 2. 獲取全市場股票清單 ==========
def get_comprehensive_stock_list():
    url_configs = [
        {'name': 'listed', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=1&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'dr', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=J&industry_code=&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'otc', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?market=2&issuetype=4&Page=1&chklike=Y', 'suffix': '.TWO'},
        {'name': 'etf', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=I&industry_code=&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'rotc', 'is_rotc': True, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=E&issuetype=R&industry_code=&Page=1&chklike=Y', 'suffix': '.TWO'},
        {'name': 'tw_innovation', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=C&issuetype=C&industry_code=&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'otc_innovation', 'is_rotc': False, 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=A&issuetype=C&industry_code=&Page=1&chklike=Y', 'suffix': '.TWO'},
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

# ========== 3. AI 即時點評 (拿掉重試/等待) ==========
def ai_single_stock_analysis(stock_name, symbol, sector):
    if not ai_client: return "AI Client 未啟動"
    
    prompt = f"你是台股分析師。請簡述「{stock_name} ({symbol})」今日大漲/漲停的可能原因。產業別：{sector}。請用50字內回答。"
    
    try:
        response = ai_client.generate_content(prompt)
        ai_msg = response.text.strip()
        
        # 寫入 Supabase
        supabase.table("individual_stock_analysis").upsert({
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "symbol": symbol,
            "stock_name": stock_name,
            "sector": sector,
            "ai_comment": ai_msg
        }, on_conflict="analysis_date,symbol").execute()
        
        return ai_msg
    except Exception as e:
        if "429" in str(e):
            log(f"🚫 {stock_name} 遇限流 (429)，直接跳過 AI 分析。")
            return "API 額度已達上限，暫無分析"
        else:
            log(f"⚠️ {stock_name} 分析失敗: {e}")
            return "暫無 AI 分析"

# ========== 4. 單一標的下載與判定 ==========
def process_single_stock(stock):
    symbol = stock['symbol']
    try:
        df = yf.download(symbol, period="5d", progress=False, threads=False, timeout=12, auto_adjust=True)
        if df.empty or len(df) < 2: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        last_close = float(df['Close'].iloc[-2])
        curr_close = float(df['Close'].iloc[-1])
        curr_high = float(df['High'].iloc[-1])
        ret_vs_prev = (curr_close / last_close) - 1
        
        is_strong = (stock['is_rotc'] and ret_vs_prev >= 0.098) or \
                    (not stock['is_rotc'] and 0.098 <= ret_vs_prev <= 0.11 and (curr_high / last_close) >= 1.098)

        if is_strong:
            # 偵測到強勢股，呼叫 AI (若遇限流會自動跳過)
            ai_comment = ai_single_stock_analysis(stock['name'], symbol, stock['sector'])
            return {**stock, 'pct': f"{ret_vs_prev:.2%}", 'ai_comment': ai_comment}
            
    except: return None
    return None

# ========== 5. 主流程 ==========
def run_monitor():
    start_ts = time.time()
    if active_model_name:
        log(f"🤖 已啟動 AI 診斷模型: {active_model_name}")
    
    stocks_df = get_comprehensive_stock_list()
    stocks_list = stocks_df.to_dict('records')
    
    limit_ups = []
    log(f"🚀 開始掃描 (總計 {len(stocks_list)} 檔)...")

    for s in tqdm(stocks_list, desc="偵測進度"):
        res = process_single_stock(s)
        if res:
            limit_ups.append(res)
            log(f"🔥 強勢股: {res['name']} | 漲幅: {res['pct']} | AI: {res['ai_comment']}")
        
        # 為了避免 yfinance 下載太快被擋，微小休息
        time.sleep(0.01)

    if limit_ups and ai_client:
        log(f"📊 正在生成大盤分析報告...")
        all_info = [f"{x['name']}({x['sector']})" for x in limit_ups]
        summary_prompt = f"今日台股強勢股：{', '.join(all_info)}。請分析今日資金流向。200字內。"
        
        try:
            summary_res = ai_client.generate_content(summary_prompt)
            supabase.table("daily_market_summary").upsert({
                "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                "stock_count": len(limit_ups),
                "summary_content": summary_res.text.strip(),
                "stock_list": ", ".join([x['name'] for x in limit_ups])
            }, on_conflict="analysis_date").execute()
            log("✅ 大盤總結完成")
        except Exception as e:
            log(f"❌ 總結 AI 失敗: {e}")

    log(f"🏁 任務結束。總耗時: {(time.time() - start_ts)/60:.1f} 分鐘")

if __name__ == "__main__":
    run_monitor()
# -*- coding: utf-8 -*-
import os, requests, time, random
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from io import StringIO
from supabase import create_client
import google.generativeai as genai 
from tqdm import tqdm

load_dotenv()

# ========== 1. 核心參數設定 ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 初始化 Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def log(msg: str):
    tqdm.write(f"{datetime.now().strftime('%H:%M:%S')}: {msg}")

# ========== 2. 功能模組 ==========

def send_telegram_msg(message):
    """發送訊息到 Telegram (支援不同 Repo 指定不同的 Chat ID)"""
    if not TG_TOKEN or not TG_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log(f"Telegram 發送失敗: {e}")

def ai_analysis_with_retry(stock_name, symbol, sector):
    """具備自動重試與快取機制的 AI 分析 (解決 429 限流問題)"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # [快取檢查]
    try:
        existing = supabase.table("individual_stock_analysis") \
            .select("ai_comment").eq("analysis_date", today_str).eq("symbol", symbol).execute()
        if existing.data: return existing.data[0]['ai_comment']
    except: pass

    # [AI 請求 + 自動重試邏輯]
    prompt = f"你是台股專家。請用30字內簡述「{stock_name}({symbol})」今日大漲可能原因。產業：{sector}。"
    
    for attempt in range(3): # 最多嘗試 3 次
        try:
            response = model.generate_content(prompt)
            ai_msg = response.text.strip()
            
            # 儲存到 Supabase 方便之後快速讀取
            if supabase:
                supabase.table("individual_stock_analysis").upsert({
                    "analysis_date": today_str, "symbol": symbol,
                    "stock_name": stock_name, "sector": sector, "ai_comment": ai_msg
                }).execute()
            return ai_msg
        except Exception as e:
            if "429" in str(e): # 如果被限流
                wait = (attempt + 1) * 15 + random.randint(1, 5) # 遞增等待時間
                log(f"⚠️ {symbol} 遭限流，等待 {wait} 秒後進行第 {attempt+1} 次重試...")
                time.sleep(wait)
            else:
                return f"分析異常: {str(e)[:15]}"
    return "API 頻繁限流，已放棄本次請求"

def get_comprehensive_stock_list():
    """獲取台股全市場清單 (上市/上櫃/興櫃)"""
    configs = [
        {'n': '上市', 'm': '1', 't': '1', 's': '.TW'},
        {'n': '上櫃', 'm': '2', 't': '4', 's': '.TWO'},
        {'n': '興櫃', 'm': 'E', 't': 'R', 's': '.TWO'}
    ]
    all_data = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for c in configs:
        url = f"https://isin.twse.com.tw/isin/class_main.jsp?market={c['m']}&issuetype={c['t']}&Page=1&chklike=Y"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = 'big5'
            df = pd.read_html(StringIO(r.text), header=0)[0]
            for _, row in df.iterrows():
                code = str(row['有價證券代號']).strip()
                name = str(row['有價證券名稱']).strip()
                if 4 <= len(code) <= 6:
                    all_data.append({
                        'symbol': code + c['s'], 
                        'name': name, 
                        'sector': row['產業別'], 
                        'is_rotc': (c['m'] == 'E')
                    })
        except: continue
    return pd.DataFrame(all_data).drop_duplicates(subset=['symbol']).to_dict('records')

# ========== 3. 主執行邏輯 ==========

def run_monitor():
    log("🚀 啟動智能台股監控系統...")
    stocks = get_comprehensive_stock_list()
    
    send_telegram_msg(f"🔔 *台股強勢股掃描啟動*\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n標的總數: {len(stocks)}")

    found_count = 0
    for s in tqdm(stocks, desc="掃描全市場"):
        try:
            # 下載股價
            df = yf.download(s['symbol'], period="2d", progress=False)
            if df.empty or len(df) < 2: continue
            
            # 確保取得 Close 價格
            close_data = df['Close']
            curr_close = float(close_data.iloc[-1])
            prev_close = float(close_data.iloc[-2])
            ret = (curr_close / prev_close) - 1
            
            # 漲幅門檻判定
            threshold = 0.1 if s['is_rotc'] else 0.098
            if ret >= threshold:
                ai_comment = ai_analysis_with_retry(s['name'], s['symbol'], s['sector'])
                
                # 組合成 Telegram 訊息
                msg = f"🔥 *強勢股: {s['name']}* ({s['symbol']})\n"
                msg += f"📈 漲幅: {ret:.2%}\n"
                msg += f"🤖 AI 分析: {ai_comment}"
                
                send_telegram_msg(msg)
                log(f"✅ 已推播: {s['name']} ({ret:.2%})")
                found_count += 1
                
            time.sleep(0.1) # 避開 Yahoo IP 封鎖
        except Exception as e:
            continue

    msg_end = f"🏁 *掃描任務結束*\n共發現 {found_count} 檔強勢股。"
    send_telegram_msg(msg_end)
    log(msg_end)

if __name__ == "__main__":
    run_monitor()

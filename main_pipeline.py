# -*- coding: utf-8 -*-
import os, requests, time, random
from datetime import datetime, timedelta
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

def ai_analysis_with_retry(stock_name, symbol, sector, return_rate):
    """具備自動重試與快取機制的 AI 分析"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # [快取檢查] - 使用漲停板資料表
    try:
        existing = supabase.table("limit_up_stocks") \
            .select("ai_comment").eq("analysis_date", today_str).eq("symbol", symbol).execute()
        if existing.data: return existing.data[0]['ai_comment']
    except: pass
    
    # [AI 請求 + 自動重試邏輯]
    prompt = f"你是台股專家。請用30字內簡述「{stock_name}({symbol})」今日大漲可能原因。產業：{sector}，漲幅：{return_rate:.2%}。"
    
    for attempt in range(3): # 最多嘗試 3 次
        try:
            response = model.generate_content(prompt)
            ai_msg = response.text.strip()
            
            # 儲存到漲停板專用資料表
            if supabase:
                supabase.table("limit_up_stocks").upsert({
                    "analysis_date": today_str, 
                    "symbol": symbol,
                    "stock_name": stock_name, 
                    "sector": sector, 
                    "ai_comment": ai_msg,
                    "return_rate": return_rate,
                    "price": 0,  # 可以從 yfinance 補充
                    "volume": 0  # 可以從 yfinance 補充
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
    """獲取台股全市場清單 (上市/上櫃/興櫃) - 單次獲取"""
    configs = [
        {'n': '上市', 'm': '1', 't': '1', 's': '.TW'},
        {'n': '上櫃', 'm': '2', 't': '4', 's': '.TWO'},
        {'n': '興櫃', 'm': 'E', 't': 'R', 's': '.TWO'}
    ]
    all_data = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    log("📋 開始獲取股票清單...")
    for c in configs:
        log(f"  正在獲取 {c['n']} 股票清單...")
        url = f"https://isin.twse.com.tw/isin/class_main.jsp?market={c['m']}&issuetype={c['t']}&Page=1&chklike=Y"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = 'big5'
            df = pd.read_html(StringIO(r.text), header=0)[0]
            
            count = 0
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
                    count += 1
            
            log(f"  ✅ 已獲取 {c['n']} {count} 檔股票")
            time.sleep(1)  # 避免請求過快
        except Exception as e:
            log(f"  ❌ 獲取 {c['n']} 股票清單失敗: {str(e)[:50]}")
            continue
    
    # 轉換為 DataFrame 並去重
    df_all = pd.DataFrame(all_data).drop_duplicates(subset=['symbol'])
    log(f"📊 總共獲取 {len(df_all)} 檔股票")
    
    return df_all.to_dict('records')

def update_stock_metadata(stocks):
    """更新股票基本資料到資料庫"""
    if not supabase:
        return False
    
    try:
        log("💾 更新股票基本資料...")
        
        for i, stock in enumerate(stocks):
            supabase.table("stock_metadata").upsert({
                "symbol": stock['symbol'],
                "name": stock['name'],
                "sector": stock['sector'],
                "is_rotc": stock['is_rotc'],
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }).execute()
            
            # 每100檔顯示一次進度
            if (i+1) % 100 == 0:
                log(f"  已更新 {i+1}/{len(stocks)} 檔股票基本資料")
        
        log(f"✅ 完成更新 {len(stocks)} 檔股票基本資料")
        return True
    except Exception as e:
        log(f"❌ 更新股票基本資料失敗: {e}")
        return False

def save_daily_summary(limit_up_stocks, total_scanned):
    """儲存每日市場總結"""
    if not supabase:
        return False
    
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 統計產業分佈
        sector_counts = {}
        for stock in limit_up_stocks:
            sector = stock['sector']
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        
        # 生成總結內容
        summary_content = f"今日掃描 {total_scanned} 檔股票，發現 {len(limit_up_stocks)} 檔漲停板股票。\n\n"
        summary_content += "產業分佈：\n"
        for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
            summary_content += f"- {sector}: {count}檔\n"
        
        # 漲幅排名
        if limit_up_stocks:
            summary_content += f"\n漲幅排名：\n"
            sorted_stocks = sorted(limit_up_stocks, key=lambda x: x['return'], reverse=True)
            for i, stock in enumerate(sorted_stocks[:10], 1):
                summary_content += f"{i}. {stock['name']}({stock['symbol']}): {stock['return']:.2%}\n"
        
        # 儲存到資料庫
        supabase.table("daily_market_summary").upsert({
            "analysis_date": today_str,
            "total_scanned": total_scanned,
            "limit_up_count": len(limit_up_stocks),
            "summary_content": summary_content,
            "sector_distribution": str(sector_counts),
            "created_at": datetime.now().isoformat()
        }).execute()
        
        log(f"✅ 已儲存今日市場總結: {len(limit_up_stocks)} 檔漲停")
        return True
    except Exception as e:
        log(f"❌ 儲存市場總結失敗: {e}")
        return False

def get_stock_price_data(symbol):
    """安全地獲取股票價格數據"""
    try:
        # 使用較短的歷史數據
        df = yf.download(symbol, period="2d", progress=False, timeout=10)
        
        if df.empty or len(df) < 2:
            return None, None
        
        # 獲取收盤價
        if 'Close' in df.columns:
            close_data = df['Close']
            if len(close_data) >= 2:
                curr_close = float(close_data.iloc[-1])
                prev_close = float(close_data.iloc[-2])
                
                # 計算漲跌幅
                if prev_close > 0:  # 避免除以零
                    ret = (curr_close / prev_close) - 1
                    return ret, curr_close
        return None, None
    except Exception as e:
        log(f"  ⚠️ 獲取 {symbol} 價格失敗: {str(e)[:30]}")
        return None, None

# ========== 3. 主執行邏輯 ==========

def run_monitor():
    log("🚀 啟動智能台股監控系統 (單執行緒版)...")
    log(f"📅 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 獲取股票清單
    stocks = get_comprehensive_stock_list()
    
    if not stocks:
        log("❌ 無法獲取股票清單，程序終止")
        return
    
    # 更新股票基本資料
    update_stock_metadata(stocks)
    
    # 發送開始通知
    send_telegram_msg(f"🔔 *台股強勢股掃描啟動*\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n標的總數: {len(stocks)}")
    
    found_count = 0
    limit_up_stocks = []
    error_count = 0
    
    # 單執行緒掃描
    for idx, s in enumerate(tqdm(stocks, desc="掃描全市場"), 1):
        try:
            # 顯示進度
            if idx % 100 == 0:
                log(f"📈 已掃描 {idx}/{len(stocks)}，發現 {found_count} 檔漲停")
            
            # 獲取股價數據
            ret, curr_price = get_stock_price_data(s['symbol'])
            
            if ret is None:
                error_count += 1
                continue
            
            # 漲幅門檻判定
            threshold = 0.1 if s['is_rotc'] else 0.098
            if ret >= threshold:
                # AI 分析
                ai_comment = ai_analysis_with_retry(s['name'], s['symbol'], s['sector'], ret)
                
                # 記錄漲停股票
                limit_up_stocks.append({
                    'symbol': s['symbol'],
                    'name': s['name'],
                    'sector': s['sector'],
                    'return': ret,
                    'price': curr_price,
                    'ai_comment': ai_comment
                })
                
                # 發送 Telegram 通知
                msg = f"🔥 *強勢股: {s['name']}* ({s['symbol']})\n"
                msg += f"📈 漲幅: {ret:.2%}\n"
                msg += f"💵 價格: {curr_price:.2f}\n"
                msg += f"🤖 AI 分析: {ai_comment}"
                
                send_telegram_msg(msg)
                log(f"✅ 已推播: {s['name']} ({ret:.2%})")
                found_count += 1
            
            # 控制請求速度 (避免被封鎖)
            delay = random.uniform(0.08, 0.15)  # 隨機延遲
            time.sleep(delay)
            
        except Exception as e:
            error_count += 1
            # 只記錄錯誤，不中斷程式
            if error_count % 50 == 0:  # 每50個錯誤顯示一次
                log(f"⚠️ 已累積 {error_count} 個錯誤，最新錯誤: {str(e)[:50]}")
            continue
    
    # 儲存每日總結
    save_daily_summary(limit_up_stocks, len(stocks))
    
    # 發送結束通知
    msg_end = f"🏁 *掃描任務結束*\n"
    msg_end += f"✅ 總掃描: {len(stocks)} 檔\n"
    msg_end += f"✅ 發現漲停: {found_count} 檔\n"
    msg_end += f"⚠️ 錯誤數量: {error_count} 個\n"
    
    # 列出今日漲停板股票
    if limit_up_stocks:
        msg_end += f"\n📊 今日漲停板 ({len(limit_up_stocks)}檔):\n"
        sorted_stocks = sorted(limit_up_stocks, key=lambda x: x['return'], reverse=True)
        for i, stock in enumerate(sorted_stocks[:10], 1):
            msg_end += f"{i}. {stock['name']}({stock['symbol']}): {stock['return']:.2%}\n"
    
    send_telegram_msg(msg_end)
    log(msg_end)
    
    # 生成統計報告
    log("\n" + "="*50)
    log("📊 掃描統計報告")
    log(f"總股票數: {len(stocks)}")
    log(f"成功掃描: {len(stocks) - error_count}")
    log(f"錯誤數量: {error_count}")
    log(f"漲停板數: {found_count}")
    log("="*50)

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        log("\n⚠️ 程式被使用者中斷")
    except Exception as e:
        log(f"❌ 程式執行錯誤: {e}")
        send_telegram_msg(f"❌ *程式執行錯誤*\n錯誤訊息: {str(e)[:100]}")

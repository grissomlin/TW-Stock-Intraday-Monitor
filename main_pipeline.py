# -*- coding: utf-8 -*-
import os, sys, requests, time, random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from io import StringIO
from supabase import create_client
from google.genai import Client
import warnings

# 忽略警告訊息
warnings.filterwarnings('ignore')

load_dotenv()

# ========== 1. 核心參數設定 ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 初始化 Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 初始化 Gemini (使用新套件)
genai_client = Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ========== 2. 日誌設定 ==========
def log(msg: str, level="INFO"):
    """自定義日誌函數，確保在 CI 環境中也能輸出"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_msg = f"{timestamp}: [{level}] {msg}"
    
    # 強制刷新輸出緩衝區
    print(formatted_msg, flush=True)

def log_progress(current, total, found):
    """顯示進度條（在 CI 環境中也能正常顯示）"""
    progress = (current / total) * 100
    bar_length = 30
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    log(f"進度: |{bar}| {progress:.1f}% ({current}/{total}), 發現漲停: {found}", "PROGRESS")

# ========== 3. 功能模組 ==========

def send_telegram_msg(message):
    """發送訊息到 Telegram"""
    if not TG_TOKEN or not TG_CHAT_ID: 
        return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log(f"Telegram 發送失敗: {response.status_code}", "ERROR")
    except Exception as e:
        log(f"Telegram 發送錯誤: {e}", "ERROR")

def ai_analysis_with_retry(stock_name, symbol, sector, return_rate):
    """AI 分析股票"""
    if not genai_client:
        return "AI 服務未初始化"
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 快取檢查
    try:
        existing = supabase.table("individual_stock_analysis") \
            .select("ai_comment") \
            .eq("analysis_date", today_str) \
            .eq("symbol", symbol) \
            .execute()
        
        if existing.data: 
            return existing.data[0]['ai_comment']
    except Exception as e:
        log(f"快取檢查失敗: {e}", "WARNING")
    
    # AI 分析
    prompt = f"你是台股專家。請用30字內簡述「{stock_name}({symbol})」今日大漲可能原因。產業：{sector}，漲幅：{return_rate:.2%}。"
    
    for attempt in range(3):  # 最多嘗試 3 次
        try:
            response = genai_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            ai_msg = response.text.strip()
            
            # 儲存到資料庫
            if supabase:
                supabase.table("individual_stock_analysis").upsert({
                    "analysis_date": today_str,
                    "symbol": symbol,
                    "stock_name": stock_name,
                    "sector": sector,
                    "ai_comment": ai_msg
                }).execute()
            
            return ai_msg
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "resource exhausted" in error_msg.lower():
                wait = (attempt + 1) * 15 + random.randint(1, 5)
                log(f"{symbol} 遭限流，等待 {wait} 秒...", "WARNING")
                time.sleep(wait)
            else:
                log(f"AI 分析錯誤: {error_msg[:50]}", "WARNING")
                return f"分析異常: {error_msg[:20]}"
    
    return "API 頻繁限流，已放棄"

def get_comprehensive_stock_list():
    """獲取台股全市場清單"""
    configs = [
        {'n': '上市', 'm': '1', 't': '1', 's': '.TW'},
        {'n': '上櫃', 'm': '2', 't': '4', 's': '.TWO'},
        {'n': '興櫃', 'm': 'E', 't': 'R', 's': '.TWO'}
    ]
    
    all_data = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    log("開始獲取股票清單...")
    
    for c in configs:
        log(f"正在獲取 {c['n']} 股票清單...")
        url = f"https://isin.twse.com.tw/isin/class_main.jsp?market={c['m']}&issuetype={c['t']}&Page=1&chklike=Y"
        
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.encoding = 'big5'
            
            # 讀取表格數據
            df_list = pd.read_html(StringIO(r.text), header=0)
            if len(df_list) == 0:
                continue
                
            df = df_list[0]
            count = 0
            
            for _, row in df.iterrows():
                code = str(row['有價證券代號']).strip()
                name = str(row['有價證券名稱']).strip()
                
                if 4 <= len(code) <= 6:
                    all_data.append({
                        'symbol': code + c['s'], 
                        'name': name, 
                        'sector': row['產業別'] if '產業別' in row else '其他', 
                        'is_rotc': (c['m'] == 'E')  # 興櫃股票
                    })
                    count += 1
            
            log(f"已獲取 {c['n']} {count} 檔股票", "SUCCESS")
            time.sleep(1)  # 避免請求過快
            
        except Exception as e:
            log(f"獲取 {c['n']} 股票清單失敗: {str(e)[:50]}", "ERROR")
            continue
    
    # 轉換為 DataFrame 並去重
    if all_data:
        df_all = pd.DataFrame(all_data).drop_duplicates(subset=['symbol'])
        log(f"總共獲取 {len(df_all)} 檔股票", "SUCCESS")
        return df_all.to_dict('records')
    else:
        log("無法獲取任何股票資料", "ERROR")
        return []

def update_stock_metadata_simple(stocks):
    """簡化的股票基本資料更新"""
    if not supabase or not stocks:
        return False
    
    try:
        log("更新股票基本資料...")
        
        success_count = 0
        fail_count = 0
        
        # 先檢查表格是否存在
        try:
            test = supabase.table("stock_metadata").select("symbol").limit(1).execute()
        except:
            log("stock_metadata 表格不存在，跳過更新", "WARNING")
            return False
        
        for i, stock in enumerate(stocks):
            try:
                # 只更新必要的欄位
                supabase.table("stock_metadata").upsert({
                    "symbol": stock['symbol'],
                    "name": stock['name'],
                    "sector": stock['sector'],
                    "last_updated": datetime.now().isoformat()
                }).execute()
                success_count += 1
                
                # 每200檔顯示一次進度
                if (i+1) % 200 == 0:
                    log(f"已更新 {i+1}/{len(stocks)} 檔股票基本資料", "INFO")
                    
            except Exception as e:
                fail_count += 1
                # 只記錄前10個錯誤
                if fail_count <= 10:
                    log(f"更新 {stock['symbol']} 失敗: {str(e)[:50]}", "WARNING")
                continue
        
        log(f"完成更新 {success_count} 檔股票基本資料，失敗 {fail_count} 檔", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"更新股票基本資料失敗: {e}", "ERROR")
        return False

def get_stock_price_data(symbol, retry_count=2):
    """安全地獲取股票價格數據"""
    for attempt in range(retry_count):
        try:
            # 增加超時時間，減少重試次數
            df = yf.download(symbol, period="2d", progress=False, timeout=15)
            
            if df.empty or len(df) < 2:
                return None, None
            
            # 修正 FutureWarning
            close_data = df['Close']
            if len(close_data) >= 2:
                try:
                    curr_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    
                    # 確保是數值
                    if pd.isna(curr_close) or pd.isna(prev_close):
                        return None, None
                    
                    # 計算漲跌幅
                    curr_price = float(curr_close)
                    prev_price = float(prev_close)
                    
                    if prev_price == 0:
                        return None, None
                    
                    ret = (curr_price / prev_price) - 1
                    return ret, curr_price
                    
                except Exception as e:
                    return None, None
            
            return None, None
            
        except Exception as e:
            # 簡化錯誤處理，只重試一次
            if attempt < retry_count - 1:
                time.sleep(1)
                continue
            return None, None
    
    return None, None

# ========== 4. 主執行邏輯 ==========

def run_monitor():
    start_time = time.time()
    log("🚀 啟動智能台股監控系統 (CI 優化版)...")
    log(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 檢查 Gemini 服務
    if not genai_client:
        log("Gemini AI 服務未初始化，將跳過 AI 分析", "WARNING")
    
    # 獲取股票清單
    log("開始獲取股票清單...")
    stocks = get_comprehensive_stock_list()
    
    if not stocks:
        log("無法獲取股票清單，程序終止", "ERROR")
        send_telegram_msg("❌ *股票監控失敗*\n無法獲取股票清單")
        return
    
    # 更新股票基本資料（簡化版）
    update_stock_metadata_simple(stocks)
    
    # 發送開始通知
    send_telegram_msg(
        f"🔔 *台股強勢股掃描啟動*\n"
        f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"標的總數: {len(stocks)}"
    )
    
    found_count = 0
    limit_up_stocks = []
    error_count = 0
    total_stocks = len(stocks)
    
    log(f"開始掃描 {total_stocks} 檔股票...", "INFO")
    
    # 單執行緒掃描
    for idx, s in enumerate(stocks, 1):
        try:
            # 每50檔顯示一次進度
            if idx % 50 == 0:
                log_progress(idx, total_stocks, found_count)
            
            # 獲取股價數據
            ret, curr_price = get_stock_price_data(s['symbol'])
            
            if ret is None:
                error_count += 1
                continue
            
            # 漲幅門檻判定
            is_rotc = s.get('is_rotc', False)
            threshold = 0.1 if is_rotc else 0.098
            
            if ret >= threshold:
                # AI 分析（如果啟用）
                ai_comment = ""
                if genai_client:
                    ai_comment = ai_analysis_with_retry(s['name'], s['symbol'], s['sector'], ret)
                else:
                    ai_comment = "AI 服務未啟用"
                
                # 記錄漲停股票
                limit_up_stocks.append({
                    'symbol': s['symbol'],
                    'name': s['name'],
                    'sector': s['sector'],
                    'return': ret,
                    'price': curr_price,
                    'ai_comment': ai_comment,
                    'is_rotc': is_rotc
                })
                
                # 發送 Telegram 通知
                msg = (
                    f"🔥 *強勢股: {s['name']}* ({s['symbol']})\n"
                    f"📈 漲幅: {ret:.2%}\n"
                    f"💵 價格: {curr_price:.2f}\n"
                    f"🏷️ 類別: {'興櫃' if is_rotc else '上市/上櫃'}\n"
                    f"🤖 AI 分析: {ai_comment}"
                )
                
                send_telegram_msg(msg)
                log(f"已推播: {s['name']} ({ret:.2%})", "SUCCESS")
                found_count += 1
            
            # 控制請求速度（更快的速度以適應 CI 環境）
            delay = random.uniform(0.05, 0.1)
            time.sleep(delay)
            
        except Exception as e:
            error_count += 1
            if error_count % 100 == 0:
                log(f"已累積 {error_count} 個錯誤", "WARNING")
            continue
    
    # 顯示最終進度
    log_progress(total_stocks, total_stocks, found_count)
    
    # 計算執行時間
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    
    # 發送結束通知
    msg_end = (
        f"🏁 *掃描任務結束*\n"
        f"⏱️ 執行時間: {minutes}分{seconds}秒\n"
        f"✅ 總掃描: {total_stocks} 檔\n"
        f"✅ 發現漲停: {found_count} 檔\n"
        f"⚠️ 錯誤數量: {error_count} 個\n"
    )
    
    # 列出今日漲停板股票
    if limit_up_stocks:
        msg_end += f"\n📊 今日漲停板 ({len(limit_up_stocks)}檔):\n"
        sorted_stocks = sorted(limit_up_stocks, key=lambda x: x['return'], reverse=True)
        for i, stock in enumerate(sorted_stocks[:10], 1):
            msg_end += f"{i}. {stock['name']}({stock['symbol']}): {stock['return']:.2%}\n"
    
    send_telegram_msg(msg_end)
    
    # 生成統計報告
    log("\n" + "="*60, "INFO")
    log("📊 掃描統計報告", "INFO")
    log(f"總股票數: {total_stocks}", "INFO")
    log(f"成功掃描: {total_stocks - error_count}", "INFO")
    log(f"錯誤數量: {error_count}", "INFO")
    log(f"漲停板數: {found_count}", "INFO")
    log(f"執行時間: {minutes}分{seconds}秒", "INFO")
    
    # 分類統計
    if limit_up_stocks:
        rotc_count = sum(1 for stock in limit_up_stocks if stock.get('is_rotc', False))
        main_count = found_count - rotc_count
        log(f"上市/上櫃漲停: {main_count} 檔", "INFO")
        log(f"興櫃漲停: {rotc_count} 檔", "INFO")
    
    log("="*60, "INFO")

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        log("\n程式被使用者中斷", "WARNING")
        send_telegram_msg("⏹️ *程式被使用者中斷*")
    except Exception as e:
        log(f"程式執行錯誤: {e}", "ERROR")
        import traceback
        log(f"錯誤詳情: {traceback.format_exc()}", "ERROR")
        send_telegram_msg(f"❌ *程式執行錯誤*\n錯誤訊息: {str(e)[:100]}")

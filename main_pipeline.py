# -*- coding: utf-8 -*-

import os, sys, requests, time, random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from io import StringIO
from supabase import create_client
import warnings
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 忽略警告訊息
warnings.filterwarnings('ignore')

load_dotenv()

# ========== 1. 核心參數設定 ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 初始化 Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 執行緒安全的鎖
db_lock = threading.Lock()
tg_lock = threading.Lock()

# ========== 2. 日誌設定 ==========
def log(msg: str, level="INFO"):
    """自定義日誌函數（執行緒安全）"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_msg = f"{timestamp}: {msg}"
    print(formatted_msg, flush=True)

# ========== 3. 功能模組 ==========

def send_telegram_msg(message):
    """發送訊息到 Telegram（執行緒安全）"""
    if not TG_TOKEN or not TG_CHAT_ID: 
        return
    
    with tg_lock:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {
            "chat_id": TG_CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                log(f"Telegram 發送失敗: {response.status_code}")
        except Exception as e:
            log(f"Telegram 發送錯誤: {e}")

def get_taiwan_stock_list():
    """獲取台灣完整股票清單（不含權證）"""
    url_configs = [
        {'name': 'listed', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=1&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'dr', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=J&industry_code=&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'otc', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?market=2&issuetype=4&Page=1&chklike=Y', 'suffix': '.TWO'},
        {'name': 'etf', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=I&industry_code=&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'rotc', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=E&issuetype=R&industry_code=&Page=1&chklike=Y', 'suffix': '.TWO'},
        {'name': 'tw_innovation', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=C&issuetype=C&industry_code=&Page=1&chklike=Y', 'suffix': '.TW'},
        {'name': 'otc_innovation', 'url': 'https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=A&issuetype=C&industry_code=&Page=1&chklike=Y', 'suffix': '.TWO'},
    ]
    
    all_stocks = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    log("開始獲取台灣股票清單...")
    
    for config in tqdm(url_configs, desc="獲取股票清單", ncols=100):
        try:
            time.sleep(0.5)
            response = requests.get(config['url'], headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = 'big5'
            
            df = pd.read_html(StringIO(response.text), header=0)[0]
            count = 0
            
            for _, row in df.iterrows():
                code = str(row['有價證券代號']).strip()
                name = str(row['有價證券名稱']).strip()
                
                if 4 <= len(code) <= 6 and '權證' not in name:
                    stock_data = {
                        'symbol': f"{code}{config['suffix']}",
                        'name': name,
                        'sector': row['產業別'] if '產業別' in row else '其他',
                        'is_rotc': (config['name'] == 'rotc')
                    }
                    all_stocks.append(stock_data)
                    count += 1
            
            log(f"✅ 已獲取 {config['name']} {count} 檔股票")
            
        except Exception as e:
            log(f"❌ 獲取 {config['name']} 失敗: {str(e)[:30]}")
            continue
    
    if all_stocks:
        df_stocks = pd.DataFrame(all_stocks).drop_duplicates(subset=['symbol'])
        log(f"📊 總共獲取 {len(df_stocks)} 檔股票")
        log(f"  上市股票: {len(df_stocks[df_stocks['symbol'].str.endswith('.TW')])}")
        log(f"  上櫃股票: {len(df_stocks[df_stocks['symbol'].str.endswith('.TWO')])}")
        log(f"  興櫃股票: {len(df_stocks[df_stocks['is_rotc']])}")
        return df_stocks.to_dict('records')
    else:
        log("❌ 無法獲取任何股票資料")
        return []

def get_stock_price_data(symbol, max_retries=2):
    """獲取股票價格數據"""
    for attempt in range(max_retries):
        try:
            df = yf.download(symbol, period="2d", progress=False, timeout=8)
            
            if df.empty or len(df) < 2:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return None, None
            
            if 'Close' in df.columns:
                close_data = df['Close']
                if len(close_data) >= 2:
                    curr_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    
                    if pd.isna(curr_close) or pd.isna(prev_close) or prev_close == 0:
                        return None, None
                    
                    ret = (float(curr_close) / float(prev_close)) - 1
                    return ret, float(curr_close)
            
            return None, None
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return None, None
    
    return None, None

def save_limit_up_stock(stock_info):
    """儲存漲停板股票到資料庫（執行緒安全）"""
    if not supabase:
        return False
    
    with db_lock:
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            stock_data = {
                "analysis_date": today_str,
                "symbol": stock_info['symbol'],
                "stock_name": stock_info['name'],
                "sector": stock_info['sector'],
                "return_rate": stock_info['return'],
                "price": stock_info.get('price', 0),
                "is_rotc": stock_info.get('is_rotc', False),
                "created_at": datetime.now().isoformat()
            }
            
            if 'ai_comment' in stock_info:
                stock_data["ai_comment"] = stock_info['ai_comment']
            
            supabase.table("individual_stock_analysis").upsert(
                stock_data,
                on_conflict='analysis_date,symbol'
            ).execute()
            
            return True
            
        except Exception as e:
            log(f"儲存 {stock_info['symbol']} 失敗: {str(e)[:50]}")
            return False

def process_single_stock(stock):
    """處理單一股票（供多執行緒呼叫）"""
    try:
        ret, curr_price = get_stock_price_data(stock['symbol'])
        
        if ret is None:
            return None
        
        threshold = 0.1 if stock['is_rotc'] else 0.098
        
        if ret >= threshold:
            stock_info = {
                'symbol': stock['symbol'],
                'name': stock['name'],
                'sector': stock['sector'],
                'return': ret,
                'price': curr_price,
                'is_rotc': stock['is_rotc']
            }
            return stock_info
        
        return None
        
    except Exception as e:
        return None

# ========== 4. 主執行邏輯 ==========

def run_monitor():
    start_time = time.time()
    log("🚀 啟動台股漲停板掃描系統...")
    log(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not supabase:
        log("⚠️ Supabase 連線失敗，將只進行掃描不儲存資料")
    
    # 獲取股票清單
    stocks = get_taiwan_stock_list()
    
    if not stocks:
        log("❌ 無法獲取股票清單，程序終止")
        send_telegram_msg("❌ *股票監控失敗*\n無法獲取股票清單")
        return
    
    send_telegram_msg(
        f"🔔 *台股漲停板掃描啟動*\n"
        f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"標的總數: {len(stocks)}"
    )
    
    found_count = 0
    limit_up_stocks = []
    error_count = 0
    total_stocks = len(stocks)
    
    log(f"\n開始掃描 {total_stocks} 檔股票（使用 20 個執行緒並行處理）...")
    
    # 使用多執行緒並行處理
    with ThreadPoolExecutor(max_workers=20) as executor:
        # 提交所有任務
        future_to_stock = {executor.submit(process_single_stock, stock): stock for stock in stocks}
        
        # 使用 tqdm 顯示進度
        with tqdm(total=total_stocks, desc="掃描進度", ncols=100, unit="檔") as pbar:
            for future in as_completed(future_to_stock):
                stock = future_to_stock[future]
                
                try:
                    result = future.result()
                    
                    if result:
                        limit_up_stocks.append(result)
                        found_count += 1
                        
                        # 儲存到資料庫
                        if supabase:
                            save_limit_up_stock(result)
                        
                        # 發送 Telegram 通知
                        msg = (
                            f"🔥 *強勢股: {result['name']}* ({result['symbol']})\n"
                            f"📈 漲幅: {result['return']:.2%}\n"
                            f"💵 價格: {result['price']:.2f}\n"
                            f"🏷️ 類別: {'興櫃' if result['is_rotc'] else '上市/上櫃'}\n"
                            f"📊 產業: {result['sector']}"
                        )
                        send_telegram_msg(msg)
                        
                        # 即時顯示發現的漲停股
                        tqdm.write(f"✅ 發現漲停: {result['name']} ({result['symbol']}) {result['return']:.2%}")
                    
                except Exception as e:
                    error_count += 1
                
                # 更新進度條
                pbar.update(1)
                pbar.set_postfix({'漲停': found_count, '錯誤': error_count})
    
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
    
    if limit_up_stocks:
        msg_end += f"\n📊 今日漲停板 ({len(limit_up_stocks)}檔):\n"
        sorted_stocks = sorted(limit_up_stocks, key=lambda x: x['return'], reverse=True)
        
        for i, stock in enumerate(sorted_stocks[:15], 1):
            stock_type = "興" if stock['is_rotc'] else "普"
            msg_end += f"{i}. {stock['name']}({stock['symbol']}): {stock['return']:.2%} [{stock_type}]\n"
    
    send_telegram_msg(msg_end)
    
    # 生成統計報告
    log("\n" + "="*60)
    log("📊 掃描統計報告")
    log(f"總股票數: {total_stocks}")
    log(f"成功掃描: {total_stocks - error_count}")
    log(f"錯誤數量: {error_count}")
    log(f"漲停板數: {found_count}")
    log(f"執行時間: {minutes}分{seconds}秒")
    log(f"平均速度: {total_stocks/elapsed_time:.1f} 檔/秒")
    
    if limit_up_stocks:
        rotc_count = sum(1 for stock in limit_up_stocks if stock['is_rotc'])
        main_count = found_count - rotc_count
        log(f"上市/上櫃漲停: {main_count} 檔")
        log(f"興櫃漲停: {rotc_count} 檔")
        
        sector_counts = {}
        for stock in limit_up_stocks:
            sector = stock['sector']
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        
        log("🏭 產業分佈:")
        for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            log(f"  {sector}: {count}檔")
    
    log("="*60)
    
    # 儲存市場總結
    if supabase and limit_up_stocks:
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            sector_counts = {}
            for stock in limit_up_stocks:
                sector = stock['sector']
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
            
            summary_content = f"今日掃描 {total_stocks} 檔股票，發現 {found_count} 檔漲停板股票。\n\n"
            
            if sector_counts:
                summary_content += "產業分佈：\n"
                for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
                    summary_content += f"- {sector}: {count}檔\n"
            
            try:
                supabase.table("daily_market_summary").upsert({
                    "analysis_date": today_str,
                    "total_scanned": total_stocks,
                    "limit_up_count": found_count,
                    "summary_content": summary_content,
                    "sector_distribution": str(sector_counts)
                }).execute()
                log("✅ 已儲存市場總結")
            except:
                log("⚠️ 無法儲存市場總結，表格可能不存在")
                
        except Exception as e:
            log(f"❌ 儲存市場總結失敗: {e}")

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        log("\n⚠️ 程式被使用者中斷")
        send_telegram_msg("⏹️ *程式被使用者中斷*")
    except Exception as e:
        log(f"❌ 程式執行錯誤: {e}")
        send_telegram_msg(f"❌ *程式執行錯誤*\n錯誤訊息: {str(e)[:100]}")

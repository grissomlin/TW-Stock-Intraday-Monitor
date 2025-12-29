# -*- coding: utf-8 -*-
import os, sys, requests, time, random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from io import StringIO
from supabase import create_client
import warnings

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

# ========== 2. 日誌設定 ==========
def log(msg: str, level="INFO"):
    """自定義日誌函數"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_msg = f"{timestamp}: {msg}"
    print(formatted_msg, flush=True)

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
            log(f"Telegram 發送失敗: {response.status_code}")
    except Exception as e:
        log(f"Telegram 發送錯誤: {e}")

def get_taiwan_stock_list():
    """獲取台灣完整股票清單（不含權證）"""
    # 定義各類證券網址，只包含股票，不包含權證
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
    
    for config in url_configs:
        log(f"獲取 {config['name']} 類別...")
        
        try:
            time.sleep(0.5)  # 避免請求過快
            response = requests.get(config['url'], headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = 'big5'
            
            df = pd.read_html(StringIO(response.text), header=0)[0]
            count = 0
            
            for _, row in df.iterrows():
                code = str(row['有價證券代號']).strip()
                name = str(row['有價證券名稱']).strip()
                
                # 過濾權證（權證代碼通常較長或有特殊字元）
                if 4 <= len(code) <= 6 and '權證' not in name:
                    stock_data = {
                        'symbol': f"{code}{config['suffix']}",
                        'name': name,
                        'sector': row['產業別'] if '產業別' in row else '其他',
                        'is_rotc': (config['name'] == 'rotc')  # 興櫃標記
                    }
                    all_stocks.append(stock_data)
                    count += 1
            
            log(f"✅ 已獲取 {config['name']} {count} 檔股票")
            
        except Exception as e:
            log(f"❌ 獲取 {config['name']} 失敗: {str(e)[:30]}")
            continue
    
    # 去重複
    if all_stocks:
        df_stocks = pd.DataFrame(all_stocks).drop_duplicates(subset=['symbol'])
        log(f"📊 總共獲取 {len(df_stocks)} 檔股票")
        
        # 顯示統計
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
            # 只獲取最近2天的數據
            df = yf.download(symbol, period="2d", progress=False, timeout=10)
            
            if df.empty or len(df) < 2:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None, None
            
            # 獲取收盤價
            if 'Close' in df.columns:
                close_data = df['Close']
                if len(close_data) >= 2:
                    curr_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    
                    # 確保是數值且不為零
                    if pd.isna(curr_close) or pd.isna(prev_close) or prev_close == 0:
                        return None, None
                    
                    # 計算漲跌幅
                    ret = (float(curr_close) / float(prev_close)) - 1
                    return ret, float(curr_close)
            
            return None, None
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None, None
    
    return None, None

def save_limit_up_stock(stock_info):
    """儲存漲停板股票到資料庫"""
    if not supabase:
        return False
    
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 準備要儲存的資料
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
        
        # 如果有AI分析，加入
        if 'ai_comment' in stock_info:
            stock_data["ai_comment"] = stock_info['ai_comment']
        
        # 使用 upsert 避免重複
        supabase.table("individual_stock_analysis").upsert(
            stock_data,
            on_conflict='analysis_date,symbol'
        ).execute()
        
        return True
        
    except Exception as e:
        log(f"儲存 {stock_info['symbol']} 失敗: {str(e)[:50]}")
        return False

def create_required_tables():
    """建立必要的資料庫表格（如果不存在）"""
    if not supabase:
        return False
    
    try:
        log("檢查資料庫表格...")
        
        # 檢查 individual_stock_analysis 表格
        try:
            test = supabase.table("individual_stock_analysis").select("symbol").limit(1).execute()
            log("✅ individual_stock_analysis 表格已存在")
        except Exception as e:
            log("⚠️ individual_stock_analysis 表格可能需要創建")
            log("請在 Supabase 執行以下 SQL:")
            log("""
            CREATE TABLE IF NOT EXISTS individual_stock_analysis (
                id SERIAL PRIMARY KEY,
                analysis_date DATE NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                stock_name VARCHAR(100),
                sector VARCHAR(50),
                return_rate DECIMAL(10,4),
                price DECIMAL(10,2),
                ai_comment TEXT,
                is_rotc BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(analysis_date, symbol)
            );
            """)
        
        return True
    except Exception as e:
        log(f"檢查資料庫表格失敗: {e}")
        return False

# ========== 4. 主執行邏輯 ==========

def run_monitor():
    start_time = time.time()
    log("🚀 啟動台股漲停板掃描系統...")
    log(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 檢查資料庫連線
    if not supabase:
        log("⚠️ Supabase 連線失敗，將只進行掃描不儲存資料")
    
    # 建立必要的表格
    if supabase:
        create_required_tables()
    
    # 獲取股票清單
    stocks = get_taiwan_stock_list()
    
    if not stocks:
        log("❌ 無法獲取股票清單，程序終止")
        send_telegram_msg("❌ *股票監控失敗*\n無法獲取股票清單")
        return
    
    # 發送開始通知
    send_telegram_msg(
        f"🔔 *台股漲停板掃描啟動*\n"
        f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"標的總數: {len(stocks)}"
    )
    
    found_count = 0
    limit_up_stocks = []
    error_count = 0
    total_stocks = len(stocks)
    
    log(f"開始掃描 {total_stocks} 檔股票...")
    
    # 單執行緒掃描
    for idx, stock in enumerate(stocks, 1):
        try:
            # 顯示進度
            if idx % 100 == 0 or idx == total_stocks:
                progress = (idx / total_stocks) * 100
                log(f"進度: {idx}/{total_stocks} ({progress:.1f}%), 發現漲停: {found_count}")
            
            # 獲取股價數據
            ret, curr_price = get_stock_price_data(stock['symbol'])
            
            if ret is None:
                error_count += 1
                continue
            
            # 漲幅門檻判定（興櫃10%，其他9.8%）
            threshold = 0.1 if stock['is_rotc'] else 0.098
            
            if ret >= threshold:
                # 記錄漲停股票
                stock_info = {
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'sector': stock['sector'],
                    'return': ret,
                    'price': curr_price,
                    'is_rotc': stock['is_rotc']
                }
                
                limit_up_stocks.append(stock_info)
                
                # 儲存到資料庫
                if supabase:
                    save_success = save_limit_up_stock(stock_info)
                    if not save_success:
                        log(f"⚠️ 儲存 {stock['symbol']} 到資料庫失敗")
                
                # 發送 Telegram 通知
                msg = (
                    f"🔥 *強勢股: {stock['name']}* ({stock['symbol']})\n"
                    f"📈 漲幅: {ret:.2%}\n"
                    f"💵 價格: {curr_price:.2f}\n"
                    f"🏷️ 類別: {'興櫃' if stock['is_rotc'] else '上市/上櫃'}\n"
                    f"📊 產業: {stock['sector']}"
                )
                
                send_telegram_msg(msg)
                log(f"✅ 已推播: {stock['name']} ({ret:.2%})")
                found_count += 1
            
            # 控制請求速度
            delay = random.uniform(0.08, 0.15)
            time.sleep(delay)
            
        except Exception as e:
            error_count += 1
            if error_count % 50 == 0:
                log(f"⚠️ 已累積 {error_count} 個錯誤")
            continue
    
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
        
        # 按漲幅排序
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
    
    # 分類統計
    if limit_up_stocks:
        rotc_count = sum(1 for stock in limit_up_stocks if stock['is_rotc'])
        main_count = found_count - rotc_count
        log(f"上市/上櫃漲停: {main_count} 檔")
        log(f"興櫃漲停: {rotc_count} 檔")
        
        # 產業分佈
        sector_counts = {}
        for stock in limit_up_stocks:
            sector = stock['sector']
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        
        log("🏭 產業分佈:")
        for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            log(f"  {sector}: {count}檔")
    
    log("="*60)
    
    # 儲存市場總結（如果資料庫可用）
    if supabase and limit_up_stocks:
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # 統計產業分佈
            sector_counts = {}
            for stock in limit_up_stocks:
                sector = stock['sector']
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
            
            summary_content = f"今日掃描 {total_stocks} 檔股票，發現 {found_count} 檔漲停板股票。\n\n"
            
            if sector_counts:
                summary_content += "產業分佈：\n"
                for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
                    summary_content += f"- {sector}: {count}檔\n"
            
            # 儲存到 daily_market_summary（如果表格存在）
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

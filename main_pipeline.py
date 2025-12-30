# -*- coding: utf-8 -*-
import os, sys, requests, time, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from io import StringIO
import warnings
from tqdm import tqdm

# 忽略警告訊息
warnings.filterwarnings('ignore')

# ========== 手動添加路徑 ==========
# 在 GitHub Actions 中，需要明確添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 嘗試導入自訂模組
AI_AVAILABLE = False
ai_analyzer = None
StockPrompts = None

try:
    from ai_analyzer import StockAIAnalyzer
    from prompts import StockPrompts
    AI_AVAILABLE = True
    print("✅ AI模組導入成功")
except ImportError as e:
    print(f"⚠️ AI模組導入失敗: {e}")
    print("嘗試重新導入...")
    
    # 嘗試另一種導入方式
    try:
        # 直接從當前目錄導入
        import importlib.util
        
        # 導入 ai_analyzer
        ai_analyzer_path = os.path.join(current_dir, "ai_analyzer.py")
        spec = importlib.util.spec_from_file_location("ai_analyzer", ai_analyzer_path)
        ai_analyzer_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ai_analyzer_module)
        StockAIAnalyzer = ai_analyzer_module.StockAIAnalyzer
        
        # 導入 prompts
        prompts_path = os.path.join(current_dir, "prompts.py")
        spec = importlib.util.spec_from_file_location("prompts", prompts_path)
        prompts_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prompts_module)
        StockPrompts = prompts_module.StockPrompts
        
        AI_AVAILABLE = True
        print("✅ AI模組動態導入成功")
    except Exception as e2:
        print(f"❌ AI模組動態導入失敗: {e2}")
        AI_AVAILABLE = False

# ========== 載入環境變數 ==========
load_dotenv()

# 環境變數檢查
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print(f"🔧 環境變數檢查:")
print(f"  SUPABASE_URL: {'已設置' if SUPABASE_URL else '未設置'}")
print(f"  SUPABASE_KEY: {'已設置' if SUPABASE_KEY else '未設置'}")
print(f"  TG_TOKEN: {'已設置' if TG_TOKEN else '未設置'}")
print(f"  TG_CHAT_ID: {'已設置' if TG_CHAT_ID else '未設置'}")
print(f"  GEMINI_API_KEY: {'已設置' if GEMINI_API_KEY else '未設置'}")
print(f"  AI模組可用: {AI_AVAILABLE}")

# ========== 初始化 ==========
from supabase import create_client

# 初始化 Supabase
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase 初始化成功")
    except Exception as e:
        print(f"❌ Supabase 初始化失敗: {e}")
else:
    print("⚠️ Supabase 環境變數未設置")

# 初始化 AI 分析器
if AI_AVAILABLE and GEMINI_API_KEY and supabase:
    try:
        ai_analyzer = StockAIAnalyzer(GEMINI_API_KEY, supabase)
        print("✅ AI分析器初始化成功")
    except Exception as e:
        print(f"❌ AI分析器初始化失敗: {e}")
        ai_analyzer = None
else:
    print("⚠️ AI分析器未初始化 (檢查: AI_AVAILABLE={AI_AVAILABLE}, GEMINI_API_KEY={'已設置' if GEMINI_API_KEY else '未設置'}, supabase={'已連接' if supabase else '未連接'})")

# ========== 日誌設定 ==========
def log(msg: str, level="INFO"):
    """自定義日誌函數"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_msg = f"{timestamp}: {msg}"
    print(formatted_msg, flush=True)

# ========== 功能模組 ==========
def send_telegram_msg(message):
    """發送訊息到 Telegram"""
    if not TG_TOKEN or not TG_CHAT_ID:
        log("⚠️ Telegram 憑證未設置")
        return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            log(f"Telegram 訊息發送成功")
        else:
            log(f"Telegram 發送失敗: {response.status_code}")
    except Exception as e:
        log(f"Telegram 發送錯誤: {e}")


def get_taiwan_stock_list():
    """獲取台灣完整股票清單"""
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
        return df_stocks.to_dict('records')
    else:
        log("❌ 無法獲取任何股票資料")
        return []

def get_stock_price_data(symbol, max_retries=2):
    """獲取股票價格數據（改進版）"""
    for attempt in range(max_retries):
        try:
            df = yf.download(symbol, period="2d", progress=False, timeout=10)
            
            if df.empty or len(df) < 2:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None, None, None
            
            if 'Close' in df.columns:
                close_data = df['Close']
                if len(close_data) >= 2:
                    curr_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    
                    if pd.isna(curr_close) or pd.isna(prev_close) or prev_close == 0:
                        return None, None, None
                    
                    ret = (float(curr_close) / float(prev_close)) - 1
                    return ret, float(curr_close), float(prev_close)
            
            return None, None, None
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None, None, None
    
    return None, None, None

def get_consecutive_limit_up_days(symbol):
    """查詢連續漲停天數（修正版）"""
    try:
        if not supabase:
            return 1
        
        today = datetime.now().strftime("%Y-%m-%d")
        five_days_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        
        response = supabase.table("individual_stock_analysis")\
            .select("analysis_date, return_rate, is_rotc")\
            .eq("symbol", symbol)\
            .gte("analysis_date", five_days_ago)\
            .lte("analysis_date", today)\
            .order("analysis_date", desc=False)\
            .execute()
        
        if not response.data:
            return 1
        
        consecutive_days = 0
        
        # 按日期排序（從舊到新）
        sorted_records = sorted(response.data, key=lambda x: x['analysis_date'])
        
        # 從昨天開始檢查連續漲停
        for record in sorted_records[-5:]:  # 只看最近5天
            return_rate = record.get('return_rate')
            is_rotc = record.get('is_rotc', False)
            threshold = 0.10 if is_rotc else 0.098
            
            # 檢查 return_rate 是否為 None
            if return_rate is None:
                break
                
            if float(return_rate) >= threshold:
                consecutive_days += 1
            else:
                break
        
        return max(consecutive_days, 1)
        
    except Exception as e:
        log(f"查詢連續漲停天數失敗 {symbol}: {e}")
        return 11

def save_stock_with_analysis(stock_info):
    """儲存股票分析資訊到資料庫"""
    if not supabase:
        return False
    
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        data = {
            "analysis_date": today_str,
            "symbol": stock_info['symbol'],
            "stock_name": stock_info['name'],
            "sector": stock_info.get('sector', ''),
            "return_rate": stock_info.get('return', 0),
            "price": stock_info.get('price', 0),
            "is_rotc": stock_info.get('is_rotc', False),
            "ai_comment": stock_info.get('ai_comment', ''),
            "consecutive_days": stock_info.get('consecutive_days', 1),
            "volume_ratio": stock_info.get('volume_ratio'),
            "created_at": datetime.now().isoformat()
        }
        
        # 使用 upsert
        supabase.table("individual_stock_analysis").upsert(
            data,
            on_conflict='analysis_date,symbol'
        ).execute()
        
        return True
        
    except Exception as e:
        log(f"儲存股票分析失敗 {stock_info['symbol']}: {e}")
        return False

def save_sector_analysis(sector_name, stocks_in_sector, ai_analysis):
    """儲存產業分析"""
    if not supabase:
        return False
    
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        data = {
            "analysis_date": today_str,
            "sector_name": sector_name,
            "stock_count": len(stocks_in_sector),
            "stocks_included": json.dumps([s['symbol'] for s in stocks_in_sector]),
            "ai_analysis": ai_analysis,
            "created_at": datetime.now().isoformat()
        }
        
        supabase.table("sector_analysis").upsert(data).execute()
        return True
        
    except Exception as e:
        log(f"儲存產業分析失敗 {sector_name}: {e}")
        return False

def update_consecutive_limit_up(stock_info):
    """更新連續漲停追蹤表"""
    if not supabase:
        return
    
    try:
        symbol = stock_info['symbol']
        consecutive_days = stock_info.get('consecutive_days', 1)
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if consecutive_days == 1:
            # 第一根漲停，建立新紀錄
            data = {
                "symbol": symbol,
                "start_date": today_str,
                "consecutive_days": 1,
                "status": "ongoing",
                "updated_at": datetime.now().isoformat()
            }
            supabase.table("consecutive_limit_up").upsert(data, on_conflict='symbol').execute()
        else:
            # 更新連續天數
            supabase.table("consecutive_limit_up")\
                .update({
                    "consecutive_days": consecutive_days,
                    "status": "ongoing",
                    "updated_at": datetime.now().isoformat()
                })\
                .eq("symbol", symbol)\
                .execute()
                
    except Exception as e:
        log(f"更新連續漲停追蹤失敗 {stock_info['symbol']}: {e}")

def send_layered_notifications(stocks, sector_analyses, market_summary):
    """分層推播通知"""
    
    # 1. 個股推播（最多10檔）
    log("📤 發送個股推播通知...")
    top_stocks = sorted(stocks, key=lambda x: x.get('consecutive_days', 1), reverse=True)[:10]
    
    for stock in top_stocks:
        days = stock.get('consecutive_days', 1)
        
        if days >= 3:
            emoji = "🚀🚀🚀"
            priority = "🔥🔥🔥"
        elif days == 2:
            emoji = "🚀🚀"
            priority = "🔥🔥"
        else:
            emoji = "🚀"
            priority = "🔥"
        
        ai_preview = stock.get('ai_comment', '')[:100] if stock.get('ai_comment') else ''
        
        msg = (
            f"{emoji} *{priority} 強勢股: {stock['name']}* ({stock['symbol']})\n"
            f"📈 漲幅: {stock['return']:.2%} | 連板: {days}天\n"
            f"💵 價格: {stock['price']:.2f}\n"
            f"🏷️ 類別: {'興櫃' if stock['is_rotc'] else '上市/上櫃'}\n"
            f"📊 產業: {stock['sector']}"
        )
        
        if ai_preview:
            msg += f"\n🤖 AI: {ai_preview}..."
        
        send_telegram_msg(msg)
        time.sleep(0.1)
    
    # 2. 產業推播（最多5個產業）
    if sector_analyses:
        log("📤 發送產業趨勢推播...")
        for sector, analysis in list(sector_analyses.items())[:5]:
            stocks_count = len([s for s in stocks if s.get('sector') == sector])
            
            # 找出產業龍頭
            sector_stocks = [s for s in stocks if s.get('sector') == sector]
            if sector_stocks:
                leader = max(sector_stocks, key=lambda x: x.get('consecutive_days', 1))
                leader_days = leader.get('consecutive_days', 1)
                
                msg = (
                    f"🏭 *產業趨勢: {sector}*\n"
                    f"📊 漲停家數: {stocks_count}家\n"
                    f"👑 龍頭股: {leader['name']}({leader_days}連板)\n"
                    f"🤖 AI分析: {analysis[:200]}..."
                )
            else:
                msg = (
                    f"🏭 *產業趨勢: {sector}*\n"
                    f"📊 漲停家數: {stocks_count}家\n"
                    f"🤖 AI分析: {analysis[:200]}..."
                )
            
            send_telegram_msg(msg)
            time.sleep(0.1)
    
    # 3. 市場總結推播
    if market_summary:
        log("📤 發送市場總結推播...")
        
        total_stocks = len(stocks)
        rotc_count = sum(1 for s in stocks if s.get('is_rotc'))
        main_count = total_stocks - rotc_count
        avg_consecutive = sum(s.get('consecutive_days', 1) for s in stocks) / total_stocks if total_stocks > 0 else 0
        
        msg = (
            f"📊 *今日市場AI總結*\n"
            f"📈 總漲停: {total_stocks}檔\n"
            f"📊 上市櫃: {main_count} | 興櫃: {rotc_count}\n"
            f"📅 平均連板: {avg_consecutive:.1f}天\n"
            f"🤖 市場分析: {market_summary[:300]}..."
        )
        
        send_telegram_msg(msg)

# ========== 4. 主執行邏輯 ==========
def run_monitor():
    start_time = time.time()
    log("🚀 啟動台股漲停板掃描系統（AI增強版）...")
    log(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 檢查連線
    if not supabase:
        log("⚠️ Supabase 連線失敗，將只進行掃描不儲存資料")
    
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
    
    total_stocks = len(stocks)
    log(f"開始掃描 {total_stocks} 檔股票...")
    
    found_count = 0
    limit_up_stocks = []
    error_count = 0
    
    # 準備 symbol 列表
    symbols = [stock['symbol'] for stock in stocks]
    stock_dict = {stock['symbol']: stock for stock in stocks}
    
    # 批量下載
    batch_size = 150
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
    
    # 掃描漲停股票
    for batch_idx, batch_symbols in enumerate(tqdm(batches, desc="批次進度", unit="batch")):
        try:
            df_batch = yf.download(batch_symbols, period="2d", progress=False, group_by='ticker')
            
            for symbol in batch_symbols:
                try:
                    stock_info = stock_dict[symbol]
                    if symbol not in df_batch:
                        error_count += 1
                        continue
                    
                    df = df_batch[symbol]
                    close_data = df['Close'].dropna()
                    if len(close_data) < 2:
                        error_count += 1
                        continue
                    
                    curr_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    
                    if pd.isna(curr_close) or pd.isna(prev_close) or prev_close == 0:
                        error_count += 1
                        continue
                    
                    ret = (curr_close / prev_close) - 1
                    threshold = 0.1 if stock_info['is_rotc'] else 0.098
                    
                    if ret >= threshold:
                        info = {
                            'symbol': symbol,
                            'name': stock_info['name'],
                            'sector': stock_info['sector'],
                            'return': ret,
                            'price': float(curr_close),
                            'prev_close': float(prev_close),
                            'is_rotc': stock_info['is_rotc'],
                            'consecutive_days': 1  # 稍後會計算
                        }
                        limit_up_stocks.append(info)
                        found_count += 1
                        
                except Exception as e:
                    error_count += 1
                    continue
                    
        except Exception as e:
            log(f"批次 {batch_idx} 下載失敗: {e}")
            error_count += len(batch_symbols)
        
        time.sleep(1)
    
    log(f"掃描完成，發現 {found_count} 檔漲停股票")
    
    # ========== AI分析階段 ==========
    if limit_up_stocks and ai_analyzer:
        log("🤖 開始AI分析階段...")
        
        # 1. 計算連續漲停天數
        log("📅 計算連續漲停天數...")
        for stock in limit_up_stocks:
            stock['consecutive_days'] = get_consecutive_limit_up_days(stock['symbol'])
        
        # 2. 個股AI分析
        log("🧠 進行個股AI分析...")
        for stock in tqdm(limit_up_stocks, desc="個股AI分析"):
            try:
                ai_comment = ai_analyzer.analyze_individual_stock(stock)
                if ai_comment:
                    stock['ai_comment'] = ai_comment
                    save_stock_with_analysis(stock)
                    update_consecutive_limit_up(stock)
                time.sleep(0.5)  # 避免API限制
            except Exception as e:
                log(f"個股AI分析失敗 {stock['symbol']}: {e}")
        
        # 3. 產業AI分析
        log("🏭 進行產業AI分析...")
        sector_groups = {}
        for stock in limit_up_stocks:
            sector = stock.get('sector', '其他')
            if sector not in sector_groups:
                sector_groups[sector] = []
            sector_groups[sector].append(stock)
        
        sector_analyses = {}
        for sector, stocks_in_sector in sector_groups.items():
            if len(stocks_in_sector) > 1:  # 同產業超過1家才分析
                try:
                    analysis = ai_analyzer.analyze_sector(sector, stocks_in_sector)
                    if analysis:
                        sector_analyses[sector] = analysis
                        save_sector_analysis(sector, stocks_in_sector, analysis)
                    time.sleep(0.5)
                except Exception as e:
                    log(f"產業AI分析失敗 {sector}: {e}")
        
        # 4. 市場AI分析
        log("📊 進行市場AI分析...")
        market_summary = None
        try:
            market_summary = ai_analyzer.analyze_market_summary(limit_up_stocks)
        except Exception as e:
            log(f"市場AI分析失敗: {e}")
        
        # 5. 發送分層通知
        send_layered_notifications(limit_up_stocks, sector_analyses, market_summary)
        
        # 6. 更新市場總結
        if market_summary and supabase:
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                safe_data = {
                    "analysis_date": today_str,
                    "stock_count": total_stocks,
                    "summary_content": market_summary[:5000],  # 限制長度
                    "stock_list": ", ".join([s['name'] + '(' + s['symbol'] + ')' for s in limit_up_stocks]) if limit_up_stocks else "無",
                    "created_at": datetime.now().isoformat()
                }
                supabase.table("daily_market_summary").upsert(safe_data).execute()
            except Exception as e:
                log(f"更新市場總結失敗: {e}")
    
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
        f"⚠️ 錯誤數量: {error_count} 個"
    )
    
    if limit_up_stocks:
        msg_end += f"\n\n📊 今日漲停板 ({len(limit_up_stocks)}檔):"
        sorted_stocks = sorted(limit_up_stocks, key=lambda x: x.get('consecutive_days', 1), reverse=True)
        for i, stock in enumerate(sorted_stocks[:10], 1):
            days = stock.get('consecutive_days', 1)
            stock_type = "興" if stock['is_rotc'] else "普"
            msg_end += f"\n{i}. {stock['name']}({stock['symbol']}): {stock['return']:.2%} [{days}連板]"
    
    send_telegram_msg(msg_end)
    
    # 生成統計報告
    log("\n" + "="*60)
    log("📊 掃描統計報告")
    log(f"總股票數: {total_stocks}")
    log(f"成功掃描: {total_stocks - error_count}")
    log(f"錯誤數量: {error_count}")
    log(f"漲停板數: {found_count}")
    log(f"執行時間: {minutes}分{seconds}秒")
    
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
            log(f" {sector}: {count}檔")
    
    log("="*60)

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        log("\n⚠️ 程式被使用者中斷")
        send_telegram_msg("⏹️ *程式被使用者中斷*")
    except Exception as e:
        log(f"❌ 程式執行錯誤: {e}")
        send_telegram_msg(f"❌ *程式執行錯誤*\n錯誤訊息: {str(e)[:100]}")




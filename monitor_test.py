# -*- coding: utf-8 -*-
import os, io, requests
import pandas as pd
import yfinance as yf
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client

# ========== 1. 設定與初始化 ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== 2. 現場獲取台股清單 (含產業別) ==========
def get_current_stock_list():
    urls = [
        ('https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=1', '.TW'),
        ('https://isin.twse.com.tw/isin/class_main.jsp?market=2&issuetype=4', '.TWO')
    ]
    all_stocks = []
    for url, suffix in urls:
        resp = requests.get(url)
        # 用 pandas 抓取網頁表格
        df = pd.read_html(StringIO(resp.text), header=0)[0]
        for _, row in df.iterrows():
            code = str(row['有價證券代號']).strip()
            # 簡單過濾：代號為 4 位數的通常是個股
            if len(code) == 4:
                all_stocks.append({
                    'symbol': f"{code}{suffix}",
                    'name': row['有價證券名稱'],
                    'sector': row.get('產業別', '其他')
                })
    return pd.DataFrame(all_stocks)

# ========== 3. 抓取並判斷漲停 ==========
def check_limit_up(stock):
    try:
        # 抓取最近 5 天日線 (為了確保有昨天和今天)
        df = yf.download(stock['symbol'], period="5d", progress=False)
        if len(df) < 2: return None
        
        # 處理 MultiIndex 欄位 (yfinance 2.0+ 特性)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        last_close = float(df['Close'].iloc[-2]) # 昨日收盤價
        curr_price = float(df['Close'].iloc[-1]) # 最新成交價
        
        # 計算漲幅
        change_pct = (curr_price - last_close) / last_close
        
        # 判斷是否大於 9.8% (台股漲停標準)
        if change_pct >= 0.098:
            return {
                'symbol': stock['symbol'],
                'name': stock['name'],
                'sector': stock['sector'],
                'change': f"{change_pct:.2%}"
            }
    except:
        return None

# ========== 4. 執行主程式 ==========
def run_test():
    # A. 抓清單
    stocks_df = get_current_stock_list()
    # 測試時可以先縮小範圍，例如只抓前 100 檔，不然會跑很久
    # stocks_df = stocks_df.head(100) 
    
    limit_up_results = []
    
    print(f"📡 正在掃描 {len(stocks_df)} 檔股票...")
    
    # B. 多執行緒抓股價 (提高效率)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_limit_up, s) for _, s in stocks_df.iterrows()]
        for f in as_completed(futures):
            res = f.result()
            if res:
                limit_up_results.append(res)
                print(f"✅ 發現漲停：{res['name']} ({res['symbol']})")

    # C. 按產業整理並寫入 Supabase
    if limit_up_results:
        res_df = pd.DataFrame(limit_up_results)
        for sector, group in res_df.groupby('sector'):
            names = ", ".join(group['name'].tolist())
            
            data = {
                "sector": sector,
                "stock_list": names,
                "ai_comment": ""  # 🔴 先留空，測試寫入功能
            }
            
            try:
                supabase.table("intraday_analysis").upsert(data, on_conflict="analysis_date,sector").execute()
                print(f"💾 已記錄產業：{sector}")
            except Exception as e:
                print(f"❌ 寫入失敗: {e}")
    else:
        print("今日目前無偵測到漲停股。")

if __name__ == "__main__":
    run_test()

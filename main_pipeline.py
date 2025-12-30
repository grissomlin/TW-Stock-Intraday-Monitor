# -*- coding: utf-8 -*-

import os
import time
import random
import requests
import warnings
from datetime import datetime
from io import StringIO

import pandas as pd
import yfinance as yf
from tqdm import tqdm
from dotenv import load_dotenv
from supabase import create_client

warnings.filterwarnings("ignore")
load_dotenv()

# =====================================================
# 1. 環境參數
# =====================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None


# =====================================================
# 2. Log & Telegram
# =====================================================
def log(msg: str):
    print(f"{datetime.now().strftime('%H:%M:%S')}: {msg}", flush=True)


def send_telegram_msg(message: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram 發送失敗: {e}")


# =====================================================
# 3. 台股清單
# =====================================================
def get_taiwan_stock_list():
    url_configs = [
        {"name": "listed", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=1&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "dr", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=J&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "otc", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=2&issuetype=4&Page=1&chklike=Y", "suffix": ".TWO"},
        {"name": "etf", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=I&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "rotc", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=E&issuetype=R&Page=1&chklike=Y", "suffix": ".TWO"},
    ]

    stocks = []
    headers = {"User-Agent": "Mozilla/5.0"}

    log("📋 取得台股清單...")

    for cfg in url_configs:
        try:
            r = requests.get(cfg["url"], headers=headers, timeout=15)
            r.encoding = "big5"
            df = pd.read_html(StringIO(r.text))[0]

            count = 0
            for _, row in df.iterrows():
                code = str(row["有價證券代號"]).strip()
                name = str(row["有價證券名稱"]).strip()

                if 4 <= len(code) <= 6 and "權證" not in name:
                    stocks.append({
                        "symbol": f"{code}{cfg['suffix']}",
                        "name": name,
                        "sector": row.get("產業別", "其他"),
                        "is_rotc": cfg["name"] == "rotc"
                    })
                    count += 1

            log(f"✅ {cfg['name']}：{count} 檔")
        except Exception as e:
            log(f"❌ {cfg['name']} 失敗: {e}")

    df = pd.DataFrame(stocks).drop_duplicates("symbol")
    log(f"📊 股票總數：{len(df)}")
    return df.to_dict("records")


# =====================================================
# 4. 🚀 批次抓價（最重要）
# =====================================================
def batch_fetch_prices(stocks):
    symbols = [s["symbol"] for s in stocks]

    log(f"📡 批次下載 {len(symbols)} 檔股價...")
    df = yf.download(
        symbols,
        period="2d",
        group_by="ticker",
        threads=True,
        progress=False,
    )

    price_map = {}

    for s in stocks:
        sym = s["symbol"]
        try:
            close = df[sym]["Close"]
            if len(close) < 2:
                continue
            prev, curr = close.iloc[-2], close.iloc[-1]
            if pd.isna(prev) or pd.isna(curr) or prev == 0:
                continue
            ret = float(curr / prev - 1)
            price_map[sym] = (ret, float(curr))
        except Exception:
            continue

    log(f"✅ 可用行情：{len(price_map)} 檔")
    return price_map


# =====================================================
# 5. Supabase
# =====================================================
def save_limit_up_stock(stock):
    if not supabase:
        return

    supabase.table("individual_stock_analysis").upsert(
        {
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "symbol": stock["symbol"],
            "stock_name": stock["name"],
            "sector": stock["sector"],
            "return_rate": stock["return"],
            "price": stock["price"],
            "is_rotc": stock["is_rotc"],
            "created_at": datetime.now().isoformat(),
        },
        on_conflict="analysis_date,symbol",
    ).execute()


# =====================================================
# 6. 主程式
# =====================================================
def run_monitor():
    start = time.time()

    log("🚀 台股漲停掃描啟動")

    stocks = get_taiwan_stock_list()
    if not stocks:
        log("❌ 無股票資料")
        return

    send_telegram_msg(f"🔔 *漲停掃描啟動*\n標的數：{len(stocks)}")

    price_map = batch_fetch_prices(stocks)

    limit_up = []

    for stock in tqdm(stocks, desc="📈 掃描股票", ncols=90):
        sym = stock["symbol"]
        if sym not in price_map:
            continue

        ret, price = price_map[sym]
        threshold = 0.1 if stock["is_rotc"] else 0.098

        if ret >= threshold:
            info = {
                **stock,
                "return": ret,
                "price": price,
            }
            limit_up.append(info)

            save_limit_up_stock(info)

            send_telegram_msg(
                f"🔥 *{stock['name']}* ({sym})\n"
                f"📈 漲幅: {ret:.2%}\n"
                f"💰 價格: {price:.2f}\n"
                f"🏷 {'興櫃' if stock['is_rotc'] else '上市/上櫃'}"
            )

    elapsed = int(time.time() - start)

    log(f"🏁 掃描完成，用時 {elapsed//60}分{elapsed%60}秒")
    log(f"🔥 漲停股：{len(limit_up)} 檔")

    if limit_up:
        summary = "📊 *今日漲停股*\n"
        for s in sorted(limit_up, key=lambda x: x["return"], reverse=True)[:15]:
            summary += f"- {s['name']} {s['return']:.2%}\n"
        send_telegram_msg(summary)


# =====================================================
if __name__ == "__main__":
    run_monitor()

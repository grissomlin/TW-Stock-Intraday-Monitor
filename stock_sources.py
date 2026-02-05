# -*- coding: utf-8 -*-
import time
import random
import requests
import pandas as pd
from io import StringIO
from logger import log

def get_taiwan_stock_list() -> list[dict]:
    url_configs = [
        {"name": "listed", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=1&issuetype=1&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "dr", "url": "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=J&industry_code=&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "otc", "url": "https://isin.twse.com.tw/isin/class_main.jsp?market=2&issuetype=4&Page=1&chklike=Y", "suffix": ".TWO"},
        {"name": "etf", "url": "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=I&industry_code=&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "rotc", "url": "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=E&issuetype=R&industry_code=&Page=1&chklike=Y", "suffix": ".TWO"},
        {"name": "tw_innovation", "url": "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=C&issuetype=C&industry_code=&Page=1&chklike=Y", "suffix": ".TW"},
        {"name": "otc_innovation", "url": "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=A&issuetype=C&industry_code=&Page=1&chklike=Y", "suffix": ".TWO"},
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    all_stocks: list[dict] = []

    log("開始獲取台灣股票清單...")

    for cfg in url_configs:
        log(f"獲取 {cfg['name']} 類別...")
        try:
            time.sleep(random.uniform(0.3, 0.8))
            r = requests.get(cfg["url"], headers=headers, timeout=15)
            r.raise_for_status()
            r.encoding = "big5"

            df = pd.read_html(StringIO(r.text), header=0)[0]
            count = 0

            for _, row in df.iterrows():
                code = str(row.get("有價證券代號", "")).strip()
                name = str(row.get("有價證券名稱", "")).strip()
                if 4 <= len(code) <= 6 and "權證" not in name:
                    all_stocks.append({
                        "symbol": f"{code}{cfg['suffix']}",
                        "name": name,
                        "sector": row["產業別"] if "產業別" in row else "其他",
                        "is_rotc": (cfg["name"] == "rotc"),
                        "market": "上市" if cfg["suffix"] == ".TW" and cfg["name"] != "rotc" else ("上櫃" if cfg["suffix"] == ".TWO" else "興櫃"),
                    })
                    count += 1

            log(f"✅ 已獲取 {cfg['name']} {count} 檔股票")
        except Exception as e:
            log(f"❌ 獲取 {cfg['name']} 失敗: {str(e)[:80]}")
            continue

    if not all_stocks:
        log("❌ 無法獲取任何股票資料")
        return []

    df_all = pd.DataFrame(all_stocks).drop_duplicates(subset=["symbol"])
    log(f"📊 總共獲取 {len(df_all)} 檔股票")
    return df_all.to_dict("records")

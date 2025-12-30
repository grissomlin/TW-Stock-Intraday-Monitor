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
import google.generativeai as genai

# 忽略警告訊息
warnings.filterwarnings('ignore')

load_dotenv()

# ========== 1. 核心參數設定 ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 初始化 Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 初始化 Gemini
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        log("✅ Gemini AI 初始化成功")
    except Exception as e:
        gemini_model = None
        log(f"❌ Gemini 初始化失敗: {e}")
else:
    gemini_model = None
    log("⚠️ 未設定 GEMINI_API_KEY，將跳過 AI 分析")

# ========== 2. 日誌設定 ==========
def log(msg: str, level="INFO"):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{timestamp}: {msg}", flush=True)

# ========== 3. 功能模組 ==========
def send_telegram_msg(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log(f"Telegram 發送失敗: {response.status_code}")
    except Exception as e:
        log(f"Telegram 發送錯誤: {e}")

def call_gemini(prompt):
    if not gemini_model:
        return "AI 服務未啟用"
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        log(f"Gemini 呼叫失敗: {str(e)[:100]}")
        return "AI 分析失敗，請稍後重試"

# ========== 4. 主執行邏輯 ==========
def run_monitor():
    start_time = time.time()
    log("🚀 啟動台股漲停板掃描系統...")
    log(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not supabase:
        log("⚠️ Supabase 連線失敗，將只進行掃描不儲存資料")

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

    total_stocks = len(stocks)
    log(f"開始掃描 {total_stocks} 檔股票...")

    found_count = 0
    limit_up_stocks = []
    error_count = 0

    symbols = [stock['symbol'] for stock in stocks]
    stock_dict = {stock['symbol']: stock for stock in stocks}

    batch_size = 150
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]

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
                            'is_rotc': stock_info['is_rotc']
                        }

                        # === 逐筆 AI 點評 ===
                        if gemini_model:
                            prompt = f"請用 50-80 字簡潔分析這檔台股：\n股票：{info['name']} ({symbol})\n產業：{info['sector']}\n今日漲幅：{ret:.2%}\n價格：{info['price']:.2f}\n請給出專業投資觀點或潛在催化劑。"
                            ai_comment = call_gemini(prompt)
                            info['ai_comment'] = ai_comment
                            log(f"✅ {info['name']} AI 點評完成")
                        else:
                            info['ai_comment'] = "AI 服務未啟用"

                        limit_up_stocks.append(info)

                        if supabase:
                            save_success = save_limit_up_stock(info)
                            if not save_success:
                                log(f"⚠️ 儲存 {symbol} 到資料庫失敗")

                        msg = (
                            f"🔥 *強勢股: {info['name']}* ({symbol})\n"
                            f"📈 漲幅: {ret:.2%}\n"
                            f"💵 價格: {curr_close:.2f}\n"
                            f"🏷️ 類別: {'興櫃' if info['is_rotc'] else '上市/上櫃'}\n"
                            f"📊 產業: {info['sector']}\n"
                            f"🤖 AI 點評: {info.get('ai_comment', '無')}"
                        )
                        send_telegram_msg(msg)
                        log(f"✅ 已推播: {info['name']} ({ret:.2%})")
                        found_count += 1

                except Exception as e:
                    error_count += 1
                    continue
        except Exception as e:
            log(f"批次 {batch_idx} 下載失敗: {e}")
            error_count += len(batch_symbols)
        time.sleep(1)

    # 計算時間與統計（保持不變）
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)

    # 結束通知（保持不變）
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

    # 統計報告（保持不變）
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
        sector_counts = {}
        for stock in limit_up_stocks:
            sector = stock['sector']
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        log("🏭 產業分佈:")
        for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            log(f" {sector}: {count}檔")
    log("="*60)

    # === 儲存市場總結（含 AI 總結） ===
    if supabase:
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            sector_counts = {}
            if limit_up_stocks:
                for stock in limit_up_stocks:
                    sector = stock['sector']
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1

            if found_count > 0:
                summary_content = f"今日掃描 {total_stocks} 檔股票，發現 {found_count} 檔漲停板股票。\n\n"
                if sector_counts:
                    summary_content += "產業分佈：\n"
                    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
                        summary_content += f"- {sector}: {count}檔\n"
            else:
                summary_content = f"今日掃描 {total_stocks} 檔股票，**無任何股票達到漲停標準**。\n\n市場整體表現平淡，無明顯強勢族群。"

            # === 總結 AI 分析（如果有漲停） ===
            if found_count > 0 and gemini_model:
                log("開始產生當日漲停總結 AI 分析...")
                summary_prompt = f"""請用 150-250 字專業台股分析師口吻，總結今日漲停板情況：
漲停家數：{found_count} 家
熱門產業：{', '.join([s for s, c in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:3]])}
請強調市場情緒、資金流向、潛在機會與風險。」
                ai_summary = call_gemini(summary_prompt)
                summary_content += f"\n\n🤖 AI 總結：\n{ai_summary}"
                log("✅ 已產生總結 AI 分析")
            else:
                summary_content += "\n\n🤖 AI 總結：今日無漲停股票，市場較平淡。"

            # 儲存
            safe_data = {
                "analysis_date": today_str,
                "stock_count": total_stocks,
                "summary_content": summary_content,
                "stock_list": ", ".join([s['name'] + '(' + s['symbol'] + ')' for s in limit_up_stocks]) if limit_up_stocks else "無",
                "created_at": datetime.now().isoformat()
            }
            supabase.table("daily_market_summary").upsert(safe_data).execute()
            log("✅ 已儲存市場總結到 daily_market_summary（含 AI 總結）")
        except Exception as e:
            log(f"❌ 儲存市場總結失敗: {str(e)[:100]}")

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        log("\n⚠️ 程式被使用者中斷")
        send_telegram_msg("⏹️ *程式被使用者中斷*")
    except Exception as e:
        log(f"❌ 程式執行錯誤: {e}")
        send_telegram_msg(f"❌ *程式執行錯誤*\n錯誤訊息: {str(e)[:100]}")

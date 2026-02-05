# -*- coding: utf-8 -*-
import time
import random
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf
from tqdm import tqdm

from logger import log
from utils import clean_markdown
from stock_sources import get_taiwan_stock_list

warnings.filterwarnings("ignore")


# =============================================================================
# Notifications
# =============================================================================
def send_basic_notification(tg, stocks: List[dict]):
    """當 AI 關閉或不可用時的簡易推播"""
    if not stocks:
        return

    log("📤 發送基本漲停通知...")
    msg = f"📊 *今日漲停板 ({len(stocks)}檔)*\n\n"

    sector_groups: Dict[str, List[dict]] = {}
    for s in stocks:
        sector_groups.setdefault(s.get("sector", "其他"), []).append(s)

    for sector, sector_stocks in sector_groups.items():
        msg += f"🏭 *{sector}* ({len(sector_stocks)}檔):\n"
        for st in sector_stocks[:3]:
            code = st["symbol"].split(".")[0]
            msg += (
                f"  • [{st['name']}({st['symbol']})]"
                f"(https://www.wantgoo.com/stock/{code}/technical-chart): {st['return']:.2%}\n"
            )
        if len(sector_stocks) > 3:
            msg += f"   ...還有 {len(sector_stocks)-3} 檔\n"
        msg += "\n"

    tg.send(msg)


def send_layered_notifications(tg, stocks: List[dict], sector_analyses: Dict[str, str], market_summary: Optional[str]):
    """AI 分層推播：個股→產業→市場"""
    if not stocks:
        return

    # 1) 個股（最多 10）
    log("📤 發送個股推播通知...")
    top = sorted(stocks, key=lambda x: x.get("consecutive_days", 1), reverse=True)[:10]

    for s in top:
        days = s.get("consecutive_days", 1)
        code = s["symbol"].split(".")[0]

        if days >= 3:
            emoji, pr = "🚀🚀🚀", "🔥🔥🔥"
        elif days == 2:
            emoji, pr = "🚀🚀", "🔥🔥"
        else:
            emoji, pr = "🚀", "🔥"

        ai_preview = (s.get("ai_comment") or "")[:100]
        msg = (
            f"{emoji} *{pr} 強勢股: {s['name']}* ({s['symbol']})\n"
            f"📈 漲幅: {s['return']:.2%} | 連板: {days}天\n"
            f"💵 價格: {s['price']:.2f}\n"
            f"🏷️ 類別: {'興櫃' if s.get('is_rotc') else '上市/上櫃'}\n"
            f"📊 產業: {s.get('sector','')}\n"
            f"🔗 分析: [玩股網](https://www.wantgoo.com/stock/{code}/technical-chart)"
        )
        if ai_preview:
            msg += f"\n🤖 AI: {clean_markdown(ai_preview)}..."
        tg.send(msg, delay=0.2)

    # 2) 產業（最多 5）
    if sector_analyses:
        log("📤 發送產業趨勢推播...")
        for sector, analysis in list(sector_analyses.items())[:5]:
            cnt = len([x for x in stocks if x.get("sector") == sector])
            msg = (
                f"🏭 *產業趨勢: {sector}*\n"
                f"📊 漲停家數: {cnt}家\n"
                f"🤖 AI分析: {clean_markdown((analysis or '')[:200])}..."
            )
            tg.send(msg, delay=0.2)

    # 3) 市場總結
    if market_summary:
        log("📤 發送市場總結推播...")
        total = len(stocks)
        rotc = sum(1 for s in stocks if s.get("is_rotc"))
        main = total - rotc
        avg_days = (sum(s.get("consecutive_days", 1) for s in stocks) / total) if total else 0

        strongest = max(stocks, key=lambda x: x.get("consecutive_days", 1)) if stocks else None
        if strongest:
            code = strongest["symbol"].split(".")[0]
            msg = (
                f"📊 *今日市場AI總結*\n"
                f"📈 總漲停: {total}檔\n"
                f"📊 上市櫃: {main} | 興櫃: {rotc}\n"
                f"📅 平均連板: {avg_days:.1f}天\n"
                f"👑 最強股: {strongest['name']}({strongest.get('consecutive_days',1)}連板) "
                f"[分析](https://www.wantgoo.com/stock/{code}/technical-chart)\n"
                f"🤖 市場分析: {clean_markdown(market_summary[:300])}..."
            )
        else:
            msg = (
                f"📊 *今日市場AI總結*\n"
                f"📈 總漲停: {total}檔\n"
                f"📊 上市櫃: {main} | 興櫃: {rotc}\n"
                f"📅 平均連板: {avg_days:.1f}天\n"
                f"🤖 市場分析: {clean_markdown(market_summary[:300])}..."
            )
        tg.send(msg, delay=0.2)


# =============================================================================
# Helpers
# =============================================================================
def _cfg_get(cfg: dict, key: str, default):
    v = cfg.get(key)
    return default if v is None else v


def _should_run_ai(cfg: dict, ai_service) -> Tuple[bool, bool, bool]:
    """
    決定是否跑 AI（總開關 + 子開關）
    你可以在 .env / cfg 用：
      ENABLE_AI, ENABLE_AI_INDIVIDUAL, ENABLE_AI_SECTOR, ENABLE_AI_MARKET
    """
    enable_ai = bool(_cfg_get(cfg, "ENABLE_AI", True))
    if not enable_ai:
        return False, False, False

    if not ai_service or not ai_service.is_ready():
        return False, False, False

    ind = bool(_cfg_get(cfg, "ENABLE_AI_INDIVIDUAL", True))
    sec = bool(_cfg_get(cfg, "ENABLE_AI_SECTOR", True))
    mkt = bool(_cfg_get(cfg, "ENABLE_AI_MARKET", True))
    return ind, sec, mkt


def _detect_limit_up(ret: float, is_rotc: bool, cfg: dict) -> bool:
    main_th = float(_cfg_get(cfg, "MAIN_BOARD_THRESHOLD", 0.098))
    rotc_th = float(_cfg_get(cfg, "ROTC_THRESHOLD", 0.10))
    th = rotc_th if is_rotc else main_th
    return ret >= th


def _sleep_range(cfg: dict, key_min: str, key_max: str, default_min: float, default_max: float):
    a = float(_cfg_get(cfg, key_min, default_min))
    b = float(_cfg_get(cfg, key_max, default_max))
    time.sleep(random.uniform(a, b))


def _chunk(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


# =============================================================================
# Main
# =============================================================================
def run_monitor(cfg: dict, tg, db_repo, ai_service):
    """
    cfg: dict（從 load_config 來 / 或你自己組）
      建議包含：
        BATCH_SIZE, REQUEST_DELAY
        MAIN_BOARD_THRESHOLD, ROTC_THRESHOLD
        ENABLE_AI, ENABLE_AI_INDIVIDUAL, ENABLE_AI_SECTOR, ENABLE_AI_MARKET
        AI_COOLDOWN_MIN/MAX, AI_SECTOR_COOLDOWN_MIN/MAX
    """
    start = time.time()
    log("🚀 啟動台股漲停板掃描系統（整合版 monitor.py）...")
    log(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    db_ready = bool(db_repo and db_repo.is_ready())
    if not db_ready:
        log("⚠️ Supabase 連線失敗，將只進行掃描不儲存資料")

    # AI 開關判斷（由 cfg + ai_service 決定）
    ai_ind, ai_sec, ai_mkt = _should_run_ai(cfg, ai_service)
    log(f"⚙️ AI 狀態: individual={ai_ind}, sector={ai_sec}, market={ai_mkt}")

    # 取股票清單
    stocks = get_taiwan_stock_list()
    if not stocks:
        log("❌ 無法獲取股票清單，程序終止")
        tg.send("❌ *股票監控失敗*\n無法獲取股票清單")
        return

    tg.send(
        f"🔔 *台股漲停板掃描啟動*\n"
        f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"標的總數: {len(stocks)}"
    )

    symbols = [s["symbol"] for s in stocks]
    stock_dict = {s["symbol"]: s for s in stocks}

    batch_size = int(_cfg_get(cfg, "BATCH_SIZE", 100))
    request_delay = float(_cfg_get(cfg, "REQUEST_DELAY", 1.5))
    batches = _chunk(symbols, batch_size)
    log(f"分成 {len(batches)} 個批次進行掃描... (batch_size={batch_size})")

    found_count = 0
    error_count = 0
    limit_up_stocks: List[dict] = []

    # =========================
    # 掃描漲停
    # =========================
    for batch_idx, batch_symbols in enumerate(tqdm(batches, desc="批次進度", unit="batch")):
        try:
            if batch_idx > 0:
                time.sleep(random.uniform(request_delay * 0.8, request_delay * 1.2))

            df_batch = yf.download(
                batch_symbols,
                period="2d",
                progress=False,
                group_by="ticker",
                threads=False,
                timeout=30,
            )

            for symbol in batch_symbols:
                try:
                    stock_info = stock_dict[symbol]

                    # yfinance 批量欄位存在性檢查
                    if symbol not in df_batch.columns.levels[0]:
                        error_count += 1
                        continue

                    df = df_batch[symbol]
                    if df.empty or "Close" not in df.columns:
                        error_count += 1
                        continue

                    close_data = df["Close"].dropna()
                    if len(close_data) < 2:
                        error_count += 1
                        continue

                    curr_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    if pd.isna(curr_close) or pd.isna(prev_close) or prev_close == 0:
                        error_count += 1
                        continue

                    ret = float((curr_close / prev_close) - 1)
                    is_rotc = bool(stock_info.get("is_rotc"))

                    if not _detect_limit_up(ret, is_rotc, cfg):
                        continue

                    info = {
                        "symbol": symbol,
                        "name": stock_info.get("name", ""),
                        "sector": stock_info.get("sector", ""),
                        "return": ret,
                        "price": float(curr_close),
                        "is_rotc": is_rotc,
                        "consecutive_days": 1,
                    }
                    limit_up_stocks.append(info)
                    found_count += 1

                    # 1) 先存基本資料（不含 AI）
                    if db_ready:
                        db_repo.save_stock_with_analysis(info)
                        log(f"📍 DB 已即時同步: {symbol}")

                    # 2) 個股 AI（受開關控制）
                    ai_comment = ""
                    if ai_ind:
                        ai_comment = "AI 分析處理中，請稍後查看儀表板。"
                        res = ai_service.analyze_individual(info)
                        if res:
                            ai_comment = res
                            info["ai_comment"] = ai_comment
                            if db_ready:
                                db_repo.save_stock_with_analysis(info)

                        # ✅ 只有真的打 AI 才冷卻
                        _sleep_range(cfg, "AI_COOLDOWN_MIN", "AI_COOLDOWN_MAX", 6.0, 9.0)

                    # 3) Telegram 通知（關 AI 也照發）
                    try:
                        code = symbol.split(".")[0]
                        dashboard_url = _cfg_get(
                            cfg,
                            "DASHBOARD_URL",
                            "https://tw-stock-intraday-monitor-d4wusvuh9sys8uumcdwms3.streamlit.app/%E5%80%8B%E8%82%A1AI%E5%88%86%E6%9E%90",
                        )
                        safe_ai = clean_markdown((ai_comment or "")[:150])
                        emoji = "🚀" if not is_rotc else "🧧"

                        msg = (
                            f"{emoji} *發現漲停強勢股: {info['name']}* ({symbol})\n"
                            f"📈 漲幅: {ret:.2%} | 💵 價格: {info['price']:.2f}\n"
                            f"🏭 產業: {info['sector']}\n"
                            + (f"🤖 AI點評: {safe_ai}...\n\n" if safe_ai else "\n")
                            + f"🔗 [查看網頁儀表板]({dashboard_url})\n"
                            f"📊 [玩股網K線](https://www.wantgoo.com/stock/{code}/technical-chart)"
                        )
                        tg.send(msg, delay=1.0)
                        log(f"📤 Telegram 推播完成: {symbol}")
                    except Exception as e:
                        log(f"❌ Telegram 發送流程失敗 {symbol}: {e}")

                except Exception:
                    error_count += 1
                    continue

        except Exception as e:
            log(f"批次 {batch_idx} 下載失敗: {str(e)[:120]}")
            error_count += len(batch_symbols)
            time.sleep(random.uniform(3.0, 5.0))

    log(f"掃描完成，發現 {found_count} 檔漲停股票")

    # ✅ 再保險一次：確保全部基本資料都在 DB
    if limit_up_stocks and db_ready:
        log(f"💾 先寫入 {len(limit_up_stocks)} 檔漲停基本資料（不含 AI）")
        for st in limit_up_stocks:
            try:
                db_repo.save_stock_with_analysis(st)
            except Exception as e:
                log(f"⚠️ 初始存檔失敗 {st.get('symbol')}: {e}")

    # =========================
    # AI 分析階段（產業/市場）
    # =========================
    sector_analyses: Dict[str, str] = {}
    market_summary: Optional[str] = None

    if limit_up_stocks and (ai_sec or ai_mkt):
        # 連板天數（不打 AI）
        if db_ready:
            log("📅 計算連續漲停天數...")
            for st in limit_up_stocks:
                try:
                    st["consecutive_days"] = db_repo.get_consecutive_limit_up_days(st["symbol"])
                except Exception:
                    st["consecutive_days"] = 1

        # 產業 AI
        if ai_sec:
            log("🏭 進行產業AI分析...")
            sector_groups: Dict[str, List[dict]] = {}
            for st in limit_up_stocks:
                sector_groups.setdefault(st.get("sector", "其他"), []).append(st)

            for sector, stocks_in_sector in sector_groups.items():
                if len(stocks_in_sector) <= 1:
                    continue

                analysis = ai_service.analyze_sector(sector, stocks_in_sector)
                if analysis:
                    sector_analyses[sector] = analysis
                    if db_ready:
                        db_repo.save_sector_analysis(sector, stocks_in_sector, analysis)

                _sleep_range(cfg, "AI_SECTOR_COOLDOWN_MIN", "AI_SECTOR_COOLDOWN_MAX", 12.0, 15.0)

        # 市場 AI
        if ai_mkt:
            market_summary = ai_service.analyze_market(limit_up_stocks)

        # 分層推播（即使 market_summary=None 也推個股/產業）
        send_layered_notifications(tg, limit_up_stocks, sector_analyses, market_summary)

        # DB：市場總結
        if market_summary and db_ready:
            try:
                db_repo.upsert_daily_market_summary(len(stocks), limit_up_stocks, market_summary)
            except Exception as e:
                log(f"更新市場總結失敗: {e}")

    else:
        if limit_up_stocks:
            log("⚠️ AI 已關閉或不可用，跳過 AI 分析階段")
            send_basic_notification(tg, limit_up_stocks)

    # =========================
    # 結束通知
    # =========================
    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    msg_end = (
        f"🏁 *掃描任務結束*\n"
        f"⏱️ 執行時間: {minutes}分{seconds}秒\n"
        f"✅ 總掃描: {len(stocks)} 檔\n"
        f"✅ 發現漲停: {found_count} 檔\n"
        f"⚠️ 錯誤數量: {error_count} 個"
    )

    if limit_up_stocks:
        msg_end += f"\n\n📊 今日漲停板 ({len(limit_up_stocks)}檔):"
        sorted_stocks = sorted(limit_up_stocks, key=lambda x: x.get("consecutive_days", 1), reverse=True)
        for i, st in enumerate(sorted_stocks[:10], 1):
            days = st.get("consecutive_days", 1)
            code = st["symbol"].split(".")[0]
            msg_end += (
                f"\n{i}. [{st['name']}({st['symbol']})]"
                f"(https://www.wantgoo.com/stock/{code}/technical-chart): {st['return']:.2%} [{days}連板]"
            )

    tg.send(msg_end)

    log("=" * 60)
    log("📊 掃描統計報告")
    log(f"總股票數: {len(stocks)}")
    log(f"錯誤數量: {error_count}")
    log(f"漲停板數: {found_count}")
    log(f"執行時間: {minutes}分{seconds}秒")
    log("=" * 60)

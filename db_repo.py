# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
from logger import log

try:
    from supabase import create_client
except Exception:
    create_client = None


class DBRepo:
    def __init__(self, url: str | None, key: str | None):
        self.url = url
        self.key = key
        self.client = None

        if url and key and create_client:
            try:
                self.client = create_client(url, key)
                log("✅ Supabase 初始化成功")
            except Exception as e:
                log(f"❌ Supabase 初始化失敗: {e}")
                self.client = None
        else:
            log("⚠️ Supabase 環境變數未設置或套件不可用")

    def is_ready(self) -> bool:
        return self.client is not None

    def save_stock_with_analysis(self, stock_info: dict) -> bool:
        if not self.is_ready():
            return False
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            data = {
                "analysis_date": today_str,
                "symbol": stock_info["symbol"],
                "stock_name": stock_info["name"],
                "sector": stock_info.get("sector", ""),
                "return_rate": stock_info.get("return", 0),
                "price": stock_info.get("price", 0),
                "is_rotc": stock_info.get("is_rotc", False),
                "ai_comment": stock_info.get("ai_comment", ""),
                "consecutive_days": stock_info.get("consecutive_days", 1),
                "volume_ratio": stock_info.get("volume_ratio"),
                "created_at": datetime.now().isoformat(),
            }
            self.client.table("individual_stock_analysis").upsert(
                data, on_conflict="analysis_date,symbol"
            ).execute()
            return True
        except Exception as e:
            log(f"儲存股票分析失敗 {stock_info.get('symbol')}: {e}")
            return False

    def save_sector_analysis(self, sector_name: str, stocks_in_sector: list[dict], ai_analysis: str) -> bool:
        if not self.is_ready():
            return False
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            data = {
                "analysis_date": today_str,
                "sector_name": sector_name,
                "stock_count": len(stocks_in_sector),
                "stocks_included": json.dumps([s["symbol"] for s in stocks_in_sector]),
                "ai_analysis": ai_analysis,
                "created_at": datetime.now().isoformat(),
            }
            self.client.table("sector_analysis").upsert(data).execute()
            return True
        except Exception as e:
            log(f"儲存產業分析失敗 {sector_name}: {e}")
            return False

    def get_consecutive_limit_up_days(self, symbol: str, main_threshold: float, rotc_threshold: float) -> int:
        """
        查詢最近 5 天連續漲停天數（用 DB 既有紀錄）
        """
        if not self.is_ready():
            return 1
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            five_days_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")

            resp = (
                self.client.table("individual_stock_analysis")
                .select("analysis_date, return_rate, is_rotc")
                .eq("symbol", symbol)
                .gte("analysis_date", five_days_ago)
                .lte("analysis_date", today)
                .order("analysis_date", desc=False)
                .execute()
            )
            if not resp.data:
                return 1

            sorted_records = sorted(resp.data, key=lambda x: x["analysis_date"])
            consecutive = 0
            for r in sorted_records[-5:]:
                rr = r.get("return_rate")
                is_rotc = bool(r.get("is_rotc", False))
                threshold = rotc_threshold if is_rotc else main_threshold
                if rr is None:
                    break
                try:
                    if float(rr) >= threshold:
                        consecutive += 1
                    else:
                        break
                except Exception:
                    break

            return max(consecutive, 1)
        except Exception as e:
            log(f"查詢連續漲停天數失敗 {symbol}: {e}")
            return 1

    def upsert_daily_market_summary(self, total_stocks: int, limit_up_stocks: list[dict], market_summary: str):
        if not self.is_ready():
            return
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            safe_data = {
                "analysis_date": today_str,
                "stock_count": total_stocks,
                "summary_content": market_summary[:5000],
                "stock_list": ", ".join([f"{s['name']}({s['symbol']})" for s in limit_up_stocks]) if limit_up_stocks else "無",
                "created_at": datetime.now().isoformat(),
            }
            self.client.table("daily_market_summary").upsert(safe_data).execute()
        except Exception as e:
            log(f"更新市場總結失敗: {e}")

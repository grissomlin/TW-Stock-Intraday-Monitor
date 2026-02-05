# -*- coding: utf-8 -*-
from logger import log

class AIService:
    def __init__(self, cfg: dict, db_repo):
        self.cfg = cfg
        self.db_repo = db_repo

        self.enable_individual = bool(cfg.get("ENABLE_AI_INDIVIDUAL"))
        self.enable_sector = bool(cfg.get("ENABLE_AI_SECTOR"))
        self.enable_market = bool(cfg.get("ENABLE_AI_MARKET"))

        self._analyzer = None

        gemini_key = cfg.get("GEMINI_API_KEY")
        if not (cfg.get("ENABLE_AI") and gemini_key):
            return

        try:
            from ai_analyzer import StockAIAnalyzer
            self._analyzer = StockAIAnalyzer(gemini_key, db_repo.client if db_repo else None)
            if hasattr(self._analyzer, "is_available") and not self._analyzer.is_available():
                log("⚠️ AI分析器部分功能不可用")
                self._analyzer = None
            else:
                log("✅ AI分析器初始化成功")
        except Exception as e:
            log(f"❌ AI分析器初始化失敗: {e}")
            self._analyzer = None

    def is_ready(self) -> bool:
        return self._analyzer is not None

    def analyze_individual(self, info: dict) -> str | None:
        if not self.is_ready():
            return None
        try:
            return self._analyzer.analyze_individual_stock(info)
        except Exception as e:
            log(f"⚠️ 個股 AI 失敗 {info.get('symbol')}: {str(e)[:80]}")
            return None

    def analyze_sector(self, sector: str, stocks_in_sector: list[dict]) -> str | None:
        if not self.is_ready():
            return None
        try:
            return self._analyzer.analyze_sector(sector, stocks_in_sector)
        except Exception as e:
            log(f"⚠️ 產業 AI 失敗 {sector}: {str(e)[:80]}")
            return None

    def analyze_market(self, limit_up_stocks: list[dict]) -> str | None:
        if not self.is_ready():
            return None
        try:
            return self._analyzer.analyze_market_summary(limit_up_stocks)
        except Exception as e:
            log(f"⚠️ 市場 AI 失敗: {str(e)[:80]}")
            return None

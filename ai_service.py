# -*- coding: utf-8 -*-
from logger import log

class AIService:
    def __init__(self, Config, db_repo):
        self.Config = Config
        self.db_repo = db_repo
        self.ai_analyzer = None

        self.enabled = bool(Config.ENABLE_AI)
        self.enable_individual = bool(Config.ENABLE_AI_INDIVIDUAL)
        self.enable_sector = bool(Config.ENABLE_AI_SECTOR)
        self.enable_market = bool(Config.ENABLE_AI_MARKET)

        if not self.enabled:
            print("⛔ ENABLE_AI=OFF：不初始化 AI 分析器")
            return

        api_key = Config.GEMINI_API_KEY
        if not api_key:
            print("⚠️ GEMINI_API_KEY 未設置：不初始化 AI 分析器")
            return

        try:
            from ai_analyzer import StockAIAnalyzer
            self.ai_analyzer = StockAIAnalyzer(
                api_key,
                db_repo.client if db_repo and db_repo.is_ready() else None
            )
            if self.ai_analyzer and self.ai_analyzer.is_available():
                print("✅ AI分析器初始化成功")
            else:
                print("⚠️ AI分析器部分功能不可用")
                self.ai_analyzer = None
        except Exception as e:
            print(f"❌ AI分析器初始化失敗: {e}")
            self.ai_analyzer = None

    def is_ready(self) -> bool:
        return self.enabled and (self.ai_analyzer is not None) and self.ai_analyzer.is_available()

    def analyze_individual(self, info: dict) -> str | None:
        if not (self.is_ready() and self.enable_individual):
            return None
        try:
            log(f"🤖 正在為 {info.get('symbol')} 請求 AI 個股分析...")
            return self.ai_analyzer.analyze_individual_stock(info)
        except Exception as e:
            log(f"⚠️ AI 個股分析失敗 {info.get('symbol')}: {str(e)[:120]}")
            return None

    def analyze_sector(self, sector: str, stocks_in_sector: list[dict]) -> str | None:
        if not (self.is_ready() and self.enable_sector):
            return None
        try:
            log(f"🧠 正在分析產業: {sector} ({len(stocks_in_sector)}檔)...")
            return self.ai_analyzer.analyze_sector(sector, stocks_in_sector)
        except Exception as e:
            log(f"⚠️ 產業AI分析失敗 {sector}: {str(e)[:120]}")
            return None

    def analyze_market(self, limit_up_stocks: list[dict]) -> str | None:
        if not (self.is_ready() and self.enable_market):
            return None
        try:
            log("📊 進行市場AI分析...")
            return self.ai_analyzer.analyze_market_summary(limit_up_stocks)
        except Exception as e:
            log(f"⚠️ 市場AI分析失敗: {str(e)[:120]}")
            return None

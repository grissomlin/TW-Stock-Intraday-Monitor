# -*- coding: utf-8 -*-
"""
app_config.py - 設定檔（整合版）
- 讀取 .env
- Supabase / Telegram / Gemini
- AI 開關（總開關 + 子開關）
- 漲停閾值 / 批次 / 延遲
- ✅提供 load_config() 給 main_pipeline.py 使用
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


class Config:
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # AI switches
    ENABLE_AI = _env_bool("ENABLE_AI", default=True)
    ENABLE_AI_INDIVIDUAL = _env_bool("ENABLE_AI_INDIVIDUAL", default=True)
    ENABLE_AI_SECTOR = _env_bool("ENABLE_AI_SECTOR", default=True)
    ENABLE_AI_MARKET = _env_bool("ENABLE_AI_MARKET", default=True)

    # thresholds
    MAIN_BOARD_THRESHOLD = _env_float("MAIN_BOARD_THRESHOLD", 0.098)
    ROTC_THRESHOLD = _env_float("ROTC_THRESHOLD", 0.10)

    # batching / pacing
    BATCH_SIZE = _env_int("BATCH_SIZE", 100)  # 你原本也用 100
    REQUEST_DELAY_MIN = _env_float("REQUEST_DELAY_MIN", 1.0)
    REQUEST_DELAY_MAX = _env_float("REQUEST_DELAY_MAX", 2.5)

    # AI cooldown
    AI_COOLDOWN_MIN = _env_float("AI_COOLDOWN_MIN", 6.0)
    AI_COOLDOWN_MAX = _env_float("AI_COOLDOWN_MAX", 9.0)

    AI_SECTOR_COOLDOWN_MIN = _env_float("AI_SECTOR_COOLDOWN_MIN", 12.0)
    AI_SECTOR_COOLDOWN_MAX = _env_float("AI_SECTOR_COOLDOWN_MAX", 15.0)

    # dashboard
    DASHBOARD_URL = os.getenv(
        "DASHBOARD_URL",
        "https://tw-stock-intraday-monitor-d4wusvuh9sys8uumcdwms3.streamlit.app/%E5%80%8B%E8%82%A1AI%E5%88%86%E6%9E%90",
    )

    @classmethod
    def effective_ai_enabled(cls) -> bool:
        return bool(cls.ENABLE_AI) and bool(cls.GEMINI_API_KEY)

    @classmethod
    def debug_print(cls):
        print("🔧 Config 檢查：")
        print(f"  SUPABASE_URL: {'已設置' if cls.SUPABASE_URL else '未設置'}")
        print(f"  SUPABASE_KEY: {'已設置' if cls.SUPABASE_KEY else '未設置'}")
        print(f"  TELEGRAM_BOT_TOKEN: {'已設置' if cls.TELEGRAM_BOT_TOKEN else '未設置'}")
        print(f"  TELEGRAM_CHAT_ID: {'已設置' if cls.TELEGRAM_CHAT_ID else '未設置'}")
        print(f"  GEMINI_API_KEY: {'已設置' if cls.GEMINI_API_KEY else '未設置'}")
        print(f"  ENABLE_AI: {cls.ENABLE_AI}")
        print(f"  ENABLE_AI_INDIVIDUAL: {cls.ENABLE_AI_INDIVIDUAL}")
        print(f"  ENABLE_AI_SECTOR: {cls.ENABLE_AI_SECTOR}")
        print(f"  ENABLE_AI_MARKET: {cls.ENABLE_AI_MARKET}")
        print(f"  BATCH_SIZE: {cls.BATCH_SIZE}")
        print(f"  MAIN_BOARD_THRESHOLD: {cls.MAIN_BOARD_THRESHOLD}")
        print(f"  ROTC_THRESHOLD: {cls.ROTC_THRESHOLD}")


def load_config() -> dict:
    """
    統一回傳 dict，並提供 main_pipeline 會用到的 keys
    """
    return {
        "SUPABASE_URL": Config.SUPABASE_URL,
        "SUPABASE_KEY": Config.SUPABASE_KEY,
        "TG_TOKEN": Config.TELEGRAM_BOT_TOKEN,
        "TG_CHAT_ID": Config.TELEGRAM_CHAT_ID,
        "GEMINI_API_KEY": Config.GEMINI_API_KEY,

        "ENABLE_AI": Config.ENABLE_AI,
        "ENABLE_AI_INDIVIDUAL": Config.ENABLE_AI_INDIVIDUAL,
        "ENABLE_AI_SECTOR": Config.ENABLE_AI_SECTOR,
        "ENABLE_AI_MARKET": Config.ENABLE_AI_MARKET,

        "MAIN_BOARD_THRESHOLD": Config.MAIN_BOARD_THRESHOLD,
        "ROTC_THRESHOLD": Config.ROTC_THRESHOLD,

        "BATCH_SIZE": Config.BATCH_SIZE,
        "REQUEST_DELAY_MIN": Config.REQUEST_DELAY_MIN,
        "REQUEST_DELAY_MAX": Config.REQUEST_DELAY_MAX,

        "AI_COOLDOWN_MIN": Config.AI_COOLDOWN_MIN,
        "AI_COOLDOWN_MAX": Config.AI_COOLDOWN_MAX,
        "AI_SECTOR_COOLDOWN_MIN": Config.AI_SECTOR_COOLDOWN_MIN,
        "AI_SECTOR_COOLDOWN_MAX": Config.AI_SECTOR_COOLDOWN_MAX,

        "DASHBOARD_URL": Config.DASHBOARD_URL,
    }

# -*- coding: utf-8 -*-
"""
config.py - 設定檔（整合版）
✅ 自證版：一載入就印出自己的檔案路徑，避免 import 到別的 config.py
"""

import os
from dotenv import load_dotenv

print(f"✅ LOADING config.py FROM: {__file__}", flush=True)

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
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    ENABLE_AI = _env_bool("ENABLE_AI", default=True)
    ENABLE_AI_INDIVIDUAL = _env_bool("ENABLE_AI_INDIVIDUAL", default=True)
    ENABLE_AI_SECTOR = _env_bool("ENABLE_AI_SECTOR", default=True)
    ENABLE_AI_MARKET = _env_bool("ENABLE_AI_MARKET", default=True)

    MAIN_BOARD_THRESHOLD = _env_float("MAIN_BOARD_THRESHOLD", 0.098)
    ROTC_THRESHOLD = _env_float("ROTC_THRESHOLD", 0.10)

    BATCH_SIZE = _env_int("BATCH_SIZE", 120)
    REQUEST_DELAY = _env_float("REQUEST_DELAY", 1.5)

    AI_COOLDOWN_MIN = _env_float("AI_COOLDOWN_MIN", 6.0)
    AI_COOLDOWN_MAX = _env_float("AI_COOLDOWN_MAX", 9.0)
    AI_SECTOR_COOLDOWN_MIN = _env_float("AI_SECTOR_COOLDOWN_MIN", 12.0)
    AI_SECTOR_COOLDOWN_MAX = _env_float("AI_SECTOR_COOLDOWN_MAX", 15.0)

    DASHBOARD_URL = os.getenv(
        "DASHBOARD_URL",
        "https://tw-stock-intraday-monitor-d4wusvuh9sys8uumcdwms3.streamlit.app/%E5%80%8B%E8%82%A1AI%E5%88%86%E6%9E%90",
    )


def load_config() -> dict:
    cfg = {
        "SUPABASE_URL": Config.SUPABASE_URL,
        "SUPABASE_KEY": Config.SUPABASE_KEY,

        # main_pipeline.py 用 TG_TOKEN/TG_CHAT_ID
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
        "REQUEST_DELAY": Config.REQUEST_DELAY,

        "AI_COOLDOWN_MIN": Config.AI_COOLDOWN_MIN,
        "AI_COOLDOWN_MAX": Config.AI_COOLDOWN_MAX,
        "AI_SECTOR_COOLDOWN_MIN": Config.AI_SECTOR_COOLDOWN_MIN,
        "AI_SECTOR_COOLDOWN_MAX": Config.AI_SECTOR_COOLDOWN_MAX,

        "DASHBOARD_URL": Config.DASHBOARD_URL,
    }
    return cfg


__all__ = ["Config", "load_config"]
print("✅ config.py export OK: load_config exists =", callable(load_config), flush=True)

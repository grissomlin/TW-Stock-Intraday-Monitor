# -*- coding: utf-8 -*-
"""
config.py - 設定檔（整合版）
- 讀取 .env
- Supabase / Telegram / Gemini
- AI 開關（總開關 + 子開關）
- 漲停閾值 / 批次 / 延遲
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """解析 .env 布林值：1/true/yes/on/y => True；0/false/no/off/n => False"""
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
    """設定類（整合版）"""

    # =========================
    # Supabase
    # =========================
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    # =========================
    # Telegram
    # =========================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # =========================
    # AI (Gemini)
    # =========================
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # ✅ AI 開關（你要先關 AI 給別的 repo 用，就設 ENABLE_AI=0）
    ENABLE_AI = _env_bool("ENABLE_AI", default=True)

    # ✅ 子開關：可更細控制（沒設就跟著總開關）
    ENABLE_AI_INDIVIDUAL = _env_bool("ENABLE_AI_INDIVIDUAL", default=True)  # 逐檔個股 AI
    ENABLE_AI_SECTOR = _env_bool("ENABLE_AI_SECTOR", default=True)          # 產業 AI
    ENABLE_AI_MARKET = _env_bool("ENABLE_AI_MARKET", default=True)          # 市場總結 AI

    # =========================
    # 漲停閾值
    # =========================
    MAIN_BOARD_THRESHOLD = _env_float("MAIN_BOARD_THRESHOLD", 0.098)  # 上市/上櫃
    ROTC_THRESHOLD = _env_float("ROTC_THRESHOLD", 0.10)              # 興櫃

    # =========================
    # 批次設定 / 下載節奏
    # =========================
    BATCH_SIZE = _env_int("BATCH_SIZE", 150)

    # 批次間隔（避免 Yahoo Finance / TWSE 被擋）
    REQUEST_DELAY = _env_float("REQUEST_DELAY", 1.0)

    # 若你在「逐檔 AI」階段要 sleep (保護 RPM)
    AI_COOLDOWN_MIN = _env_float("AI_COOLDOWN_MIN", 6.0)
    AI_COOLDOWN_MAX = _env_float("AI_COOLDOWN_MAX", 9.0)

    # 產業分析每次間隔（保護 RPM）
    AI_SECTOR_COOLDOWN_MIN = _env_float("AI_SECTOR_COOLDOWN_MIN", 12.0)
    AI_SECTOR_COOLDOWN_MAX = _env_float("AI_SECTOR_COOLDOWN_MAX", 15.0)

    @classmethod
    def effective_ai_enabled(cls) -> bool:
        """總開關：一個地方統一判斷 AI 是否允許"""
        return bool(cls.ENABLE_AI) and bool(cls.GEMINI_API_KEY)

    @classmethod
    def effective_ai_individual(cls) -> bool:
        return cls.effective_ai_enabled() and bool(cls.ENABLE_AI_INDIVIDUAL)

    @classmethod
    def effective_ai_sector(cls) -> bool:
        return cls.effective_ai_enabled() and bool(cls.ENABLE_AI_SECTOR)

    @classmethod
    def effective_ai_market(cls) -> bool:
        return cls.effective_ai_enabled() and bool(cls.ENABLE_AI_MARKET)

    @classmethod
    def validate(cls, require_supabase: bool = False) -> bool:
        """
        驗證設定
        - require_supabase=False：Supabase 可選（沒設就只掃描不存）
        - Telegram token 建議必填（如果你要推播）
        """
        missing = []

        # Telegram（你原本 validate 只有 token；我也保留 chat_id 的檢查更合理）
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")

        # Supabase（可選）
        if require_supabase:
            if not cls.SUPABASE_URL:
                missing.append("SUPABASE_URL")
            if not cls.SUPABASE_KEY:
                missing.append("SUPABASE_KEY")

        if missing:
            raise ValueError(f"缺少環境變數: {', '.join(missing)}")

        return True

    @classmethod
    def debug_print(cls):
        """方便你啟動時印設定（不會印出 key 本身）"""
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
        print(f"  REQUEST_DELAY: {cls.REQUEST_DELAY}")
        print(f"  MAIN_BOARD_THRESHOLD: {cls.MAIN_BOARD_THRESHOLD}")
        print(f"  ROTC_THRESHOLD: {cls.ROTC_THRESHOLD}")

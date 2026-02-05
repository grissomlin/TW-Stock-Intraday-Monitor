# -*- coding: utf-8 -*-
import os
import sys

# 確保同資料夾可 import
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# ✅ 永遠優先用 app_config（避免 config.py 同名衝突）
try:
    from app_config import load_config
except Exception:
    # 兼容：如果你堅持要用 config.py，也能跑
    from config import load_config

from telegram_client import TelegramClient
from db_repo import DBRepo
from ai_service import AIService
from monitor import run_monitor


def main():
    cfg = load_config()

    print("🔧 環境變數檢查:")
    print(f"  SUPABASE_URL: {'已設置' if cfg.get('SUPABASE_URL') else '未設置'}")
    print(f"  SUPABASE_KEY: {'已設置' if cfg.get('SUPABASE_KEY') else '未設置'}")
    print(f"  TG_TOKEN: {'已設置' if cfg.get('TG_TOKEN') else '未設置'}")
    print(f"  TG_CHAT_ID: {'已設置' if cfg.get('TG_CHAT_ID') else '未設置'}")
    print(f"  GEMINI_API_KEY: {'已設置' if cfg.get('GEMINI_API_KEY') else '未設置'}")
    print(f"  ENABLE_AI: {cfg.get('ENABLE_AI')}")
    print(f"  ENABLE_AI_INDIVIDUAL: {cfg.get('ENABLE_AI_INDIVIDUAL')}")
    print(f"  ENABLE_AI_SECTOR: {cfg.get('ENABLE_AI_SECTOR')}")
    print(f"  ENABLE_AI_MARKET: {cfg.get('ENABLE_AI_MARKET')}")

    db_repo = DBRepo(cfg.get("SUPABASE_URL"), cfg.get("SUPABASE_KEY"))
    tg = TelegramClient(cfg.get("TG_TOKEN"), cfg.get("TG_CHAT_ID"))
    ai = AIService(cfg, db_repo)

    run_monitor(cfg, tg, db_repo, ai)


if __name__ == "__main__":
    main()

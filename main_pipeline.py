# -*- coding: utf-8 -*-
import os
import sys

# 確保同資料夾可 import
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import Config
from telegram_client import TelegramClient
from db_repo import DBRepo
from ai_service import AIService
from monitor import run_monitor


def main():
    # （可選）你要強制檢查 Telegram 一定要有就打開
    # Config.validate(require_supabase=False)

    Config.debug_print()

    db_repo = DBRepo(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    tg = TelegramClient(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
    ai = AIService(Config, db_repo)  # ✅ 這裡改成傳 Config 類

    run_monitor(tg, db_repo, ai)     # ✅ 這裡不再傳 cfg dict


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
設定檔
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """設定類"""
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # 漲停閾值
    MAIN_BOARD_THRESHOLD = 0.098  # 上市櫃
    ROTC_THRESHOLD = 0.10        # 興櫃
    
    # 批次設定
    BATCH_SIZE = 150
    REQUEST_DELAY = 1.0  # 批次間隔秒數
    
    @classmethod
    def validate(cls):
        """驗證設定"""
        missing = []
        for key in ['SUPABASE_URL', 'SUPABASE_KEY', 'TELEGRAM_BOT_TOKEN']:
            if not getattr(cls, key):
                missing.append(key)
        
        if missing:
            raise ValueError(f"缺少環境變數: {', '.join(missing)}")
        
        return True

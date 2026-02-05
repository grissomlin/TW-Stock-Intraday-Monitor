# -*- coding: utf-8 -*-
import time
import requests
from logger import log

class TelegramClient:
    def __init__(self, token: str | None, chat_id: str | None):
        self.token = token
        self.chat_id = chat_id

    def is_ready(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str, delay: float = 0.1):
        """發送訊息到 Telegram（帶延遲避免限流）"""
        if not self.is_ready():
            log("⚠️ Telegram 憑證未設置")
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                log("Telegram 訊息發送成功")
            elif resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                log(f"Telegram 限流，等待 {retry_after} 秒後重試")
                time.sleep(retry_after)
                requests.post(url, json=payload, timeout=10)
            else:
                log(f"Telegram 發送失敗: {resp.status_code}")
        except Exception as e:
            log(f"Telegram 發送錯誤: {e}")

        time.sleep(delay)

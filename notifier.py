import os
import html
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_alert(message: str):
    """Отправляет текстовое сообщение/алерт в Telegram с поддержкой HTML-разметки"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram token или chat_id не настроены в .env")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",  # Перешли на HTML, чтобы избежать ошибок парсинга Markdown
        "disable_web_page_preview": True  # Отключает громоздкое превью ссылок
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        # Если Telegram вернул ошибку, выводим подробности в консоль
        if not response.ok:
            print(f"❌ Ошибка Telegram API ({response.status_code}): {response.text}")

        response.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка отправки алертов в Telegram: {e}")


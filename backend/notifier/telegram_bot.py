
import requests
from backend.notifier.notifications_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={  # Используем json вместо data
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=5)
        print(f"Telegram API response: {response.status_code} {response.text}")  # Логирование
        return response.json()
    except Exception as e:
        print(f"Telegram send error: {str(e)}")
        return {"ok": False, "error": str(e)}
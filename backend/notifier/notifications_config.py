import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "") # укащать реальный токен бота
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "") #указать реальный чат ID
DATABASE_PATH = os.getenv("DATABASE_PATH", "/backend/database/database1.db") #указать реальный путь к дб
CHECK_INTERVAL_SECONDS = 1800  # 30 минут
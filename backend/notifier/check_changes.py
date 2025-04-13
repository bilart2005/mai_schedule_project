import sqlite3
from datetime import datetime, timedelta
from backend.notifier.telegram_bot import send_telegram_message
from backend.notifier.notifications_config import DATABASE_PATH
import os

print("\n" + "="*50)
print(f"🕒 Запуск проверки в {datetime.now()}")

# Проверка существования файла БД
if not os.path.exists(DATABASE_PATH):
    print(f"❌ Файл БД не найден по пути: {DATABASE_PATH}")
    exit(1)

try:
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    print(f"🔌 Подключено к БД: {DATABASE_PATH}")

    thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
    print(f"⏳ Ищем изменения после: {thirty_minutes_ago}")

    cursor.execute("""
        SELECT schedule_id, change_type, timestamp 
        FROM changes_log 
        WHERE timestamp > ?
        ORDER BY timestamp DESC
    """, (thirty_minutes_ago.strftime("%Y-%m-%d %H:%M:%S"),))
    
    changes = cursor.fetchall()
    conn.close()

    print(f"📊 Найдено изменений: {len(changes)}")
    
    if not changes:
        print("✅ Нет новых изменений")
        exit(0)

    message = "<b>🗓 Обнаружены изменения в расписании:</b>\n" + \
              "\n".join(f"• [{row[1].upper()}] Пара ID: {row[0]} в {row[2]}" for row in changes)
    
    print(f"✉️ Текст сообщения:\n{message}")
    
    result = send_telegram_message(message)
    if result.get('ok'):
        print("✅ Сообщение успешно отправлено!")
    else:
        print(f"❌ Ошибка отправки: {result}")

except Exception as e:
    print(f"🔥 Критическая ошибка: {str(e)}")
    raise
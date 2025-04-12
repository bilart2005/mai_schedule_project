import sqlite3
from datetime import datetime, timezone  # добавили timezone сюда
from backend.database.database import get_db_connection

DB_PATH = "/backend/database/database1.db"  # укажи реальный путь к БД

def insert_test_change():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now = datetime.now()  # или используй localtime, если все данные в local
    cursor.execute("""
        INSERT INTO changes_log (schedule_id, change_type, timestamp)
        VALUES (?, ?, ?)
    """, (999, 'update', now))

    conn.commit()
    conn.close()
    print(f"✅ Вставлено тестовое изменение с timestamp: {now}")

if __name__ == "__main__":
    insert_test_change()
import sqlite3
from datetime import datetime

DB_PATH = "/backend/database/database1.db"  # указать реальный путь к дб

def create_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS changes_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER,
            change_type TEXT CHECK( change_type IN ('create','update','delete') ),
            timestamp TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Таблица changes_log создана (или уже была).")

if __name__ == "__main__":
    create_table()

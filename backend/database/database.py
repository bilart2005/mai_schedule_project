import sqlite3

DB_PATH = "mai_schedule.db"


def create_tables():
    """Создает таблицы в БД, если их нет"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            link TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            week INTEGER,
            day TEXT,
            time TEXT,
            subject TEXT,
            teacher TEXT,
            room TEXT,
            FOREIGN KEY(group_name) REFERENCES groups(name)
        )
    ''')

    conn.commit()
    conn.close()


def save_groups(groups):
    """Сохраняет список групп в БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for group in groups:
        try:
            cursor.execute("INSERT INTO groups (name, link) VALUES (?, ?)", (group["name"], group["link"]))
        except sqlite3.IntegrityError:
            pass  # Игнорируем дубликаты

    conn.commit()
    conn.close()


def get_groups():
    """Возвращает список всех групп из БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, link FROM groups")
    groups = [{"name": row[0], "link": row[1]} for row in cursor.fetchall()]

    conn.close()
    return groups


def save_schedule(group_name, schedule):
    """Сохраняет расписание в БД"""
    conn = sqlite3.connect("mai_schedule.db")
    cursor = conn.cursor()

    if not schedule:
        print(f"⚠️ Нет данных для сохранения в БД для группы {group_name}.")
        return

    print(f"💾 Сохраняем {len(schedule)} занятий для {group_name}...")

    for lesson in schedule:
        cursor.execute('''
            INSERT INTO schedule (group_name, week, day, time, subject, teacher, room)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (group_name, lesson["week"], lesson["day"], lesson["time"],
              lesson["subject"], lesson["teacher"], lesson["room"]))

    conn.commit()
    conn.close()
    print(f"✅ Расписание для {group_name} успешно сохранено!")


def query_db(query, args=(), one=False):
    """
    Выполняет SQL-запрос и возвращает результат.
    """
    conn = sqlite3.connect("mai_schedule.db")
    cursor = conn.cursor()
    cursor.execute(query, args)
    result = cursor.fetchall()
    conn.close()
    return (result[0] if result else None) if one else result


def execute_db(query, args=()):
    """
    Выполняет SQL-запрос (INSERT, UPDATE, DELETE) и коммитит изменения.
    """
    conn = sqlite3.connect("mai_schedule.db")
    cursor = conn.cursor()
    cursor.execute(query, args)
    conn.commit()
    conn.close()


create_tables()

import sqlite3

DB_PATH = "mai_schedule.db"

def create_tables():
    """Создает таблицы в БД, если их нет, с расширенной схемой для расписания."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица групп
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            link TEXT
        )
    ''')

    # Таблица расписания с отдельными полями для времени и параметрами повторяемости
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            week INTEGER,
            day TEXT,
            start_time TEXT,         -- Время начала занятия
            end_time TEXT,           -- Время окончания занятия
            subject TEXT,
            teacher TEXT,
            room TEXT,
            event_type TEXT DEFAULT 'разовое',         -- Тип события: разовое/повторяющееся
            recurrence_pattern TEXT DEFAULT '',         -- Режим повторяемости (например, "каждую неделю" или "по верхней/нижней")
            google_event_id TEXT DEFAULT NULL,
            is_custom INTEGER DEFAULT 0,                -- Флаг пользовательского изменения (1 - изменено вручную)
            FOREIGN KEY(group_name) REFERENCES groups(name)
        )
    ''')

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')

    conn.commit()
    conn.close()


def save_groups(groups):
    """Сохраняет список групп в БД."""
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
    """Возвращает список всех групп из БД."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, link FROM groups")
    groups = [{"name": row[0], "link": row[1]} for row in cursor.fetchall()]

    conn.close()
    return groups


def save_schedule(group_name, schedule):
    """
    Сохраняет расписание для указанной группы.
    Ожидается, что schedule — список словарей с ключами:
      week, day, start_time, end_time, subject, teacher, room.
    Для данных, полученных с сайта, по умолчанию event_type='разовое' и recurrence_pattern='' .
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not schedule:
        print(f"⚠️ Нет данных для сохранения в БД для группы {group_name}.")
        return

    print(f"💾 Сохраняем {len(schedule)} занятий для {group_name}...")

    for lesson in schedule:
        # Здесь можно реализовать проверку на is_custom, чтобы не перезаписывать пользовательские изменения
        cursor.execute('''
            INSERT INTO schedule (
                group_name, week, day, start_time, end_time, subject, teacher, room, event_type, recurrence_pattern
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            group_name,
            lesson["week"],
            lesson["day"],
            lesson.get("start_time", "Неизвестно"),
            lesson.get("end_time", "Неизвестно"),
            lesson["subject"],
            lesson["teacher"],
            lesson["room"],
            "разовое",   # По умолчанию для данных с сайта
            ""
        ))

    conn.commit()
    conn.close()
    print(f"✅ Расписание для {group_name} успешно сохранено!")


def query_db(query, args=(), one=False):
    """
    Выполняет SQL-запрос и возвращает результат.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, args)
    result = cursor.fetchall()
    conn.close()
    return (result[0] if result else None) if one else result


def execute_db(query, args=()):
    """
    Выполняет SQL-запрос (INSERT, UPDATE, DELETE) и коммитит изменения.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, args)
    conn.commit()
    conn.close()


# При импортировании этого файла автоматически создаются таблицы.
create_tables()

import os
import sqlite3

# Список кабинетов, которые мы хотим проверять
ALLOWED_IT_ROOMS = {
    "ГУК Б-416", "ГУК Б-362", "ГУК Б-434", "ГУК Б-436", "ГУК Б-422",
    "ГУК Б-438", "ГУК Б-440", "ГУК Б-417", "ГУК Б-426", "ГУК Б-415",
    "ГУК Б-324", "ГУК Б-325", "ГУК Б-326", "ГУК Б-418", "ГУК Б-420"
}

# Путь до БД parser/mai_schedule.db (относительно этого скрипта)
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PARSER_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "parser"))
DB_PATH    = os.path.join(PARSER_DIR, "mai_schedule.db")


def setup_db(conn: sqlite3.Connection):
    cur = conn.cursor()

    # --- Миграция: если старая таблица без нужных колонок, удаляем её ---
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='occupied_rooms';")
    if cur.fetchone():
        cur.execute("PRAGMA table_info(occupied_rooms);")
        cols = [row[1] for row in cur.fetchall()]
        # если нет start_time — это старая схема, сносим обе таблицы
        if "start_time" not in cols:
            print("🗑 Обнаружена старая схема occupied_rooms, пересоздаём таблицы...")
            cur.execute("DROP TABLE IF EXISTS occupied_rooms;")
            cur.execute("DROP TABLE IF EXISTS free_rooms;")
            conn.commit()

    # --- Создаём таблицы заново с нужной схемой ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS occupied_rooms (
            week        INTEGER,
            day         TEXT,
            start_time  TEXT,
            end_time    TEXT,
            room        TEXT,
            subject     TEXT,
            teacher     TEXT,
            group_name  TEXT,
            weekday     TEXT,
            PRIMARY KEY (week, day, start_time, end_time, room)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS free_rooms (
            week       INTEGER,
            day        TEXT,
            start_time TEXT,
            end_time   TEXT,
            room       TEXT,
            PRIMARY KEY (week, day, start_time, end_time, room)
        );
    """)
    conn.commit()


def get_occupied_rooms(conn: sqlite3.Connection):
    """
    Берём из schedule все записи по ALLOWED_IT_ROOMS,
    выделяем weekday из day и возвращаем список кортежей:
    (week, day, start_time, end_time, room, subject, teacher, group_name, weekday)
    """
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in ALLOWED_IT_ROOMS)
    sql = f"""
        SELECT week, day, start_time, end_time, room, subject, teacher, group_name
        FROM schedule
        WHERE room IN ({placeholders})
    """
    cur.execute(sql, tuple(ALLOWED_IT_ROOMS))
    rows = cur.fetchall()

    occupied = []
    for week, day_str, start, end, room, subj, teacher, grp in rows:
        weekday = day_str.split(",", 1)[0].strip()
        occupied.append((week, day_str, start, end, room, subj, teacher, grp, weekday))
    return occupied


def get_free_rooms(occupied):
    """
    Строим свободные комбинации строго для тех weeks/days/slots,
    которые реально пришли в occupied.
    """
    weeks = sorted({rec[0] for rec in occupied})
    days  = sorted({rec[1] for rec in occupied})
    slots = sorted({(rec[2], rec[3]) for rec in occupied})

    occupied_set = {
        (week, day, start, end, room)
        for week, day, start, end, room, *_ in occupied
    }

    free = []
    for week in weeks:
        for day in days:
            for start, end in slots:
                for room in ALLOWED_IT_ROOMS:
                    key = (week, day, start, end, room)
                    if key not in occupied_set:
                        free.append(key)
    return free


def save_filtered_data():
    conn = sqlite3.connect(DB_PATH)
    try:
        # 1) Миграция + (re)создание таблиц
        setup_db(conn)
        cur = conn.cursor()

        # 2) Убираем старые данные
        cur.execute("DELETE FROM occupied_rooms;")
        cur.execute("DELETE FROM free_rooms;")

        # 3) Извлекаем занятые и вставляем их
        occupied = get_occupied_rooms(conn)
        # дедупликация по (week, day, start, end, room)
        uniq = {}
        for rec in occupied:
            key = rec[:5]
            if key not in uniq:
                uniq[key] = rec
        occ_list = list(uniq.values())

        cur.executemany(
            "INSERT OR IGNORE INTO occupied_rooms "
            "(week, day, start_time, end_time, room, subject, teacher, group_name, weekday) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            occ_list
        )

        # 4) Генерируем свободные и сохраняем их
        free = get_free_rooms(occ_list)
        cur.executemany(
            "INSERT OR IGNORE INTO free_rooms "
            "(week, day, start_time, end_time, room) VALUES (?, ?, ?, ?, ?);",
            free
        )

        conn.commit()
        print("✅ occupied_rooms и free_rooms обновлены.")
    finally:
        conn.close()


if __name__ == "__main__":
    save_filtered_data()

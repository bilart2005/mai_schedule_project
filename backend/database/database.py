import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

# Путь к БД — backend/mai_schedule.db
BASE_DIR = Path(__file__).resolve().parent
# главный файл БД лежит рядом с каталогом backend
DB_PATH = BASE_DIR.parent / "mai_schedule.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    return conn


def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()

    # таблица групп
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT    UNIQUE NOT NULL,
        link    TEXT
    );
    """)

    # кеш сырых пар в JSON
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parser_pairs (
        group_id   INTEGER NOT NULL,
        week       INTEGER NOT NULL,
        json_data  TEXT    NOT NULL,
        parsed_at  TEXT    NOT NULL,
        is_custom  INTEGER DEFAULT 0,
        PRIMARY KEY(group_id, week),
        FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
    );
    """)

    # разобранное итоговое расписание
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id   INTEGER NOT NULL,
        week       INTEGER NOT NULL,
        date       TEXT    NOT NULL,
        time       TEXT    NOT NULL,
        subject    TEXT    NOT NULL,
        teachers   TEXT    NOT NULL,  -- JSON array
        rooms      TEXT    NOT NULL,  -- JSON array
        is_custom  INTEGER DEFAULT 0,
        FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
    );
    """)

    conn.commit()


def save_groups(groups: list[dict], force: bool = False):
    """
    Сохраняет список групп в таблицу groups.
    Если force=True — очищает её перед вставкой.
    """
    conn = get_connection()
    init_db(conn)
    cur = conn.cursor()
    if force:
        cur.execute("DELETE FROM groups;")
    for g in groups:
        cur.execute("""
            INSERT INTO groups(name, link)
            VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET link=excluded.link;
        """, (g["name"], g.get("link", "")))
    conn.commit()
    conn.close()


def get_groups_with_id() -> list[dict]:
    conn = get_connection()
    cur = conn.execute("SELECT id, name, link FROM groups;")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "link": r[2]} for r in rows]


def get_cached_pairs(conn: sqlite3.Connection, group_id: int, week: int):
    cur = conn.execute(
        "SELECT json_data FROM parser_pairs WHERE group_id=? AND week=?;",
        (group_id, week)
    )
    row = cur.fetchone()
    return json.loads(row[0]) if row and row[0] else None


def create_app_tables(conn: sqlite3.Connection):
    """Создаёт таблицы users, schedule, occupied_rooms, free_rooms и changes_log."""
    cur = conn.cursor()
    # Таблица пользователей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        email    TEXT    UNIQUE NOT NULL,
        password TEXT    NOT NULL,
        role     TEXT    NOT NULL
    );
    """)
    # Расписание
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name         TEXT    NOT NULL,
        week               INTEGER NOT NULL,
        day                TEXT    NOT NULL,
        start_time         TEXT    NOT NULL,
        end_time           TEXT    NOT NULL,
        subject            TEXT    NOT NULL,
        teacher            TEXT,
        room               TEXT,
        event_type         TEXT,
        recurrence_pattern TEXT,
        is_custom          INTEGER DEFAULT 0
    );
    """)
    # Занятые аудитории
    cur.execute("""
    CREATE TABLE IF NOT EXISTS occupied_rooms (
        week       INTEGER,
        day        TEXT,
        start_time TEXT,
        end_time   TEXT,
        room       TEXT,
        subject    TEXT,
        teacher    TEXT,
        group_name TEXT,
        PRIMARY KEY (week, day, start_time, end_time, room)
    );
    """)
    # Свободные аудитории
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
    # Лог изменений
    cur.execute("""
    CREATE TABLE IF NOT EXISTS changes_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER,
        changed_at  TEXT    NOT NULL,
        old_data    TEXT,
        new_data    TEXT,
        FOREIGN KEY(schedule_id) REFERENCES schedule(id) ON DELETE CASCADE
    );
    """)
    conn.commit()


def save_pairs(conn: sqlite3.Connection, group_id: int, week: int, data: list[dict]):
    js = json.dumps(data, ensure_ascii=False)
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute("""
    INSERT INTO parser_pairs(group_id, week, json_data, parsed_at, is_custom)
    VALUES (?,?,?,?,0)
    ON CONFLICT(group_id, week) DO UPDATE
      SET json_data=excluded.json_data,
          parsed_at=excluded.parsed_at;
    """, (group_id, week, js, ts))
    conn.commit()


def save_schedule(conn: sqlite3.Connection, group_id: int, week: int, data: list[dict]):
    """
    Пройдём по всем урокам из JSON и вставим их в schedule.
    teachers и rooms храним как JSON-строку.
    """
    cur = conn.cursor()
    for lesson in data:
        teachers_json = json.dumps(lesson["teachers"], ensure_ascii=False)
        rooms_json = json.dumps(lesson["rooms"], ensure_ascii=False)
        cur.execute("""
        INSERT INTO schedule (
            group_id, week, date, time, subject, teachers, rooms
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            group_id,
            week,
            lesson["date"],
            lesson["time"],
            lesson["subject"],
            teachers_json,
            rooms_json
        ))
    conn.commit()

import os
import sqlite3

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PARSER_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "parser"))
DB_PATH    = os.path.join(PARSER_DIR, "mai_schedule.db")


def create_tables():
    """Создаёт все нужные таблицы, если их нет."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()

    # пользователи
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id       INTEGER PRIMARY KEY AUTOINCREMENT,
          email    TEXT    UNIQUE NOT NULL,
          password TEXT    NOT NULL,
          role     TEXT    NOT NULL DEFAULT 'student'
        );
    """)
    # группы
    c.execute("""
        CREATE TABLE IF NOT EXISTS groups (
          name TEXT PRIMARY KEY
        );
    """)
    # основное расписание
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
          id                 INTEGER PRIMARY KEY AUTOINCREMENT,
          group_name         TEXT    NOT NULL,
          week               INTEGER NOT NULL,
          day                TEXT    NOT NULL,
          start_time         TEXT    NOT NULL,
          end_time           TEXT    NOT NULL,
          subject            TEXT    NOT NULL,
          teacher            TEXT    NOT NULL,
          room               TEXT    NOT NULL,
          event_type         TEXT    NOT NULL,
          recurrence_pattern TEXT,
          is_custom          INTEGER NOT NULL DEFAULT 0
        );
    """)
    # лог изменений
    c.execute("""
        CREATE TABLE IF NOT EXISTS changes_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          schedule_id  INTEGER NOT NULL,
          change_type  TEXT    NOT NULL,
          timestamp    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # занятые кабинеты
    c.execute("""
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
    # свободные кабинеты
    c.execute("""
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
    conn.close()


def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_PATH, timeout=5)

    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows[0] if one and rows else rows


def execute_db(query, args=()):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    conn.close()
    return last_id


# создаём таблицы сразу при импорте
create_tables()

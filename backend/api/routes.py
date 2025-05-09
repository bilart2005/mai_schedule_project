import sqlite3
import os
import json
import datetime
from functools import wraps
from flask import Flask, request, jsonify, g

# Импорты вашей БД и синка
from database import create_tables, query_db, execute_db
from api.google_sync import sync_group_to_calendar, sync_events_in_date_range

app = Flask(__name__)

# Убедимся, что все таблицы есть (работаем с той же БД parser/mai_schedule.db)
create_tables()


# ——— Простейшая «JWT» авторизация с JSON-токеном ——— #
def jwt_required():
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"msg": "Missing Authorization Header"}), 401
            token = auth.split(" ", 1)[1]
            try:
                identity = json.loads(token)
            except Exception:
                return jsonify({"msg": "Invalid token"}), 401
            g.current_user = identity
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def get_jwt_identity():
    return getattr(g, "current_user", None)


# ——— Регистрация и логин ——— #
@app.route("/register", methods=["POST"])
def register_user():
    data = request.get_json(force=True)
    email = data["email"]
    password = data["password"]
    role = data.get("role", "student")
    try:
        execute_db(
            "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
            (email, password, role)
            )
    except sqlite3.IntegrityError:
        return jsonify({"msg": "Пользователь с таким email уже существует"}), 409

    return jsonify({"msg": "Пользователь зарегистрирован"}), 201


@app.route("/login", methods=["POST"])
def login_user():
    data = request.get_json(force=True)
    email = data["email"]
    password = data["password"]
    user = query_db(
        "SELECT id, password, role FROM users WHERE email = ?",
        (email,), one=True
    )
    if not user or user[1] != password:
        return jsonify({"msg": "Неверный логин или пароль"}), 401
    user_id, _, role = user
    # наш «токен» — просто JSON-строка с id и ролью
    token = json.dumps({"user_id": user_id, "role": role})
    return jsonify(access_token=token), 200


# ——— Группы ——— #
@app.route("/groups", methods=["GET"])
def get_groups():
    rows = query_db("SELECT name FROM groups")
    return jsonify([r[0] for r in rows]), 200


# ——— Расписание ——— #
@app.route("/schedule", methods=["GET"])
def get_schedule():
    group = request.args.get("group")
    week = request.args.get("week")
    if not group or not week:
        return jsonify({"error": "Параметры group и week обязательны"}), 400

    rows = query_db(
        """
        SELECT id, day, start_time, end_time,
               subject, teacher, room,
               event_type, recurrence_pattern, is_custom
        FROM schedule
        WHERE group_name = ? AND week = ?
        """,
        (group, week)
    )
    schedule = [
        {
            "id": r[0],
            "day": r[1],
            "start_time": r[2],
            "end_time": r[3],
            "subject": r[4],
            "teacher": r[5] or "Не указан",
            "room": r[6] or "Не указана",
            "event_type": r[7],
            "recurrence_pattern": r[8],
            "is_custom": bool(r[9])
        }
        for r in rows
    ]
    return jsonify(schedule), 200


@app.route("/schedule", methods=["POST"])
@jwt_required()
def add_schedule():
    user = get_jwt_identity()
    if user["role"] not in ("teacher", "admin"):
        return jsonify({"msg": "Недостаточно прав"}), 403

    data = request.get_json(force=True)
    execute_db(
        """
        INSERT INTO schedule
          (group_name, week, day, start_time, end_time,
           subject, teacher, room, event_type, recurrence_pattern, is_custom)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            data.get("group_name", ""),
            data["week"],
            data["day"],
            data["start_time"],
            data["end_time"],
            data["subject"],
            data.get("teacher", "Не указан"),
            data.get("room", "Не указана"),
            data.get("event_type", "разовое"),
            data.get("recurrence_pattern", "")
        )
    )
    return jsonify({"msg": "Занятие добавлено"}), 201


# ——— Аудитории ——— #
@app.route("/occupied_rooms", methods=["GET"])
def occupied_rooms():
    rows = query_db(
        "SELECT week, day, start_time, end_time, room, subject, teacher, group_name "
        "FROM occupied_rooms"
    )
    return jsonify([
        {
            "week": r[0],
            "day": r[1],
            "start_time": r[2],
            "end_time": r[3],
            "room": r[4],
            "subject": r[5],
            "teacher": r[6],
            "group": r[7],
        }
        for r in rows
    ]), 200


@app.route("/free_rooms", methods=["GET"])
def free_rooms():
    rows = query_db(
        "SELECT week, day, start_time, end_time, room "
        "FROM free_rooms"
    )
    return jsonify([
        {
            "week": r[0],
            "day": r[1],
            "start_time": r[2],
            "end_time": r[3],
            "room": r[4],
        }
        for r in rows
    ]), 200


# ——— Синхронизация с Google ——— #
@app.route("/calendar/sync_group", methods=["POST"])
@jwt_required()
def sync_group_calendar():
    data = request.get_json(force=True)
    group = data.get("group")
    if not group:
        return jsonify({"error": "Укажите группу"}), 400
    sync_group_to_calendar(group)
    return jsonify({"msg": f"Расписание группы {group} добавлено в Google Calendar"}), 200


@app.route("/calendar/sync_range", methods=["POST"])
def sync_range_calendar():
    data = request.get_json(force=True)
    start_str = data.get("start_date")
    end_str = data.get("end_date")
    if not start_str or not end_str:
        return jsonify({"error": "Введите start_date и end_date"}), 400
    try:
        sd = datetime.datetime.strptime(start_str, "%d.%m.%Y").date()
        ed = datetime.datetime.strptime(end_str, "%d.%m.%Y").date()
    except Exception as e:
        return jsonify({"error": f"Неверный формат даты: {e}"}), 400
    if ed < sd:
        return jsonify({"error": "Дата окончания раньше даты начала"}), 400
    sync_events_in_date_range(sd, ed)
    return jsonify({"msg": f"Синхронизированы события с {sd} по {ed}"}), 200


if __name__ == "__main__":
    # Отключаем отладчик и релоад, чтобы не блокировать SQLite
    app.run(debug=False, use_reloader=False, port=5000)


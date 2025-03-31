from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import sqlite3
from database import create_tables, query_db, execute_db
from google_sync import sync_group_to_calendar

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "super-secret"  # Замените на свой ключ
jwt = JWTManager(app)

# 🛠 Создаём таблицы в БД, если их нет
create_tables()


### ---------- АВТОРИЗАЦИЯ И РОЛИ ---------- ###
@app.route("/register", methods=["POST"])
def register_user():
    """
    🔐 Регистрация пользователя.
    Входные данные: {"email": "...", "password": "...", "role": "..."}
    role может быть "student", "teacher", "admin"
    """
    data = request.json
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "student")  # По умолчанию студент

    execute_db(
        "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
        (email, password, role)
    )
    return jsonify({"msg": "Пользователь зарегистрирован"}), 201


@app.route("/login", methods=["POST"])
def login_user():
    """
    🔑 Вход пользователя (JWT-авторизация).
    Входные данные: {"email": "...", "password": "..."}
    """
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = query_db(
        "SELECT id, password, role FROM users WHERE email = ?",
        (email,), one=True
    )
    if not user or user[1] != password:
        return jsonify({"msg": "Неверный логин или пароль"}), 401

    user_id = user[0]
    user_role = user[2]
    access_token = create_access_token(
        identity={"user_id": user_id, "role": user_role}
    )
    return jsonify(access_token=access_token), 200


### ---------- РАСПИСАНИЕ ---------- ###
@app.route("/groups", methods=["GET"])
def get_groups():
    """📋 Возвращает список всех групп."""
    groups = query_db("SELECT name FROM groups")
    return jsonify([g[0] for g in groups])


@app.route("/schedule", methods=["GET"])
def get_schedule():
    """
    📆 Возвращает расписание группы на заданную неделю.
    Пример запроса: GET /schedule?group=М8О-101А-24&week=5
    """
    group = request.args.get("group")
    week = request.args.get("week")
    if not group or not week:
        return jsonify({"error": "Параметры group и week обязательны"}), 400

    rows = query_db(
        """
        SELECT day, time, room, subject, teacher
        FROM schedule
        WHERE group_name = ? AND week = ?
        """,
        (group, week)
    )
    return jsonify([
        {"day": row[0], "time": row[1], "room": row[2], "subject": row[3], "teacher": row[4] or "Не указан"}
        for row in rows
    ])


@app.route("/schedule", methods=["POST"])
@jwt_required()
def add_schedule():
    """
    ➕ Добавляет новое занятие (только преподаватели и админы).
    """
    current_user = get_jwt_identity()
    role = current_user["role"]
    if role not in ["teacher", "admin"]:
        return jsonify({"msg": "Недостаточно прав"}), 403

    data = request.json
    execute_db(
        """
        INSERT INTO schedule (week, day, time, room, subject, teacher, group_name, is_custom)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (data["week"], data["day"], data["time"], data["room"], data["subject"],
         data.get("teacher", "Не указан"), data.get("group_name", ""), 1 if role == "teacher" else 0)
    )
    return jsonify({"msg": "Занятие добавлено"}), 201


@app.route("/schedule/<int:schedule_id>", methods=["PUT"])
@jwt_required()
def update_schedule(schedule_id):
    """
    ✏️ Обновляет существующее занятие (например, изменяет время/аудиторию).
    """
    current_user = get_jwt_identity()
    role = current_user["role"]
    if role not in ["teacher", "admin"]:
        return jsonify({"msg": "Недостаточно прав"}), 403

    data = request.json
    fields = []
    values = []

    for key in ["week", "day", "time", "room", "subject", "teacher", "group_name"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])

    if not fields:
        return jsonify({"msg": "Нет данных для обновления"}), 400

    values.append(schedule_id)
    execute_db(f"UPDATE schedule SET {', '.join(fields)} WHERE id = ?", tuple(values))
    return jsonify({"msg": "Занятие обновлено"}), 200


@app.route("/schedule/<int:schedule_id>", methods=["DELETE"])
@jwt_required()
def delete_schedule(schedule_id):
    """🗑 Удаляет занятие (teacher/admin)."""
    current_user = get_jwt_identity()
    role = current_user["role"]
    if role not in ["teacher", "admin"]:
        return jsonify({"msg": "Недостаточно прав"}), 403

    execute_db("DELETE FROM schedule WHERE id = ?", (schedule_id,))
    return jsonify({"msg": "Занятие удалено"}), 200


### ---------- АУДИТОРИИ ---------- ###
@app.route("/occupied_rooms", methods=["GET"])
def get_occupied_rooms():
    """📌 Возвращает список занятых IT-кабинетов."""
    rooms = query_db("SELECT week, day, time, room, subject, teacher, group_name FROM occupied_rooms")
    return jsonify([
        {"week": row[0], "day": row[1], "time": row[2], "room": row[3], "subject": row[4], "teacher": row[5],
         "group": row[6]}
        for row in rooms
    ])


@app.route("/free_rooms", methods=["GET"])
def get_free_rooms():
    """✅ Возвращает список свободных IT-кабинетов."""
    rooms = query_db("SELECT week, day, time, room FROM free_rooms")
    return jsonify([
        {"week": row[0], "day": row[1], "time": row[2], "room": row[3]}
        for row in rooms
    ])


### ---------- GOOGLE CALENDAR ---------- ###
@app.route("/calendar/sync_group", methods=["POST"])
@jwt_required()
def sync_group_calendar():
    """
    🔄 Синхронизирует расписание всей группы с Google Calendar.
    """
    data = request.json
    group = data.get("group")
    if not group:
        return jsonify({"error": "Укажите группу"}), 400

    sync_group_to_calendar(group)
    return jsonify({"msg": f"Расписание группы {group} добавлено в Google Calendar"})


### ---------- ЗАПУСК СЕРВЕРА ---------- ###
if __name__ == "__main__":
    app.run(debug=True, port=5000)


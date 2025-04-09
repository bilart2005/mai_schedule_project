from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import datetime, sys
import logging
from database import create_tables, query_db, execute_db
from google_sync import sync_group_to_calendar, sync_events_in_date_range

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.config["JWT_SECRET_KEY"] = "super-secret"
jwt = JWTManager(app)

# Создаем таблицы в БД, если их ещё нет
create_tables()


### ---------- АВТОРИЗАЦИЯ И РОЛИ ---------- ###
@app.route("/register", methods=["POST"])
def register_user():
    """
    Регистрация нового пользователя.
    Входные данные (JSON): {"email": "email", "password": "pass", "role": "student/teacher/admin"}
    Если роль не указана, по умолчанию используется "student".
    """
    data = request.json
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "student")
    execute_db(
        "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
        (email, password, role)
    )
    return jsonify({"msg": "Пользователь зарегистрирован"}), 201


@app.route("/login", methods=["POST"])
def login_user():
    """
    Вход пользователя.
    Входные данные (JSON): {"email": "email", "password": "pass"}
    Возвращает JWT-токен для дальнейшей аутентификации.
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


### ---------- ГРУППЫ ---------- ###
@app.route("/groups", methods=["GET"])
def get_groups():
    """
    Возвращает список всех групп.
    """
    groups = query_db("SELECT name FROM groups")
    return jsonify([g[0] for g in groups])


### ---------- РАСПИСАНИЕ ---------- ###
@app.route("/schedule", methods=["GET"])
def get_schedule():
    """
    Возвращает расписание для указанной группы на заданную неделю.
    Пример запроса: GET /schedule?group=М8О-101А-24&week=5
    """
    group = request.args.get("group")
    week = request.args.get("week")
    if not group or not week:
        return jsonify({"error": "Параметры group и week обязательны"}), 400
    rows = query_db(
        """
        SELECT id, day, start_time, end_time, subject, teacher, room, event_type, recurrence_pattern, is_custom
        FROM schedule
        WHERE group_name = ? AND week = ?
        """,
        (group, week)
    )
    schedule = [
        {
            "id": row[0],
            "day": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "subject": row[4],
            "teacher": row[5] if row[5] else "Не указан",
            "room": row[6] if row[6] else "Не указана",
            "event_type": row[7],
            "recurrence_pattern": row[8],
            "is_custom": bool(row[9])
        }
        for row in rows
    ]
    return jsonify(schedule)


@app.route("/schedule", methods=["POST"])
@jwt_required()
def add_schedule():
    """
    Добавляет новое занятие (только для преподавателей и администраторов).
    Ожидаемые поля (JSON):
    {
      "group_name": "название группы",
      "week": <номер недели>,
      "day": "Пн, 17 марта 2025" (или без года),
      "start_time": "09:00",
      "end_time": "10:30",
      "subject": "Название предмета",
      "teacher": "ФИО преподавателя",
      "room": "Аудитория",
      "event_type": "разовое" или "повторяющееся",
      "recurrence_pattern": "повторяемость" (если применимо)
    }
    При ручном добавлении выставляется флаг is_custom = 1.
    """
    current_user = get_jwt_identity()
    if current_user["role"] not in ["teacher", "admin"]:
        return jsonify({"msg": "Недостаточно прав"}), 403
    data = request.json
    execute_db(
        """
        INSERT INTO schedule (group_name, week, day, start_time, end_time, subject, teacher, room, event_type, recurrence_pattern, is_custom)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get("recurrence_pattern", ""),
            1
        )
    )
    return jsonify({"msg": "Занятие добавлено"}), 201


@app.route("/schedule/<int:schedule_id>", methods=["PUT"])
@jwt_required()
def update_schedule(schedule_id):
    """
    Обновляет существующее занятие (изменение времени, аудитории, преподавателя, типа события и т.д.).
    Поддерживаются обновления следующих полей: group_name, week, day, start_time, end_time, subject, teacher, room, event_type, recurrence_pattern.
    """
    current = get_jwt_identity()
    if current["role"] not in ["teacher", "admin"]:
        return jsonify({"msg": "Недостаточно прав"}), 403
    data = request.json
    fields = []
    values = []
    for key in ["group_name", "week", "day", "start_time", "end_time", "subject", "teacher", "room", "event_type",
                "recurrence_pattern"]:
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
    """
    Удаляет занятие по его идентификатору.
    """
    current = get_jwt_identity()
    if current["role"] not in ["teacher", "admin"]:
        return jsonify({"msg": "Недостаточно прав"}), 403
    execute_db("DELETE FROM schedule WHERE id = ?", (schedule_id,))
    return jsonify({"msg": "Занятие удалено"}), 200


### ---------- АУДИТОРИИ ---------- ###
@app.route("/occupied_rooms", methods=["GET"])
def get_occupied_rooms():
    """
    Возвращает список занятых IT-кабинетов.
    Ожидается, что таблица occupied_rooms содержит: week, day, start_time, end_time, room, subject, teacher, group_name.
    """
    rows = query_db("SELECT week, day, start_time, end_time, room, subject, teacher, group_name FROM occupied_rooms")
    rooms = [
        {
            "week": row[0],
            "day": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "room": row[4],
            "subject": row[5],
            "teacher": row[6],
            "group": row[7]
        }
        for row in rows
    ]
    return jsonify(rooms)


@app.route("/free_rooms", methods=["GET"])
def get_free_rooms():
    """
    Возвращает список свободных IT-кабинетов.
    Ожидается, что таблица free_rooms содержит: week, day, start_time, end_time, room.
    """
    rows = query_db("SELECT week, day, start_time, end_time, room FROM free_rooms")
    rooms = [
        {
            "week": row[0],
            "day": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "room": row[4]
        }
        for row in rows
    ]
    return jsonify(rooms)


### ---------- GOOGLE CALENDAR СИНХРОНИЗАЦИЯ ---------- ###
@app.route("/calendar/sync_group", methods=["POST"])
@jwt_required()
def sync_group_calendar():
    """
    Синхронизирует расписание указанной группы с Google Calendar.
    Входные данные (JSON): {"group": "название группы"}
    """
    data = request.json
    group = data.get("group")
    if not group:
        return jsonify({"error": "Укажите группу"}), 400
    sync_group_to_calendar(group)
    return jsonify({"msg": f"Расписание группы {group} добавлено в Google Calendar"}), 200


@app.route("/calendar/sync_range", methods=["POST"])
#@jwt_required() - из-за него 422 ошибка, нужно убрать будет строгий перевод в строку в google_sync
def sync_range_calendar():
    print("[DEBUG] Точка входа в эндпоинт /calendar/sync_range")
    data = request.json
    print("[DEBUG] request.json:", data)
    """
    Синхронизирует события из occupied_rooms, дата которых попадает в указанный диапазон.
    Входные данные (JSON):
    {
      "start_date": "DD.MM.YYYY",
      "end_date": "DD.MM.YYYY"
    }
    """
    data = request.json
    start_str = data.get("start_date")
    end_str = data.get("end_date")
    if not start_str or not end_str:
        return jsonify({"error": "Введите start_date и end_date в формате DD.MM.YYYY"}), 400
    try:
        start_date = datetime.datetime.strptime(start_str, "%d.%m.%Y").date()
        end_date = datetime.datetime.strptime(end_str, "%d.%m.%Y").date()
    except Exception as e:
        return jsonify({"error": f"Ошибка при разборе дат: {e}"}), 400
    if end_date < start_date:
        return jsonify({"error": "Дата конца раньше даты начала"}), 400
    sync_events_in_date_range(start_date, end_date)
    return jsonify({"msg": f"Синхронизированы события с {start_date} по {end_date}."}), 200


### ---------- ЗАПУСК СЕРВЕРА ---------- ###
if __name__ == "__main__":
    app.run(debug=True, port=5000)

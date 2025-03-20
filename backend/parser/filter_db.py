import sqlite3

# Список кабинетов, доступных для занятий
ALLOWED_IT_ROOMS = {
    "ГУК Б-416", "ГУК Б-362", "ГУК Б-434", "ГУК Б-436", "ГУК Б-422",
    "ГУК Б-438", "ГУК Б-440", "ГУК Б-417", "ГУК Б-426", "ГУК Б-415",
    "ГУК Б-324", "ГУК Б-325", "ГУК Б-326", "ГУК Б-418", "ГУК Б-420"
}

# Список кабинетов, которые нельзя занимать
EXCLUDED_ROOMS = {
    "ГУК Б-413", "ГУК Б-419", "ГУК Б-421", "ГУК Б-423",
    "ГУК Б-425", "ГУК Б-432", "ГУК Б-430", "ГУК Б-424"
}


def setup_db():
    """Создаёт таблицы, если их нет"""
    conn = sqlite3.connect("mai_schedule.db")
    cursor = conn.cursor()

    # Проверяем, есть ли колонка `group_name`
    cursor.execute("PRAGMA table_info(occupied_rooms);")
    columns = [row[1] for row in cursor.fetchall()]

    if "group_name" not in columns:
        print("🔄 Добавляем колонку group_name в occupied_rooms...")
        cursor.execute("ALTER TABLE occupied_rooms ADD COLUMN group_name TEXT;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS occupied_rooms (
            week INTEGER, 
            day TEXT, 
            time TEXT, 
            room TEXT, 
            subject TEXT, 
            teacher TEXT,
            group_name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS free_rooms (
            week INTEGER, 
            day TEXT, 
            time TEXT, 
            room TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_occupied_rooms():
    """Получает список занятых IT-кабинетов с группами"""
    conn = sqlite3.connect("mai_schedule.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT week, day, time, room, subject, teacher, group_name
        FROM schedule
        WHERE room IN ({})
    """.format(",".join(["?"] * len(ALLOWED_IT_ROOMS))), tuple(ALLOWED_IT_ROOMS))

    occupied_rooms = cursor.fetchall()
    conn.close()

    return occupied_rooms


def get_free_rooms():
    """Определяет свободные IT-кабинеты"""
    occupied_rooms = get_occupied_rooms()
    occupied_set = {(week, day, time, room) for week, day, time, room, _, _, _ in occupied_rooms}

    free_rooms = []
    for week in range(1, 18):
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]:
            for time in ["09:00 - 10:30", "10:45 - 12:15", "13:00 - 14:30", "14:45 - 16:15"]:
                for room in ALLOWED_IT_ROOMS:
                    if (week, day, time, room) not in occupied_set:
                        free_rooms.append((week, day, time, room))

    return free_rooms


def save_filtered_data():
    """Сохраняет занятые и свободные кабинеты в БД"""
    setup_db()  # Гарантируем, что таблицы существуют

    conn = sqlite3.connect("mai_schedule.db")
    cursor = conn.cursor()

    # Очищаем старые данные
    cursor.execute("DELETE FROM occupied_rooms")
    cursor.execute("DELETE FROM free_rooms")

    # Заполняем занятые кабинеты
    occupied_rooms = get_occupied_rooms()
    cursor.executemany("INSERT INTO occupied_rooms VALUES (?, ?, ?, ?, ?, ?, ?)", occupied_rooms)

    # Заполняем свободные кабинеты
    free_rooms = get_free_rooms()
    cursor.executemany("INSERT INTO free_rooms VALUES (?, ?, ?, ?)", free_rooms)

    conn.commit()
    conn.close()
    print("✅ Данные успешно сохранены!")


if __name__ == "__main__":
    save_filtered_data()
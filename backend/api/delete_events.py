import os
import sys
import datetime
import sqlite3
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend.database.database import DB_PATH

# Замените на ваш Calendar ID
CALENDAR_ID = 'be410167da6282a13f52aad85d4ab444e8b456ecaf5da50495e0b782b566426f@group.calendar.google.com'
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Путь до service account JSON (правильное название файла)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'service_account.json')

# Московская временная зона UTC+3
MOSCOW_TZ = datetime.timezone(datetime.timedelta(hours=3))


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def delete_all_events_for_group(group_name):
    # пример работы с БД
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT google_event_id FROM occupied_rooms WHERE group_name = ?", (group_name,))
    ids = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()

    service = get_calendar_service()
    for eid in ids:
        service.events().delete(calendarId=CALENDAR_ID, eventId=eid).execute()


from googleapiclient.errors import HttpError


def delete_events_in_range(start_date_str, end_date_str):
    """
    Удаляет все события из календаря между start_date_str и end_date_str.
    Формат дат: 'DD.MM.YYYY'.
    Обработка ошибок HttpError для случаев отсутствия календаря или событий.
    """
    # Парсим строки дат
    try:
        start_dt = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')
        end_dt = datetime.datetime.strptime(end_date_str, '%d.%m.%Y') + datetime.timedelta(days=1)
    except ValueError as e:
        print(f"Ошибка при разборе дат: {e}")
        return

    # Добавляем таймзону и преобразуем в ISO
    time_min_iso = start_dt.replace(tzinfo=MOSCOW_TZ).isoformat()
    time_max_iso = end_dt.replace(tzinfo=MOSCOW_TZ).isoformat()

    service = get_calendar_service()

    # 1) Получаем список событий, ловим 404 по CalendarId
    try:
        events = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])
    except HttpError as e:
        if e.resp.status == 404:
            print(f"Календарь с ID '{CALENDAR_ID}' не найден или нет доступа.")
        else:
            print(f"Ошибка при получении событий: {e}")
        return

    if not events:
        print("События не найдены в заданном диапазоне.")
        return

    # 2) Удаляем каждое событие, игнорируя 404 по событию
    for event in events:
        eid = event.get('id')
        summary = event.get('summary', '<без названия>')
        try:
            service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=eid
            ).execute()
            print(f"Удалено событие: {summary} (ID={eid})")
        except HttpError as e:
            if e.resp.status == 404:
                print(f"Событие ID={eid} не найдено (возможно уже удалено)")
            else:
                print(f"Ошибка удаления события {eid}: {e}")


def main():
    start_date = input("Введите дату начала (DD.MM.YYYY): ").strip()
    end_date = input("Введите дату конца (DD.MM.YYYY): ").strip()
    print(f"Удаляем события с {start_date} по {end_date}...")
    delete_events_in_range(start_date, end_date)
    print("Операция завершена.")


if __name__ == '__main__':
    main()

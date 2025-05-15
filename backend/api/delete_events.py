import os
import datetime
import sqlite3
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.database.database import DB_PATH

# Ваш Calendar ID и пути
CALENDAR_ID = 'be410167da6282a13f52aad85d4ab444e8b456ecaf5da50495e0b782b566426f@group.calendar.google.com'
SCOPES = ['https://www.googleapis.com/auth/calendar']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'service_account.json')
MOSCOW_TZ = datetime.timezone(datetime.timedelta(hours=3))


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)


def delete_events_in_range(start_date_str, end_date_str):
    """
    Удаляет события из Google Calendar в диапазоне дат [start_date, end_date].
    Формат дат на входе 'DD.MM.YYYY'.
    """
    # 1) Парсим входные даты
    try:
        sd = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')
        ed = datetime.datetime.strptime(end_date_str, '%d.%m.%Y') + datetime.timedelta(days=1)
    except ValueError as e:
        print(f"Неверный формат даты: {e}")
        return

    time_min = sd.replace(tzinfo=MOSCOW_TZ).isoformat()
    time_max = ed.replace(tzinfo=MOSCOW_TZ).isoformat()

    service = get_calendar_service()

    # 2) Постранично получаем все события
    page_token = None
    all_events = []
    while True:
        try:
            resp = service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                pageToken=page_token
            ).execute()
        except HttpError as e:
            print(f"Ошибка при list: {e}")
            return

        items = resp.get('items', [])
        all_events.extend(items)
        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    if not all_events:
        print("Нет событий в указанном диапазоне.")
        return

    # 3) Удаляем одно за другим с backoff
    for ev in all_events:
        eid = ev.get('id')
        summary = ev.get('summary', '<без названия>')
        success = False

        for attempt in range(1, 4):  # до 3 попыток
            try:
                service.events().delete(
                    calendarId=CALENDAR_ID,
                    eventId=eid
                ).execute()
                print(f"Удалено: {summary} (ID={eid})")
                success = True
                break
            except HttpError as e:
                code = e.resp.status
                # при rate limit делаем экспоненциальную задержку
                if code in (429, 403):
                    wait = 2 ** (attempt - 1)
                    print(f"Rate limit ({code}), попытка {attempt}/3. Ждём {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"Ошибка удаления {eid}: {e}")
                    break

        if not success:
            print(f"Не удалось удалить событие ID={eid} после 3 попыток.")

        # небольшой таймаут между запросами, чтобы не спамить API
        time.sleep(0.1)

    print("Удаление всех попавших в диапазон событий завершено.")


if __name__ == '__main__':
    sd = input("Дата начала (DD.MM.YYYY): ").strip()
    ed = input("Дата конца   (DD.MM.YYYY): ").strip()
    delete_events_in_range(sd, ed)

import datetime
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Замените на ваш Calendar ID
CALENDAR_ID = '***@group.calendar.google.com'
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service_account.json'

# Определяем временную зону +03:00 для Москвы
MOSCOW_TZ = datetime.timezone(datetime.timedelta(hours=3))


def get_calendar_service():
    """
    Создает и возвращает объект сервиса Google Calendar,
    используя данные сервисного аккаунта.
    """
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=credentials)
    return service


def delete_events_in_range(time_min_iso, time_max_iso):
    """
    Удаляет все события из календаря между time_min_iso и time_max_iso.
    Параметры time_min_iso и time_max_iso – строки в формате ISO 8601.
    """
    service = get_calendar_service()

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=time_min_iso,
        timeMax=time_max_iso,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        print("События не найдены в заданном диапазоне.")
        return

    for event in events:
        try:
            service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()
            print(f"Удалено событие: {event.get('summary', 'Без названия')}")
        except Exception as e:
            print(f"Ошибка удаления события {event.get('id')}: {e}")


def main():
    # Запрашиваем у пользователя дату начала и дату конца в формате DD.MM.YYYY
    start_date_str = input("Введите дату начала (DD.MM.YYYY): ").strip()
    end_date_str = input("Введите дату конца (DD.MM.YYYY): ").strip()

    try:
        # Преобразуем строки в объекты datetime с учетом московской временной зоны
        start_dt = datetime.datetime.strptime(start_date_str, "%d.%m.%Y").replace(tzinfo=MOSCOW_TZ)
        end_dt_input = datetime.datetime.strptime(end_date_str, "%d.%m.%Y")
        # Чтобы включить все события за конечный день, прибавляем 1 день и устанавливаем время 00:00:00
        end_dt = (end_dt_input + datetime.timedelta(days=1)).replace(tzinfo=MOSCOW_TZ)
    except Exception as e:
        print(f"Ошибка при разборе дат: {e}")
        sys.exit(1)

    # Преобразуем datetime в ISO 8601 строки
    time_min_iso = start_dt.isoformat()
    time_max_iso = end_dt.isoformat()

    print(f"Удаляем события с {time_min_iso} до {time_max_iso} ...")
    delete_events_in_range(time_min_iso, time_max_iso)
    print("Операция завершена.")


if __name__ == "__main__":
    main()

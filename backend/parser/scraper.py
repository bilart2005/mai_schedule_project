import time
import random
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from fake_useragent import UserAgent
from database import get_groups, save_schedule
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Базовая ссылка для расписания
BASE_SCHEDULE_URL = "https://mai.ru/education/studies/schedule/index.php?group={group}&week={week}"

# Ограничение на количество потоков
MAX_THREADS = 5  # Оптимально 3-5, можно больше, если сервер позволяет


def get_driver():
    """Создает Selenium-драйвер с рандомным User-Agent"""
    ua = UserAgent()
    user_agent = ua.random

    options = webdriver.EdgeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--headless")  # Без GUI
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)
    return driver


def get_schedule(group_name):
    """Парсит расписание группы с 1 по 17 неделю"""
    schedule = []
    driver = get_driver()

    for week in range(5, 18):
        week_url = BASE_SCHEDULE_URL.format(group=group_name, week=week)
        driver.get(week_url)
        time.sleep(random.uniform(2, 5))  # Даем странице загрузиться

        # ✅ Ожидаем загрузки контента перед парсингом
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.step-item"))
            )
        except:
            print(f"⚠️ Неделя {week} для группы {group_name} не загрузилась корректно. Пропускаем...")
            continue

        days = driver.find_elements(By.CSS_SELECTOR, "li.step-item")

        if not days:
            print(f"⚠️ Неделя {week} для группы {group_name} не имеет расписания, пропускаем...")
            continue

        print(f"📅 Парсим неделю {week} для группы {group_name}...")

        for day in days:
            try:
                day_name = day.find_element(By.CSS_SELECTOR, "span.step-title").text.strip()

                # ✅ Получаем список всех занятий за день
                lessons = day.find_elements(By.CSS_SELECTOR, "div.mb-4")

                for lesson in lessons:
                    subject_elem = lesson.find_element(By.CSS_SELECTOR, "p.mb-2.fw-semi-bold.text-dark")
                    subject = subject_elem.text.strip().rsplit(" ", 1)[0]  # Убираем "ЛК", "ПЗ" и т.д.

                    time_range_elem = lesson.find_elements(By.CSS_SELECTOR, "li.list-inline-item")
                    if len(time_range_elem) > 0:
                        start_time, end_time = time_range_elem[0].text.strip().split(" – ")
                    else:
                        start_time, end_time = "Неизвестно", "Неизвестно"

                    teacher_elem = lesson.find_elements(By.CSS_SELECTOR, "a.text-body")
                    teacher = teacher_elem[0].text.strip() if teacher_elem else "Не указан"

                    # ✅ Новый способ поиска аудитории
                    room_elem = lesson.find_elements(By.XPATH, ".//li[contains(text(),'ГУК') or contains(text(),'каф')]")
                    room = room_elem[0].text.strip() if room_elem else "Не указана"

                    schedule.append({
                        "week": week,
                        "day": day_name,
                        "time": f"{start_time} - {end_time}",
                        "subject": subject,
                        "teacher": teacher,
                        "room": room
                    })

                    print(f"✅ {day_name}: {subject} ({start_time}-{end_time}), {teacher}, {room}")

            except Exception as e:
                print(f"❌ Ошибка при обработке пары: {e}")
                print(f"📄 HTML проблемного занятия:\n{day.get_attribute('outerHTML')}")

    driver.quit()
    return schedule


def process_group(group):
    """Парсит и сохраняет расписание для одной группы"""
    group_name = group["name"]
    print(f"📡 Начинаем парсинг {group_name}...")
    schedule = get_schedule(group_name)
    save_schedule(group_name, schedule)
    print(f"✅ Расписание для {group_name} сохранено!")


if __name__ == "__main__":
    groups = get_groups()

    # Используем многопоточный парсинг
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        executor.map(process_group, groups)

    print("🎉 Все данные загружены и сохранены в БД!")

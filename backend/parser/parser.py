import time
import random
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from fake_useragent import UserAgent
from database import save_groups, save_schedule

# URL для парсинга групп и расписания
GROUPS_URL = "https://mai.ru/education/studies/schedule/groups.php?department=Институт+№8&course=all"
BASE_SCHEDULE_URL = "https://mai.ru/education/studies/schedule/index.php?group={group}&week={week}"

# Ограничение на количество потоков
MAX_THREADS = 6


def get_driver():
    """Создает Selenium-драйвер с рандомным User-Agent."""
    ua = UserAgent()
    user_agent = ua.random

    options = webdriver.EdgeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)
    return driver


def close_popups(driver):
    """Закрывает всплывающие окна (куки, алерты) на странице."""
    try:
        cookie_banner = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "cookie_message"))
        )
        driver.execute_script("arguments[0].style.display = 'none';", cookie_banner)
        print("✅ Куки-баннер скрыт")
    except Exception:
        pass  # Если баннера нет, идем дальше


def scrape_groups():
    """
    Парсит список групп с сайта.
    Возвращает список словарей вида: {"name": <название группы>, "link": <ссылка>}.
    """
    driver = get_driver()
    driver.get(GROUPS_URL)
    wait = WebDriverWait(driver, 10)
    time.sleep(random.uniform(2, 5))

    close_popups(driver)

    groups = []
    tabs = driver.find_elements(By.CSS_SELECTOR, "ul.nav.nav-segment.nav-pills.nav-fill a.nav-link")

    for tab in tabs:
        try:
            driver.execute_script("arguments[0].scrollIntoView();", tab)
            driver.execute_script("arguments[0].click();", tab)
            time.sleep(random.uniform(2, 4))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn.btn-soft-secondary")))
            elements = driver.find_elements(By.CSS_SELECTOR, "a.btn.btn-soft-secondary.btn-xs.mb-1.fw-medium.btn-group")
            for elem in elements:
                group_name = elem.text.strip()
                group_link = elem.get_attribute("href")
                if group_name and group_link:
                    groups.append({"name": group_name, "link": group_link})
        except Exception as e:
            print(f"❌ Ошибка при парсинге вкладки: {e}")

    driver.quit()
    return groups


def get_schedule_for_group(group_name):
    """
    Парсит расписание для заданной группы по неделям с 7 по 19.
    Возвращает список уроков с полями: week, day, start_time, end_time, subject, teacher, room.
    """
    schedule = []
    driver = get_driver()

    for week in range(7, 20):  # Недели с 7 по 19 включительно
        week_url = BASE_SCHEDULE_URL.format(group=group_name, week=week)
        driver.get(week_url)
        time.sleep(random.uniform(2, 5))

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.step-item"))
            )
        except Exception:
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
                lessons = day.find_elements(By.CSS_SELECTOR, "div.mb-4")
                for lesson in lessons:
                    subject_elem = lesson.find_element(By.CSS_SELECTOR, "p.mb-2.fw-semi-bold.text-dark")
                    subject = subject_elem.text.strip().rsplit(" ", 1)[0]  # Убираем обозначения (например, ЛК, ПЗ)

                    time_range_elem = lesson.find_elements(By.CSS_SELECTOR, "li.list-inline-item")
                    if time_range_elem:
                        time_text = time_range_elem[0].text.strip()
                        if "–" in time_text:
                            start_time, end_time = [t.strip() for t in time_text.split("–")]
                        else:
                            start_time, end_time = "Неизвестно", "Неизвестно"
                    else:
                        start_time, end_time = "Неизвестно", "Неизвестно"

                    teacher_elem = lesson.find_elements(By.CSS_SELECTOR, "a.text-body")
                    teacher = teacher_elem[0].text.strip() if teacher_elem else "Не указан"

                    room_elem = lesson.find_elements(By.XPATH,
                                                     ".//li[contains(text(),'ГУК') or contains(text(),'каф')]")
                    room = room_elem[0].text.strip() if room_elem else "Не указана"

                    schedule.append({
                        "week": week,
                        "day": day_name,
                        "start_time": start_time,
                        "end_time": end_time,
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


def process_group_schedule(group):
    """Парсит расписание для одной группы и сохраняет его в БД."""
    group_name = group["name"]
    print(f"📡 Начинаем парсинг расписания для группы {group_name}...")
    schedule = get_schedule_for_group(group_name)
    save_schedule(group_name, schedule)
    print(f"✅ Расписание для группы {group_name} сохранено!")


if __name__ == "__main__":
    # 1. Парсинг групп
    print("📥 Загружаем список групп...")
    groups = scrape_groups()
    print(f"✅ Найдено {len(groups)} групп.")

    # 2. Сохранение групп в БД
    save_groups(groups)
    print("✅ Группы сохранены в БД.")

    # 3. Парсинг расписания для каждой группы (недели с 7 по 19)
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        executor.map(process_group_schedule, groups)

    print("🎉 Все данные загружены и сохранены в БД!")

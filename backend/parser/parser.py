import argparse
import sqlite3
import json
import os
import random
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from json import JSONDecodeError
from fake_useragent import UserAgent
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from backend.database.database import (
    get_connection, init_db,
    get_groups_with_id, get_cached_pairs, save_pairs, save_schedule
)

# Пути для кеша и логов
HERE      = os.path.dirname(__file__)
CACHE_DIR = os.path.join(HERE, "cache")
LOGS_DIR  = os.path.join(HERE, "logs")
ERROR_LOG = os.path.join(LOGS_DIR, "errors.json")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,  exist_ok=True)


def log_error(group: str, week: int, msg: str):
    entry = {
        "group": group,
        "week":  week,
        "error": msg,
        "at":    datetime.now(timezone.utc).isoformat()
    }
    try:
        with open(ERROR_LOG, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, JSONDecodeError):
        data = []
    data.append(entry)
    with open(ERROR_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cache_path(group: str, week: int) -> str:
    safe = group.replace(" ", "_").replace("/", "_")
    return os.path.join(CACHE_DIR, f"{safe}_wk{week}.json")


def create_driver() -> uc.Chrome:
    """Конфигурирует и запускает один headless Chrome."""
    ua   = UserAgent().random
    opts = uc.ChromeOptions()
    opts.headless = True
    opts.add_argument(f"--user-agent={ua}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    prefs = {
        "profile.managed_default_content_settings.images":      2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts":       2,
    }
    opts.add_experimental_option("prefs", prefs)
    chrome_bin = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    opts.binary_location = chrome_bin
    driver = uc.Chrome(options=opts, browser_executable_path=chrome_bin)
    driver.implicitly_wait(5)
    return driver


def scrape_pairs(driver: uc.Chrome, group: str, week: int) -> list[dict]:
    base = "https://mai.ru/education/studies/schedule/index.php"
    url  = f"{base}?group={quote_plus(group)}&week={week}"
    driver.get(url)
    # если редирект на главную — повторяем
    if "index.php?group=" not in driver.current_url:
        driver.get(url)

    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.step.mb-5")))
    except TimeoutException:
        # считаем, что просто нет расписания на эту неделю
        return []

    items = driver.find_elements(By.CSS_SELECTOR, "ul.step.mb-5 > li.step-item")
    if not items:
        return []

    lessons = []
    for day in items:
        date_txt = day.find_element(By.CSS_SELECTOR, ".step-title") \
                      .text.strip().replace("\u00A0", " ")
        for blk in day.find_elements(By.CSS_SELECTOR, "div.mb-4"):
            subj = blk.find_element(By.CSS_SELECTOR, "p.fw-semi-bold.text-dark").text.strip()
            tm   = blk.find_element(
                By.CSS_SELECTOR, "ul.list-inline li.list-inline-item"
            ).text.strip()
            teachers = [
                a.text.strip() for a in blk.find_elements(
                    By.CSS_SELECTOR, "ul.list-inline li.list-inline-item a.text-body"
                )
            ]
            rooms = [
                li.text.strip() for li in blk.find_elements(
                    By.CSS_SELECTOR, "ul.list-inline li.list-inline-item"
                ) if li.find_elements(By.CSS_SELECTOR, "i.fa-map-marker-alt")
            ]
            lessons.append({
                "date":     date_txt,
                "time":     tm,
                "subject":  subj,
                "teachers": teachers,
                "rooms":    rooms
            })
    return lessons


def worker(task):
    """
    Задача: (group_id, group_name, week, force_db, driver_queue)
      1) проверяем БД
      2) читаем из JSON-кеша, если есть
      3) иначе парсим через Selenium
      4) сохраняем в кеш и в две таблицы БД
    """
    gid, name, week, force_db, driver_queue = task
    cache_file = cache_path(name, week)

    conn = get_connection()
    init_db(conn)
    print(f"[RUN]   {name} wk={week}")

    # 1) если уже есть в БД и не force — пропускаем
    if not force_db and get_cached_pairs(conn, gid, week):
        conn.close()
        print(f"🐁 {name} {week} скип")
        return (gid, name, week, "skipped", 0)

    # 2) JSON-кеш
    if os.path.exists(cache_file) and not force_db:
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        # 3) парсим
        driver = driver_queue.get()
        try:
            data = scrape_pairs(driver, name, week)
        except Exception as e:
            msg = str(e)
            log_error(name, week, msg)
            driver_queue.put(driver)
            conn.close()
            return (gid, name, week, "error", msg)
        finally:
            # независимо от успеха, возвращаем драйвер в очередь
            driver_queue.put(driver)

        # 4) сохраняем JSON-кеш
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 5) сохраняем в БД: кеш и расписание
    save_pairs(conn, gid, week, data)
    save_schedule(conn, gid, week, data)
    conn.close()
    return (gid, name, week, "ok", len(data))


def main():
    p = argparse.ArgumentParser(description="MAI Schedule Parser (multi-threaded)")
    p.add_argument("--weeks",   required=True,
                   help="Список недель через запятую, напр. 14,15,16")
    p.add_argument("--force-db", action="store_true",
                   help="Перезаписать пары в БД и JSON-кеше")
    p.add_argument("--threads", type=int, default=5,
                   help="Число параллельных потоков (по умолчанию 5)")
    args = p.parse_args()

    weeks  = [int(w) for w in args.weeks.split(",")]
    groups = get_groups_with_id()
    if not groups:
        print("Не найдены группы в БД, сначала запустите groups_parser.")
        return

    # 1) создаём пул драйверов
    driver_queue = Queue(maxsize=args.threads)
    for _ in range(args.threads):
        drv = create_driver()
        driver_queue.put(drv)

    # 2) собираем задачи
    tasks = [
        (g["id"], g["name"], wk, args.force_db, driver_queue)
        for g in groups for wk in weeks
    ]
    random.shuffle(tasks)

    print(f"▶️ Запускаем парсер: {len(tasks)} задач × {args.threads} потоков…")
    with ThreadPoolExecutor(max_workers=args.threads) as exe:
        futures = {exe.submit(worker, t): t for t in tasks}
        for fut in as_completed(futures):
            gid, name, wk, status, info = fut.result()
            if status == "ok":
                print(f"[ OK ]   {name} wk={wk} → {info} пар")
            elif status == "skipped":
                print(f"[SKIP]   {name} wk={wk} (есть в БД)")
            else:
                print(f"[FAIL]   {name} wk={wk}: {info}")

    print("✅ Все задачи завершены, закрываем браузеры…")
    # 3) чисто завершаем все драйверы
    while not driver_queue.empty():
        drv = driver_queue.get_nowait()
        try:
            drv.quit()
        except:
            pass

    print("✅ Готово.")


if __name__ == "__main__":
    main()

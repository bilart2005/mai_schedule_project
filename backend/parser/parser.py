import argparse
import sqlite3
import time
import random
import json
from datetime import datetime

from fake_useragent import UserAgent
import undetected_chromedriver as uc

from groups_parser import get_cached_groups

DB_PATH = "mai_schedule.db"  # или полный путь до вашей БД


def get_driver() -> uc.Chrome:
    ua = UserAgent().random
    options = uc.ChromeOptions()
    options.headless = True
    options.page_load_strategy = "eager"
    options.add_argument(f"--user-agent={ua}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Отключаем картинки/стили/шрифты
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }
    options.add_experimental_option("prefs", prefs)
    # Прокси Nekoray (socks5 на localhost:2080)
    options.add_argument("--proxy-server=socks5://127.0.0.1:2080")
    # Явный путь к Chrome — строка!
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.binary_location = chrome_path

    driver = uc.Chrome(
        options=options,
        browser_executable_path=chrome_path
    )
    driver.implicitly_wait(10)
    return driver


def init_db(conn: sqlite3.Connection):
    """Создаёт таблицу parser_pairs, если её ещё нет."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS parser_pairs (
        group_id   INTEGER,
        week       INTEGER,
        json_data  TEXT,
        parsed_at  TEXT,
        is_custom  INTEGER DEFAULT 0,
        PRIMARY KEY(group_id, week)
    );
    """)
    conn.commit()


def get_cached_pairs(conn: sqlite3.Connection, group_id: int, week: int):
    cur = conn.execute(
        "SELECT json_data FROM parser_pairs WHERE group_id=? AND week=?;",
        (group_id, week)
    )
    row = cur.fetchone()
    return json.loads(row[0]) if row and row[0] else None


def save_pairs(conn: sqlite3.Connection, group_id: int, week: int, data):
    js = json.dumps(data, ensure_ascii=False)
    now = datetime.utcnow().isoformat()
    conn.execute("""
    INSERT INTO parser_pairs(group_id, week, json_data, parsed_at, is_custom)
    VALUES(?,?,?,?,0)
    ON CONFLICT(group_id, week) DO UPDATE
      SET json_data=excluded.json_data,
          parsed_at=excluded.parsed_at
    ;
    """, (group_id, week, js, now))
    conn.commit()


def scrape_pairs(driver: uc.Chrome, group: dict, week: int):
    """
    Ваша реальная логика парсинга здесь:
      1. driver.get(урл для group['id'], week)
      2. ждем загрузки таблицы
      3. достаём строки и колонки
      4. собираем структуру Python-объекта (list/dict)
      5. возвращаем его
    """
    url = f"https://example.com/schedule?group={group['id']}&week={week}"
    driver.get(url)
    # TODO: замените на ваши селекторы и сбор данных
    rows = driver.find_elements_by_css_selector("table.schedule tr")
    result = []
    for r in rows[1:]:
        cols = r.find_elements_by_tag_name("td")
        lesson = {
            "time": cols[0].text,
            "subject": cols[1].text,
            "room": cols[2].text,
            "instructor": cols[3].text,
        }
        result.append(lesson)
    return result


def main():
    p = argparse.ArgumentParser(description="MAI Schedule Parser (Selenium)")
    p.add_argument("--weeks", required=True, help="Номера недель через запятую, напр. 13,14,15")
    p.add_argument("--force-groups", action="store_true", help="Принудительно обновить кэш групп")
    p.add_argument("--force-pairs", action="store_true", help="Перезаписать пары, даже если есть кэш")
    args = p.parse_args()

    # парсим номера недель
    try:
        weeks = [int(w.strip()) for w in args.weeks.split(",")]
    except ValueError:
        print("Ошибка: --weeks должен быть списком чисел через запятую.")
        return

    # получаем группы
    groups = get_cached_groups(force=args.force_groups)
    if not groups:
        print("Не найдено ни одной группы.")
        return

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    driver = get_driver()
    try:
        for grp in groups:
            gid = grp["id"]
            name = grp.get("name", str(gid))
            for wk in weeks:
                if not args.force_pairs and get_cached_pairs(conn, gid, wk):
                    print(f"[SKIP] {name} wk={wk} (cached)")
                    continue

                print(f"[RUN ] {name} wk={wk}")
                try:
                    data = scrape_pairs(driver, grp, wk)
                except Exception as e:
                    print(f"  ❌ Ошибка парсинга: {e}")
                    continue

                save_pairs(conn, gid, wk, data)
                # небольшая случайная задержка
                time.sleep(random.uniform(1.0, 2.5))

    finally:
        driver.quit()
        conn.close()


if __name__ == "__main__":
    main()

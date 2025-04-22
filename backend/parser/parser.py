#!/usr/bin/env python3
import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from fake_useragent import UserAgent

from database import get_groups, save_schedule, create_tables
from groups_parser import get_cached_groups

CACHE_FILE = Path("schedule_cache.json")
MAX_THREADS = 6
WEEK_RETRIES = 3


def get_driver():
    ua = UserAgent()
    options = webdriver.EdgeOptions()
    options.add_argument(f"user-agent={ua.random}")
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)


def load_schedule_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_schedule_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_schedule_html(driver, url):
    for attempt in range(WEEK_RETRIES):
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        try:
            WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.step-item"))
            )
            return True
        except Exception:
            print(f"⚠️ Попытка {attempt + 1} не удалась, пробуем снова...")
    return False


def parse_schedule_from_page(driver, group_name, week):
    days = driver.find_elements(By.CSS_SELECTOR, "li.step-item")
    parsed = []
    for day in days:
        try:
            day_name = day.find_element(By.CSS_SELECTOR, "span.step-title").text.strip()
            lessons = day.find_elements(By.CSS_SELECTOR, "div.mb-4")
            for lesson in lessons:
                subject_elem = lesson.find_element(By.CSS_SELECTOR, "p.mb-2.fw-semi-bold.text-dark")
                subject = subject_elem.text.strip().rsplit(" ", 1)[0]

                time_elems = lesson.find_elements(By.CSS_SELECTOR, "li.list-inline-item")
                time_text = time_elems[0].text.strip() if time_elems else ""
                if "–" in time_text:
                    start, end = [t.strip() for t in time_text.split("–")]
                else:
                    start, end = "Неизвестно", "Неизвестно"

                teacher_elems = lesson.find_elements(By.CSS_SELECTOR, "a.text-body")
                teacher = ", ".join(t.text.strip() for t in teacher_elems) if teacher_elems else "Не указан"

                room_elems = [li.text.strip() for li in lesson.find_elements(By.XPATH,
                    ".//li[contains(text(),'ГУК') or contains(text(),'каф') or contains(text(),'Орш')]")]
                room = room_elems[0] if room_elems else "Не указана"

                parsed.append({
                    "week": week,
                    "day": day_name,
                    "start_time": start,
                    "end_time": end,
                    "subject": subject,
                    "teacher": teacher,
                    "room": room
                })
                print(f"  ✅ {day_name}: {subject} ({start}-{end}), {teacher}, {room}")
        except Exception as e:
            print(f"  ❌ Ошибка при парсинге пары: {e}")
            print(day.get_attribute("outerHTML"))
    return parsed


def parse_schedule_for_group(group, weeks, cache):
    group_name = group["name"]
    group_cache = cache.setdefault(group_name, {})
    all_parsed = []

    driver = get_driver()
    for week in weeks:
        print(f"📅 Группа {group_name}, неделя {week}...")

        if str(week) in group_cache:
            url = group_cache[str(week)]
        else:
            url = f"{group['link'].split('&week=')[0]}&week={week}"
            group_cache[str(week)] = url

        if not fetch_schedule_html(driver, url):
            print(f"  ⚠️ Страница {url} так и не загрузилась.")
            continue

        weekly_schedule = parse_schedule_from_page(driver, group_name, week)
        for pair in weekly_schedule:
            pair["group_name"] = group_name
        all_parsed.extend(weekly_schedule)

    driver.quit()
    return all_parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, help="Одна неделя")
    parser.add_argument("--weeks", type=str, help="Несколько недель через запятую (напр. 11,12,13)")
    parser.add_argument("--force-groups", action="store_true", help="Принудительный парсинг групп с сайта")
    args = parser.parse_args()

    create_tables()
    groups = get_cached_groups(force=args.force_groups)

    if args.week:
        weeks = [args.week]
    elif args.weeks:
        weeks = [int(w.strip()) for w in args.weeks.split(",")]
    else:
        weeks = list(range(7, 20))

    print(f"📚 Загружаем расписание на недели: {weeks}")
    schedule_cache = load_schedule_cache()

    def worker(group):
        print(f"▶️ {group['name']}")
        parsed_schedule = parse_schedule_for_group(group, weeks, schedule_cache)
        print(f"💾 Сохраняем {len(parsed_schedule)} занятий для {group['name']}")
        save_schedule(group["name"], parsed_schedule)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as pool:
        pool.map(worker, groups)

    save_schedule_cache(schedule_cache)
    print("✅ Парсинг завершён.")


if __name__ == "__main__":
    main()

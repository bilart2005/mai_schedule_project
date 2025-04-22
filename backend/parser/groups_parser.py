import os
import json
import time
import random

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent

from database import save_groups

GROUPS_URL = "https://mai.ru/education/studies/schedule/groups.php?department=Институт+№8&course=all"
CACHE_FILE = "groups_cache.json"


def get_driver():
    ua = UserAgent()
    options = webdriver.EdgeOptions()
    options.add_argument(f"user-agent={ua.random}")
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")

    edge_path = os.getenv("msedgedriver")
    service = Service(edge_path)
    return webdriver.Edge(service=service, options=options)


def close_popups(driver):
    try:
        banner = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "cookie_message")))
        driver.execute_script("arguments[0].style.display='none';", banner)
    except:
        pass


def scrape_groups():
    driver = get_driver()
    driver.get(GROUPS_URL)
    time.sleep(random.uniform(2, 5))
    close_popups(driver)

    groups = []
    tabs = driver.find_elements(By.CSS_SELECTOR, "ul.nav-segment a.nav-link")
    for tab in tabs:
        try:
            driver.execute_script("arguments[0].click();", tab)
            time.sleep(random.uniform(1, 3))
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn-group")))
            elems = driver.find_elements(By.CSS_SELECTOR, "a.btn-group")
            for e in elems:
                name = e.text.strip()
                link = e.get_attribute("href")
                if name and link:
                    groups.append({"name": name, "link": link})
        except Exception as e:
            print("Ошибка вкладки:", e)
    driver.quit()
    return groups


def get_cached_groups(force=False):
    if not force and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    groups = scrape_groups()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    return groups


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Скачивает список групп")
    p.add_argument("--force", action="store_true", help="Игнорировать кеш и перезаписать")
    args = p.parse_args()

    groups = get_cached_groups(force=args.force)
    save_groups(groups)
    print(f"Сохранено групп: {len(groups)}")

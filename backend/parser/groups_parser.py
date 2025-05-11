import json
import time
import random
import os
import argparse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent

from backend.database.database import DB_PATH, save_groups

# URL для получения списка всех групп ИП-806 (институт №8, все курсы)
GROUPS_URL = (
    "https://mai.ru/education/studies/schedule/groups.php"
    "?department=Институт+№8&course=all"
)
# Файл для локального кеша списка групп
CACHE_FILE = os.path.join(os.path.dirname(__file__), "groups_cache.json")


def get_driver() -> uc.Chrome:
    """Настраивает и возвращает headless Chrome через undetected-chromedriver."""
    ua = UserAgent().random
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument(f"--user-agent={ua}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # При необходимости можно убрать прокси или указать свой путь к бинарнику Chrome:
    # options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    driver = uc.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver


def close_popups(driver: uc.Chrome):
    """Скрывает баннеры cookie или прочие попапы, мешающие скрапингу."""
    try:
        banner = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "cookie_message"))
        )
        driver.execute_script("arguments[0].style.display='none';", banner)
    except Exception:
        pass


def scrape_groups() -> list[dict]:
    """
    Собирает список групп (name, link) со страницы GROUPS_URL.
    Возвращает list[{"name": ..., "link": ...}, ...].
    """
    driver = get_driver()
    driver.get(GROUPS_URL)
    time.sleep(random.uniform(2.0, 5.0))
    close_popups(driver)

    groups = []
    # Вкладки по курсам
    tabs = driver.find_elements(By.CSS_SELECTOR, "ul.nav-segment a.nav-link")
    for tab in tabs:
        try:
            driver.execute_script("arguments[0].click();", tab)
            time.sleep(random.uniform(1.0, 3.0))
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn-group"))
            )
            # Сами группы на вкладке
            elems = driver.find_elements(By.CSS_SELECTOR, "a.btn-group")
            for e in elems:
                name = e.text.strip()
                link = e.get_attribute("href")
                if name and link:
                    groups.append({"name": name, "link": link})
        except Exception as e:
            print("Ошибка при обработке вкладки:", e)
    try:
        driver.quit()
    except Exception:
        pass
    # чтобы локальный драйвер не доживал до деструктора
    driver = None
    return groups


def get_cached_groups(force: bool = False) -> list[dict]:
    """
    Если есть кеш и force=False — читает его из CACHE_FILE.
    Иначе запускает scrape_groups() и сохраняет результат в CACHE_FILE.
    """
    if not force and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    groups = scrape_groups()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    return groups


def main():
    parser = argparse.ArgumentParser(
        description="Скачивает и сохраняет список групп кафедры 806 МАИ"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Игнорировать кеш и перезаписать список групп"
    )
    args = parser.parse_args()

    groups = get_cached_groups(force=args.force)
    save_groups(groups)
    print(f"Сохранено групп: {len(groups)}")


if __name__ == "__main__":
    main()

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from fake_useragent import UserAgent
import time
import random
from database import save_groups

GROUPS_URL = "https://mai.ru/education/studies/schedule/groups.php?department=Институт+№8&course=all"


def get_driver():
    """Создает Selenium-драйвер с рандомным User-Agent"""
    ua = UserAgent()
    user_agent = ua.random

    options = webdriver.EdgeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)
    return driver


def close_popups(driver):
    """Закрывает всплывающие окна (куки, алерты)"""
    try:
        cookie_banner = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "cookie_message")))
        driver.execute_script("arguments[0].style.display = 'none';", cookie_banner)
        print("✅ Куки-баннер скрыт")
    except Exception:
        pass  # Если баннера нет, идем дальше


def get_groups():
    """Парсит список групп, включая скрытые вкладки"""
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


if __name__ == "__main__":
    print("📥 Загружаем список групп...")
    groups = get_groups()
    save_groups(groups)
    print(f"✅ Сохранено {len(groups)} групп в базу данных!")

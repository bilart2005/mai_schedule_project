# 💻 Веб-сервис для отслеживания занятости компьютерных классов кафедры 806 МАИ

Проект предназначен для **автоматизированного сбора и отображения расписания занятий** в IT-аудиториях кафедры 806 Московского авиационного института.

---

## 🚀 Функциональность

| Статус | Компонент                             | Описание                                                                 |
|--------|----------------------------------------|--------------------------------------------------------------------------|
| ✅     | **Парсер расписания**                 | Использует Selenium для получения расписания с сайта МАИ (`scraper.py`) |
| ✅     | **База данных**                        | Локальное хранение данных в SQLite (`mai_schedule.db`)                  |
| ✅     | **Фильтрация IT-аудиторий**           | Отбор только нужных аудиторий по ключевым признакам (`filter_db.py`)    |
| ✅     | **API-сервер**                        | Flask-API для взаимодействия с интерфейсом и внешними сервисами (`api.py`) |
| ✅     | **Интеграция с Google Calendar**      | Автоматическая синхронизация с календарём Google                        |
| ✅     | **Уведомления преподавателей и студентов** | Система уведомлений при изменении расписания                            |
| 🔲     | **Веб-интерфейс**                     | Разработка удобной панели управления и отображения расписания           |
| 🔲     | **CRUD для расписания**               | Редактирование/добавление/удаление пар вручную                          |

---

## 🔧 Установка и запуск

### 📦 Требования

- Python 3.9+
- Установленный Microsoft Edge (или Chromium)
- WebDriver (`msedgedriver`) автоматически ставится через `webdriver-manager`

### 🛠️ Установка

1. Клонируйте репозиторий:

   ```bash
   git clone https://github.com/Diwan1337/mai_schedule_project.git
   cd mai_schedule_project
Создайте виртуальное окружение и активируйте его:

  ```bash
  python -m venv venv
  source venv/bin/activate  # Windows: venv\Scripts\activate
  ```
Установите зависимости:

```bash
pip install -r requirements.txt
```
📁 Структура проекта
```bash
.
├── backend/
│   ├── database/             # Работа с SQLite
│   ├── parser/               # Скрипты парсера (Selenium)
│   ├── api/                  # REST API на Flask
│   └── notifier/             # Вспомогательные утилиты
├── docs
│   ├── Business Requirements
│   ├── System Requrinements
├── mai_schedule.db           # SQLite база
├── requirements.txt          # Зависимости
├── .gitignore
└── README.md                 # Документация проекта
```
📄 Документация
📘 Бизнес-требования: docs/Business Requirements.docx

📘 Системная спецификация (SRS): docs/System Requirements.docx

## 🌳 Прогресс
- **Оценка 3**  
  ✓ Парсер на Selenium  
  ✓ Кэширование и CLI  
  ✓ SQLite  
- **Оценка 4**  
  ✓ Google Calendar  
  ✓ Уведомления  
  △ Оптимизация (в планах)  
- **Оценка 5**  
  ◻ CRUD-интерфейс  
  ◻ Синхронизация  

👥 Авторы проекта:
👨‍💻 
👨‍💻 
👨‍💻 
👩‍💻 

## 📊 Прогресс выполнения

| Номер | Инициалы  |
|-------|-----------|
| 1 | Резинкин Д.В. |
| 2 | Лебедев И.В. |
| 3 | Билый А.Б. |
| 3 | Телепнева А.В. |

🛡️ Лицензия:
Проект распространяется под лицензией MIT License.

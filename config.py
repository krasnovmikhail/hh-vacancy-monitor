import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "Monitor_Vacancy"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

HEADERS = {
    "User-Agent": "VacancyMarketMonitor/0.1 (mikhailkrasnovnn@gmail.com)",
    "Content-Type": "application/x-www-form-urlencoded"
}


# --- ГИБКИЕ ФИЛЬТРЫ ДЛЯ ТЕЛЕГРАМ-АЛЕРТОВ ---
HOT_VACANCIES_ALERT_ENABLED = True

# Минимальная зарплата (поставьте 0 или None, если зарплата неважна)
HOT_VACANCY_MIN_SALARY = None

# Опыт: None = Любой опыт. Или список: ['Нет опыта', 'От 1 года до 3 лет']
FILTER_EXPERIENCE = ['От 1 года до 3 лет', 'Нет опыта']

# Формат работы: None = Любой формат. Или список: ['Удаленная работа', 'Гибридный формат']
FILTER_WORK_FORMATS = ['Удалённо', ] # Игнорируется, пришлет и офис, и удаленку Удалённая

# Навыки: None = Любые навыки. Или список: ['SQL', 'Python', 'Power BI']
FILTER_MUST_HAVE_SKILLS = ['SQL', 'Python', 'Power BI']

# Поисковые запросы и регионы
SEARCH_QUERIES = [
    "аналитик данных", "Data Analyst", "продуктовый аналитик",
    "Product Analyst", "BI аналитик", "BI Analyst",
    "маркетинговый аналитик", "Marketing Analyst", "DWH аналитик", "разработчик BI"
]

AREAS = [1, 2, 113, 1001, 5, 16, 53, 97, 40, 115, 275]
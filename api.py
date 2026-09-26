# api.py
import json
import os
import time
import requests
from config import CLIENT_ID, CLIENT_SECRET, HEADERS

TOKEN_FILE = "token_cache.json"
MAX_RETRIES = 5


def get_access_token():
    """Возвращает закэшированный токен или запрашивает новый у HH API,

    если кэш отсутствует или его срок действия истек.
    """
    # 1. Проверяем наличие закэшированного токена
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Проверяем запас времени (запас 5 минут / 300 секунд)
                if data.get("expires_at", 0) > time.time() + 300:
                    return data.get("access_token")
        except Exception:
            # Если файл поврежден, просто перейдем к запросу нового
            pass

    # 2. Если токена нет или он устарел — запрашиваем новый
    url = "https://hh.ru/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    try:
        response = requests.post(
            url, data=payload, headers=HEADERS, timeout=10
        )

        if not response.ok:
            print(
                f"❌ Ошибка получения токена HH ({response.status_code}): {response.text}"
            )
            response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 14400)

        # 3. Сохраняем в локальный файл-кэш
        cache_data = {
            "access_token": access_token,
            "expires_at": time.time() + expires_in,
        }
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        print("🔑 Успешно получен и закэширован новый OAuth-токен HH.")
        return access_token

    except Exception as e:
        print(f"❌ Не удалось получить токен HH: {e}")
        raise


def get_headers():
    """Формирует заголовки с актуальным OAuth-токеном"""
    return {
        "User-Agent": HEADERS["User-Agent"],
        "Authorization": f"Bearer {get_access_token()}",
    }


def make_request_with_retry(
    url, params=None, max_retries=MAX_RETRIES, timeout=30
):
    """Единый универсальный метод HTTP-запроса с retry-логикой для сети, 429 и таймаутов."""
    wait_time = 5

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url, params=params, headers=get_headers(), timeout=timeout
            )

            # 1. Если HH просит снизить скорость (Rate Limit)
            if response.status_code in (429, 403):
                print(
                    f"⚠️ [Rate Limit / Block {response.status_code}] Попытка {attempt}/{max_retries} для {url}. Ждем {wait_time}с..."
                )
                time.sleep(wait_time)
                wait_time *= 2  #экспоненциальный рост ожидания (5с -> 10с -> 20с...)
                continue

            response.raise_for_status()
            return response.json()

        except (
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
        ) as e:
            if attempt == max_retries:
                print(
                    f"❌ [API Error] Превышено число попыток ({max_retries}) для {url}: {e}"
                )
                raise e

            print(
                f"🔄 [Network Retry {attempt}/{max_retries}] Таймаут или сбой сети на {url}. Повтор через {wait_time}с..."
            )
            time.sleep(wait_time)
            wait_time *= 2

    return {}


def get_vacancies(text, area_id=None, page=0, per_page=100):
    """Поиск вакансий по ключевому слову и региону с защитой от сбоев."""
    url = "https://api.hh.ru/vacancies"
    params = {"text": text, "page": page, "per_page": per_page}
    if area_id:
        params["area"] = area_id

    # Небольшая задержка, чтобы соблюдать RPS (запросов в секунду)
    time.sleep(0.05)
    return make_request_with_retry(url, params=params)


def get_vacancy_detail(vacancy_id):
    """Запрос детальной информации по ID с обработкой Rate Limit и повторами."""
    url = f"https://api.hh.ru/vacancies/{vacancy_id}"
    time.sleep(0.4)
    return make_request_with_retry(url)
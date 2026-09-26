import psycopg2
from config import DB_CONFIG
import json
from db import get_connection


def start_pipeline_run():
    """Создает запись о начале работы пайплайна и возвращает run_id"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pipeline_runs (run_date) VALUES (NOW()) RETURNING run_id;")
    run_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return run_id


def log_vacancy_change(run_id, vacancy_id, action_type, snapshot=None):
    """Фиксирует изменения по вакансии в журнале audit log (CREATED, UPDATED, ARCHIVED)
    и сохраняет слепок полей (title, salary, work_formats и т.д.)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vacancy_changes_log (run_id, vacancy_id, action_type, snapshot) 
                VALUES (%s, %s, %s, %s);
                """,
                (
                    run_id,
                    vacancy_id,
                    action_type,
                    json.dumps(snapshot, ensure_ascii=False)
                    if snapshot
                    else None,
                ),
            )


def finish_pipeline_run(run_id, total_processed, new_count, updated_count, archived_count, duration):
    """Обновляет итоговую агрегированную статистику запускa"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    query = """
    UPDATE pipeline_runs
    SET total_processed = %s,
        new_count = %s,
        updated_count = %s,
        archived_count = %s,
        duration_seconds = %s
    WHERE run_id = %s;
    """
    cursor.execute(query, (total_processed, new_count, updated_count, archived_count, duration, run_id))
    conn.commit()
    cursor.close()
    conn.close()


def sync_archived_vacancies(run_id, days_threshold=3):
    """
    Переводит вакансии в статус is_active = FALSE, если они не встречались N дней.
    Фиксирует их в журнале изменений как ARCHIVED.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Находим ID вакансий для архивации
    find_query = """
    SELECT vacancy_id FROM vacancies 
    WHERE is_active = TRUE AND last_seen_at < NOW() - INTERVAL '%s days';
    """
    cursor.execute(find_query, (days_threshold,))
    archived_ids = [row[0] for row in cursor.fetchall()]

    if archived_ids:
        # Переводим в неактивные
        update_query = """
        UPDATE vacancies SET is_active = FALSE 
        WHERE vacancy_id = ANY(%s);
        """
        cursor.execute(update_query, (archived_ids,))

        # Логируем в детальный журнал
        log_records = [(run_id, v_id, 'ARCHIVED') for v_id in archived_ids]
        from psycopg2.extras import execute_values
        execute_values(
            cursor,
            "INSERT INTO vacancy_changes_log (run_id, vacancy_id, action_type) VALUES %s;",
            log_records
        )

    conn.commit()
    cursor.close()
    conn.close()
    return len(archived_ids)


def make_light_snapshot(data: dict) -> dict:
    """Формирует облегченный JSONB-слепок для таблицы логов (SCD Type 2).
    Исключает статичные и тяжелые поля (description, url).
    """
    if not data:
        return None

    # Поля, динамику изменений которых мы хотим отслеживать
    keys_to_keep = [
        "vacancy_id",
        "title",
        "salary_from",
        "salary_to",
        "salary_currency",
        "salary_gross",
        "experience",
        "employment",
        "work_formats",
        "key_skills",
        "area_name",
        "company_name",
        "company_id",
        "published_at",
        "requirements_snippet",
        "responsibilities_snippet",
    ]

    return {k: data[k] for k in keys_to_keep if k in data}
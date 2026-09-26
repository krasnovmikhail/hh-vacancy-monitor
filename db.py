from contextlib import contextmanager
import psycopg2
from psycopg2.extras import execute_values
from config import DB_CONFIG


@contextmanager
def get_connection():
    """Контекстный менеджер для безопасной работы с БД (автоматически закрывает connection)."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_or_update_vacancy(vacancy_data):
    """Сохраняет новую вакансию или полностью обновляет изменившуюся"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            upsert_query = """
            INSERT INTO vacancies (
                vacancy_id, title, company_name, company_id, area_name, url,
                experience, employment, work_formats, requirements_snippet, responsibilities_snippet,
                salary_from, salary_to, salary_currency, salary_gross, published_at,
                description, content_hash, is_active, first_seen_at, last_seen_at, updated_at
            ) VALUES (
                %(vacancy_id)s, %(title)s, %(company_name)s, %(company_id)s, %(area_name)s, %(url)s,
                %(experience)s, %(employment)s, %(work_formats)s, %(requirements_snippet)s, %(responsibilities_snippet)s,
                %(salary_from)s, %(salary_to)s, %(salary_currency)s, %(salary_gross)s, %(published_at)s,
                %(description)s, %(content_hash)s, TRUE, NOW(), NOW(), NOW()
            )
            ON CONFLICT (vacancy_id) DO UPDATE SET
                title = EXCLUDED.title,
                company_name = EXCLUDED.company_name,
                company_id = EXCLUDED.company_id,
                area_name = EXCLUDED.area_name,
                experience = EXCLUDED.experience,
                employment = EXCLUDED.employment,
                work_formats = EXCLUDED.work_formats,
                salary_from = EXCLUDED.salary_from,
                salary_to = EXCLUDED.salary_to,
                salary_currency = EXCLUDED.salary_currency,
                salary_gross = EXCLUDED.salary_gross,
                description = EXCLUDED.description,
                content_hash = EXCLUDED.content_hash,
                is_active = TRUE,
                last_seen_at = NOW(),
                updated_at = NOW();
            """
            cursor.execute(upsert_query, vacancy_data)

            # Обновление навыков
            skills = vacancy_data.get("key_skills", [])
            if skills:
                cursor.execute(
                    "DELETE FROM vacancy_skills WHERE vacancy_id = %s;",
                    (vacancy_data["vacancy_id"],),
                )
                skills_records = [
                    (vacancy_data["vacancy_id"], skill) for skill in skills
                ]

                insert_skills_query = """
                INSERT INTO vacancy_skills (vacancy_id, skill_name)
                VALUES %s
                ON CONFLICT DO NOTHING;
                """
                execute_values(cursor, insert_skills_query, skills_records)
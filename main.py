import datetime
import time
from api import get_vacancies, get_vacancy_detail
from config import (
    AREAS,
    FILTER_EXPERIENCE,
    FILTER_MUST_HAVE_SKILLS,
    FILTER_WORK_FORMATS,
    HOT_VACANCIES_ALERT_ENABLED,
    HOT_VACANCY_MIN_SALARY,
    SEARCH_QUERIES,
)
from db import (
    get_connection,
    save_or_update_vacancy,
)
from logger import (
    finish_pipeline_run,
    log_vacancy_change,
    start_pipeline_run,
    sync_archived_vacancies,
    make_light_snapshot
)
from notifier import send_telegram_alert
from parser import build_vacancy_record, calculate_vacancy_hash


def load_existing_vacancies_map():
    """Загружает все существующие ID и их хэши из БД в память за 1 быстрый запрос."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vacancy_id, content_hash FROM vacancies;")
            return {row[0]: row[1] for row in cur.fetchall()}


def batch_touch_last_seen(vacancy_ids):
    """Обновляет время последнего просмотра для списка ID за 1 массовый запрос."""
    if not vacancy_ids:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE vacancies 
                SET last_seen_at = NOW(), is_active = TRUE 
                WHERE vacancy_id = ANY(%s);
                """,
                (list(vacancy_ids),),
            )


def check_and_send_hot_alert(vacancy_data):
    """Проверяет вакансию по фильтрам. Если фильтр == None, он игнорируется."""
    if not HOT_VACANCIES_ALERT_ENABLED:
        return

    # 1. Фильтр по ЗАРПЛАТЕ
    if HOT_VACANCY_MIN_SALARY is not None and HOT_VACANCY_MIN_SALARY > 0:
        salary_from = vacancy_data.get("salary_from") or 0
        if salary_from < HOT_VACANCY_MIN_SALARY:
            return

    # 2. Фильтр по ОПЫТУ
    if FILTER_EXPERIENCE is not None:
        if vacancy_data.get("experience") not in FILTER_EXPERIENCE:
            return

    # 3. Фильтр по ФОРМАТУ РАБОТЫ
    if FILTER_WORK_FORMATS is not None:
        vacancy_formats = vacancy_data.get("work_formats") or []
        if not any(fmt in vacancy_formats for fmt in FILTER_WORK_FORMATS):
            return

    # 4. Фильтр по НАВЫКАМ (мягкая проверка: каждый обязательный навык должен содержаться хотя бы в одном навыке вакансии)
    if FILTER_MUST_HAVE_SKILLS is not None:
        vacancy_skills = [
            s.lower() for s in (vacancy_data.get("key_skills") or [])
        ]

        for req_skill in FILTER_MUST_HAVE_SKILLS:
            req_lower = req_skill.lower()
            # Проверяем, есть ли req_lower как подстрока хотя бы в одном навыке вакансии
            found = any(req_lower in v_skill for v_skill in vacancy_skills)
            if not found:
                 return

    # --- ВСЕ ВАЛИДАЦИИ ПРОЙДЕНЫ: ФОРМИРУЕМ И ОТПРАВЛЯЕМ HTML-АЛЕРТ ---
    salary_str = (
        f"от {vacancy_data['salary_from']:,} {vacancy_data.get('salary_currency')}"
        if vacancy_data.get("salary_from")
        else "Не указана"
    )
    skills_str = (
        ", ".join(vacancy_data.get("key_skills", [])[:5]) or "Не указаны"
    )
    formats_str = ", ".join(vacancy_data.get("work_formats", [])) or "Не указан"

    hot_msg = (
        f"🎯 <b>Подходящая вакансия найдена!</b>\n\n"
        f"📌 <a href='{vacancy_data['url']}'>{vacancy_data['title']}</a>\n"
        f"🏢 <b>Компания:</b> {vacancy_data['company_name'] or 'Не указана'}\n"
        f"💰 <b>Зарплата:</b> {salary_str}\n"
        f"👨‍💻 <b>Опыт:</b> {vacancy_data.get('experience') or 'Не указан'}\n"
        f"🏠 <b>Формат:</b> {formats_str}\n"
        f"🛠 <b>Навыки:</b> {skills_str}"
    )
    send_telegram_alert(hot_msg)


def run_query_pipeline(
    search_text, area_id, run_id, stats, existing_map, seen_in_this_run
):
    """Сбор выдачи по поисковому запросу с быстрой проверкой в памяти."""
    first_page = get_vacancies(
        search_text, area_id=area_id, page=0, per_page=100
    )
    total_pages = min(first_page.get("pages", 1), 20)

    for page in range(total_pages):
        data = (
            first_page
            if page == 0
            else get_vacancies(
                search_text, area_id=area_id, page=page, per_page=100
            )
        )
        items = data.get("items", [])

        for item in items:
            v_id = str(item["id"])
            stats["processed"] += 1

            # 1. Сценарий: Новая вакансия (CREATED)
            if v_id not in existing_map:
                detail = get_vacancy_detail(v_id)
                vacancy_data = build_vacancy_record(item, detail=detail)
                save_or_update_vacancy(vacancy_data)

                existing_map[v_id] = vacancy_data["content_hash"]

                #  Передаем snapshot=vacancy_data
                log_vacancy_change(
                    run_id, v_id, "CREATED", snapshot=make_light_snapshot(vacancy_data)
                )
                stats["new"] += 1
                print(f"  ✅ [NEW] {v_id} - {vacancy_data['title']}")

                check_and_send_hot_alert(vacancy_data)

            # 2. Сценарий: Вакансия уже есть (UPDATED / HASH SYNC)
            else:
                search_record = build_vacancy_record(item)
                new_hash = calculate_vacancy_hash(search_record)

                if existing_map[v_id] != new_hash:
                    # Скачиваем детали и обновляем запись в БД
                    detail = get_vacancy_detail(v_id)
                    updated_data = build_vacancy_record(item, detail=detail)
                    save_or_update_vacancy(updated_data)

                    existing_map[v_id] = updated_data["content_hash"]

                    # Фиксируем изменение со снимком!
                    log_vacancy_change(
                        run_id, v_id, "UPDATED", snapshot=make_light_snapshot(updated_data)
                    )
                    stats["updated"] += 1
                    print(f"  🔄 [UPDATE] {v_id} - {updated_data['title']}")

            # 💡 ИСПРАВЛЕНО 2: Вынесено из else! Запоминаем ВСЕ вакансии (и новые, и старые)
            seen_in_this_run.add(v_id)
            time.sleep(0.01)


def parse_entire_market():
    """Главная функция обхода рынка с оптимизированным I/O."""
    start_time = time.time()
    run_id = start_pipeline_run()

    # 1. Загружаем кэш из БД в оперативку
    print("🧠 Загружаем существующие вакансии из БД в память...")
    existing_map = load_existing_vacancies_map()
    print(f"📦 Загружено {len(existing_map)} уникальных вакансий.")

    seen_in_this_run = set()

    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_msg = (
        f"🚀 <b>Запуск ETL-пайплайна HH.ru #{run_id}</b>\n\n"
        f"⏰ <b>Время:</b> {start_time_str}\n"
        f"Статус: Инициализация сбора данных..."
    )
    try:
        send_telegram_alert(start_msg)
    except Exception as e:
        print(f"⚠️ Не удалось отправить стартовое уведомление в Telegram: {e}")

    stats = {"processed": 0, "new": 0, "updated": 0, "archived": 0}
    print(f"🚀 Запуск пайплайна #{run_id}...")

    try:
        for query in SEARCH_QUERIES:
            for area in AREAS:
                try:
                    run_query_pipeline(
                        query,
                        area,
                        run_id,
                        stats,
                        existing_map,
                        seen_in_this_run,
                    )
                except Exception as e:
                    errors_msg = f"❌ Ошибка в пайплайне ({query}, area {area}): {e}"
                    print(f"\n{errors_msg}")
                    send_telegram_alert(errors_msg)

        # Архивация неактивных вакансий (при штатном завершении)
        stats["archived"] = sync_archived_vacancies(run_id, days_threshold=3)

    except KeyboardInterrupt:
        print("\n🛑 Скрипт остановлен пользователем (Ctrl+C). Сохраняем собранные данные...")

    finally:
        # --- ЭТОТ БЛОК ВЫПОЛНИТСЯ ВСЕГДА (в т.ч. при Ctrl+C) ---
        print("⚡️ Пакетное обновление времени просмотра вакансий в БД...")
        try:
            batch_touch_last_seen(seen_in_this_run)
        except Exception as e:
            print(f"⚠️ Ошибка при пакетном обновлении last_seen: {e}")

        duration = round(time.time() - start_time, 2)

        finish_pipeline_run(
            run_id=run_id,
            total_processed=stats["processed"],
            new_count=stats["new"],
            updated_count=stats["updated"],
            archived_count=stats["archived"],
            duration=duration,
        )

        summary_msg = (
            f"📊 <b>Отчет по сбору вакансий</b>\n\n"
            f"🔹 <b>Запуск:</b> #{run_id}\n"
            f"🔹 <b>Всего обработано:</b> {stats['processed']}\n"
            f"✅ <b>Новых вакансий:</b> {stats['new']}\n"
            f"🔄 <b>Обновлено:</b> {stats['updated']}\n"
            f"📦 <b>Отправлено в архив:</b> {stats['archived']}\n"
            f"⏱ <b>Время работы:</b> {duration} сек."
        )
        send_telegram_alert(summary_msg)
        print(
            f"\n🎉 Пайплайн #{run_id} зафиксирован за {duration}с. Отчет отправлен в Telegram."
        )


if __name__ == "__main__":
    try:
        parse_entire_market()
    except Exception as err:
        error_msg = f"🚨 <b>Критический сбой пайплайна!</b>\n\n Ошибка: <code>{err}</code>"
        print(f"\n{error_msg}")
        send_telegram_alert(error_msg)
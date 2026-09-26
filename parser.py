import hashlib
import json


def calculate_vacancy_hash(vacancy_dict):
    """Считает MD5-хэш только по полям из краткой выдачи для быстрого отслеживания изменений"""
    payload = {
        "title": vacancy_dict.get("title"),
        "salary_from": vacancy_dict.get("salary_from"),
        "salary_to": vacancy_dict.get("salary_to"),
        "salary_currency": vacancy_dict.get("salary_currency"),
        "experience": vacancy_dict.get("experience"),
        "work_formats": sorted(vacancy_dict.get("work_formats") or []),
        "company_name": vacancy_dict.get("company_name"),
    }
    data_string = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(data_string.encode("utf-8")).hexdigest()


def build_vacancy_record(item, detail=None):
    """Формирует единую структуру вакансии"""
    salary = item.get("salary") or {}
    employer = item.get("employer") or {}
    area = item.get("area") or {}
    experience = item.get("experience") or {}
    employment = item.get("employment_form") or item.get("employment") or {}
    snippet = item.get("snippet") or {}
    work_formats = item.get("work_format") or []

    record = {
        "vacancy_id": str(item["id"]),
        "title": item.get("name"),
        "company_name": employer.get("name"),
        "company_id": str(employer.get("id")) if employer.get("id") else None,
        "area_name": area.get("name"),
        "url": item.get("alternate_url"),
        "experience": experience.get("name"),
        "employment": employment.get("name"),
        "work_formats": [x.get("name") for x in work_formats if isinstance(x, dict)],
        "requirements_snippet": snippet.get("requirement"),
        "responsibilities_snippet": snippet.get("responsibility"),
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "salary_currency": salary.get("currency"),
        "salary_gross": salary.get("gross"),
        "published_at": item.get("published_at"),
        "description": None,
        "key_skills": [],
        "content_hash": None
    }

    if detail:
        record["description"] = detail.get("description")
        record["key_skills"] = [s["name"] for s in detail.get("key_skills", []) if "name" in s]

    record["content_hash"] = calculate_vacancy_hash(record)
    return record
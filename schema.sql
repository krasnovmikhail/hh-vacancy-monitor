-- 1. Основная таблица вакансий
CREATE TABLE IF NOT EXISTS vacancies (
    vacancy_id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    company_id VARCHAR(50),
    area_name VARCHAR(100),
    url TEXT,
    experience VARCHAR(100),
    employment VARCHAR(100),
    work_formats TEXT[],                        -- Массив строк (гибрид, удаленка и т.д.)
    requirements_snippet TEXT,
    responsibilities_snippet TEXT,
    salary_from INT,
    salary_to INT,
    salary_currency VARCHAR(10),
    salary_gross BOOLEAN,
    description TEXT,                           -- Текст вакансии
    content_hash VARCHAR(32) NOT NULL,           -- MD5-хэш для отслеживания изменений (SCD Type 2)
    is_active BOOLEAN DEFAULT TRUE,              -- Флаг активности вакансии на HH
    published_at TIMESTAMP WITH TIME ZONE,       -- Дата публикации на HH
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Связующая таблица для ключевых навыков (Key Skills)
CREATE TABLE IF NOT EXISTS vacancy_skills (
    vacancy_id VARCHAR(50) REFERENCES vacancies(vacancy_id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (vacancy_id, skill_name)
);

-- 3. Агрегированная статистика по запускам ETL-пайплайна
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    run_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    total_processed INT DEFAULT 0,
    new_count INT DEFAULT 0,
    updated_count INT DEFAULT 0,
    archived_count INT DEFAULT 0,
    duration_seconds NUMERIC(10, 2)
);

-- 4. Журнал изменений (CDC / Audit Log) с JSONB-снапшотом
CREATE TABLE IF NOT EXISTS vacancy_changes_log (
    log_id SERIAL PRIMARY KEY,
    run_id INT REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    vacancy_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(20) NOT NULL,            -- 'CREATED', 'UPDATED', 'ARCHIVED'
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    snapshot JSONB                               -- Полный JSON-слепок вакансии на момент события
);

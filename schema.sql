-- 项目表：记录学习项目基本信息
CREATE TABLE IF NOT EXISTS learning_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    total_pages INTEGER DEFAULT 0,
    current_stage INTEGER DEFAULT 1,
    completed_pages INTEGER DEFAULT 0,
    current_chapter TEXT
);

-- 总结表：支持多个阶段并包含结构化字段
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    stage INTEGER, -- 1: 粗略总结, 2: 深度总结, 3: 补缺总结

    -- 通用原始总结内容
    content TEXT,

    -- 阶段一：结构化字段
    classification TEXT,
    overview TEXT,
    outline TEXT,
    questions TEXT,

    -- 阶段二：结构化字段
    keywords TEXT,
    main_sentences TEXT,
    argument_structure TEXT,
    resolved_questions TEXT,
    unresolved_questions TEXT,

    chapter_title TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES learning_projects(id)
);

-- 章节页码映射表
CREATE TABLE IF NOT EXISTS chapter_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    chapter_title TEXT,
    start_page INTEGER,
    end_page INTEGER,
    section_summary TEXT,
    content_hash TEXT,
    FOREIGN KEY (project_id) REFERENCES learning_projects(id)
);

-- 学习进度记录
CREATE TABLE IF NOT EXISTS progress_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    log_date TEXT NOT NULL,
    studied_minutes INTEGER,
    studied_pages INTEGER,
    FOREIGN KEY (project_id) REFERENCES learning_projects(id)
);

-- 学习计划设置
CREATE TABLE IF NOT EXISTS planning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    daily_minutes INTEGER,
    target_days INTEGER,
    FOREIGN KEY (project_id) REFERENCES learning_projects(id)
);

CREATE TABLE IF NOT EXISTS difficult_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    title TEXT,
    page_or_chapter TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES learning_projects(id)
);

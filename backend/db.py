import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join("projects", "feynmind.db")


def connect():
    return sqlite3.connect(DB_PATH)


# 初始化数据库（可选，推荐用 init_db.py）
def init_db():
    from init_db import init_db as inner_init
    inner_init()


# 添加项目
def add_project(name, file_path, total_pages=0):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO learning_projects (name, file_path, created_at, total_pages)
            VALUES (?, ?, ?, ?)
        """, (name, file_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_pages))
        conn.commit()


# 获取项目 ID
def get_project_id_by_name(name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM learning_projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row[0] if row else None


# 保存结构化总结（支持阶段一、阶段二字段）
def save_summary(project_id, stage, content="", classification=None, overview=None,
                 outline=None, questions=None, keywords=None, main_sentences=None,
                 argument_structure=None, resolved_questions=None, unresolved_questions=None,chapter_title=""):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO summaries (
                project_id, stage, content, classification, overview, outline, questions,
                keywords, main_sentences, argument_structure, resolved_questions, unresolved_questions,
                chapter_title,created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
        """, (
            project_id, stage, content, classification, overview, outline, questions,
            keywords, main_sentences, argument_structure, resolved_questions, unresolved_questions,
            chapter_title,created_at
        ))
        conn.commit()


# 保存章节页码映射
def save_chapter_map(project_id, chapter_title, start_page, end_page, section_summary="", content_hash=""):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chapter_map (
                project_id, chapter_title, start_page, end_page, section_summary, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, chapter_title, start_page, end_page, section_summary, content_hash))
        conn.commit()


# 获取所有项目及其最近的总结
def get_all_projects():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.id, p.name, p.file_path, p.current_stage, p.completed_pages, p.current_chapter,
                s.content, s.created_at
            FROM learning_projects p
            LEFT JOIN (
                SELECT project_id, content, MAX(created_at) as created_at
                FROM summaries GROUP BY project_id
            ) s ON s.project_id = p.id
            ORDER BY p.id DESC
        """)
        return cursor.fetchall()


# 获取章节信息（用于精准问答）
def get_chapter_map_by_project(project_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chapter_title, start_page, end_page, section_summary
            FROM chapter_map
            WHERE project_id = ?
            ORDER BY start_page ASC
        """, (project_id,))
        return cursor.fetchall()


# 保存学习计划
def save_learning_plan(project_id, daily_minutes, target_days):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO planning (project_id, daily_minutes, target_days)
            VALUES (?, ?, ?)
        """, (project_id, daily_minutes, target_days))
        conn.commit()


# 获取学习计划（用于项目管理界面）
def get_learning_plan_by_project_id(project_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT daily_minutes, target_days
            FROM planning
            WHERE project_id = ?
        """, (project_id,))
        row = cursor.fetchone()
        if row:
            return {
                "daily_minutes": row[0],
                "target_days": row[1]
            }
        return None


# 更新学习进度（阶段和页数）
def update_project_progress(project_id, current_stage=None, completed_pages=None):
    with connect() as conn:
        cursor = conn.cursor()
        if current_stage is not None and completed_pages is not None:
            cursor.execute("""
                UPDATE learning_projects
                SET current_stage = ?, completed_pages = ?
                WHERE id = ?
            """, (current_stage, completed_pages, project_id))
        elif current_stage is not None:
            cursor.execute("""
                UPDATE learning_projects
                SET current_stage = ?
                WHERE id = ?
            """, (current_stage, project_id))
        elif completed_pages is not None:
            cursor.execute("""
                UPDATE learning_projects
                SET completed_pages = ?
                WHERE id = ?
            """, (completed_pages, project_id))
        conn.commit()


# 新增函数：单独更新项目阶段
def update_project_stage(project_id: int, stage: int):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE learning_projects SET current_stage = ? WHERE id = ?", (stage, project_id))
        conn.commit()


# 新增函数：单独更新当前章节
def update_current_chapter(project_id: int, chapter: str):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE learning_projects SET current_chapter = ? WHERE id = ?", (chapter, project_id))
        conn.commit()


# 获取完整结构化总结（项目管理用）
def get_full_summary_by_project_id(project_id, stage=0):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT content, classification, overview, outline, questions,
                   keywords, main_sentences, argument_structure,
                   resolved_questions, unresolved_questions, chapter_title
            FROM summaries
            WHERE project_id = ? AND stage = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (project_id, stage))
        row = cursor.fetchone()
        if row:
            return {
                "content": row[0],
                "classification": row[1],
                "overview": row[2],
                "outline": row[3],
                "questions": row[4],
                "keywords": row[5],
                "main_sentences": row[6],
                "argument_structure": row[7],
                "resolved_questions": row[8],
                "unresolved_questions": row[9],
                "chapter_title": row[10]
            }
        return None



# 更新结构化总结
def update_summary(project_id, stage, content, classification, overview, outline, questions,
                   keywords, main_sentences, argument_structure, resolved_questions, unresolved_questions,chapter_title):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE summaries SET
                content = ?, classification = ?, overview = ?, outline = ?, questions = ?,
                keywords = ?, main_sentences = ?, argument_structure = ?, 
                resolved_questions = ?, unresolved_questions = ?,chapter_title = ?
            WHERE project_id = ? AND stage = ?
        """, (
            content, classification, overview, outline, questions,
            keywords, main_sentences, argument_structure, resolved_questions, unresolved_questions,chapter_title,
            project_id, stage,
        ))
        conn.commit()


# 更新章节信息
def update_chapter_map(project_id, old_title, new_title, start_page, end_page):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE chapter_map SET
                chapter_title = ?, start_page = ?, end_page = ?
            WHERE project_id = ? AND chapter_title = ?
        """, (new_title, start_page, end_page, project_id, old_title))
        conn.commit()


# 删除项目及其相关数据
def delete_project(project_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM summaries WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM chapter_map WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM planning WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM progress_logs WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM learning_projects WHERE id = ?", (project_id,))
        conn.commit()


# 获取学习记录
def get_progress_logs_by_project_id(project_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT log_date, studied_minutes, studied_pages
            FROM progress_logs
            WHERE project_id = ?
            ORDER BY log_date ASC
        """, (project_id,))
        return cursor.fetchall()


# 添加学习记录
def log_progress(project_id, studied_minutes, studied_pages):
    with connect() as conn:
        cursor = conn.cursor()

        # 获取当前已完成页数
        cursor.execute("SELECT completed_pages FROM learning_projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        current_completed = row[0] if row else 0

        # 更新学习记录表
        cursor.execute("""
            INSERT INTO progress_logs (project_id, log_date, studied_minutes, studied_pages)
            VALUES (?, ?, ?, ?)
        """, (project_id, datetime.now().strftime("%Y-%m-%d"), studied_minutes, studied_pages))

        # 更新学习项目总完成页数
        new_completed = current_completed + studied_pages
        cursor.execute("""
            UPDATE learning_projects
            SET completed_pages = ?
            WHERE id = ?
        """, (new_completed, project_id))

        conn.commit()

def save_difficult_point(project_id, title, page_or_chapter):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO difficult_points (project_id, title, page_or_chapter, created_at)
            VALUES (?, ?, ?, ?)
        """, (project_id, title, page_or_chapter, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

# db.py 中新增：获取某个项目的所有总结记录（按阶段和时间排序）
def get_summaries_by_project(project_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT stage, content, chapter_title,created_at
            FROM summaries
            WHERE project_id = ?
            ORDER BY stage ASC, created_at DESC
        """, (project_id,))
        return cursor.fetchall()

def get_difficulty_points_by_project(project_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, page_or_chapter, created_at
            FROM difficult_points
            WHERE project_id = ?
            ORDER BY created_at DESC
        """, (project_id,))
        return cursor.fetchall()

def update_difficulty_point(point_id, title, page_or_chapter):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE difficult_points
            SET title = ?, page_or_chapter = ?
            WHERE id = ?
        """, (title, page_or_chapter, point_id))
        conn.commit()

def delete_difficulty_point(point_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM difficult_points WHERE id = ?", (point_id,))
        conn.commit()



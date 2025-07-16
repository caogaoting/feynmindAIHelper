import sqlite3
import os

DB_PATH = os.path.join("projects", "feynmind.db")

def init_db():
    os.makedirs("projects", exist_ok=True)

    SCHEMA = open("schema.sql", "r", encoding="utf-8").read()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA)
        conn.commit()
    print(f"✅ 数据库初始化完成：{DB_PATH}")

if __name__ == "__main__":
    init_db()

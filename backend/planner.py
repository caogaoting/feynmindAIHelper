import os
import json
from datetime import datetime, timedelta

PROJECTS_FILE = "data/projects.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(PROJECTS_FILE):
    with open(PROJECTS_FILE, "w") as f:
        json.dump({}, f)

def load_projects():
    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_projects(data):
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def create_project(name, path, total_pages, daily_time, total_days):
    projects = load_projects()
    projects[name] = {
        "path": path,
        "created_at": str(datetime.now().date()),
        "stage": 1,
        "progress": 0,
        "total_pages": total_pages,
        "pages_read": 0,
        "daily_time": daily_time,
        "total_days": total_days,
        "history": [],
    }
    save_projects(projects)

def get_projects():
    return load_projects()

def get_today_tasks():
    projects = load_projects()
    today = str(datetime.now().date())
    result = {}
    for name, data in projects.items():
        remaining_pages = data["total_pages"] - data["pages_read"]
        remaining_days = data["total_days"] - len(data["history"])
        today_pages = max(1, remaining_pages // max(1, remaining_days))
        result[name] = {
            "stage": data["stage"],
            "today_pages": today_pages,
            "progress": round(data["pages_read"] / data["total_pages"] * 100, 2)
        }
    return result

def update_progress(name, pages_read_today, time_spent_today):
    projects = load_projects()
    if name not in projects:
        return
    project = projects[name]
    project["pages_read"] += pages_read_today
    project["history"].append({
        "date": str(datetime.now().date()),
        "pages": pages_read_today,
        "time": time_spent_today
    })
    if project["pages_read"] >= project["total_pages"] and project["stage"] < 3:
        project["stage"] += 1
    save_projects(projects)

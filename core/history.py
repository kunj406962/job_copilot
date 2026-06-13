import json
import os
import uuid
from datetime import datetime

HISTORY_DIR = "./data/history"


def _ensure_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def save_analysis(
    job_name: str,
    jd_text: str,
    skills: dict,
    gap_analysis: dict,
    selected_entries: list,
    summary: str,
    projects: str,
    experience: str,
    cover_letter: str,
) -> str:
    _ensure_dir()
    analysis_id = str(uuid.uuid4())[:8]
    record = {
        "id": analysis_id,
        "job_name": job_name,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "jd_text": jd_text,
        "skills": skills,
        "gap_analysis": gap_analysis,
        "selected_entries": selected_entries,
        "summary": summary,
        "projects": projects,
        "experience": experience,
        "cover_letter": cover_letter,
    }
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return analysis_id


def load_all() -> list[dict]:
    _ensure_dir()
    records = []
    for fname in sorted(os.listdir(HISTORY_DIR), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(HISTORY_DIR, fname)) as f:
                records.append(json.load(f))
    return records


def load_one(analysis_id: str) -> dict:
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    with open(path) as f:
        return json.load(f)


def delete_analysis(analysis_id: str) -> None:
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    if os.path.exists(path):
        os.remove(path)
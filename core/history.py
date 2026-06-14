import json
import os
import uuid
from datetime import datetime

HISTORY_DIR = "./data/history"


def _ensure_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def save_progress(
    job_name: str,
    jd_text: str,
    skills: dict,
    gap_analysis: dict,
    ranked_entries: list,
    selected_ids: list,
    analysis_id: str = None,
) -> str:
    """Save after search phase. No docs generated yet."""
    _ensure_dir()
    analysis_id = analysis_id or str(uuid.uuid4())[:8]

    # Preserve existing docs if updating an existing record
    existing = {}
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)

    record = {
        "id": analysis_id,
        "job_name": job_name,
        "date": existing.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "jd_text": jd_text,
        "skills": skills,
        "gap_analysis": gap_analysis,
        "ranked_entries": ranked_entries,
        "selected_ids": selected_ids,
        "status": "search_done",
        "summary": existing.get("summary", ""),
        "projects": existing.get("projects", ""),
        "experience": existing.get("experience", ""),
        "cover_letter": existing.get("cover_letter", ""),
    }

    if existing.get("status") == "docs_done":
        record["status"] = "docs_done"

    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return analysis_id


def save_docs(analysis_id: str, summary: str, projects: str, experience: str, cover_letter: str) -> None:
    """Update an existing record with generated docs."""
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    with open(path) as f:
        record = json.load(f)

    record["summary"] = summary
    record["projects"] = projects
    record["experience"] = experience
    record["cover_letter"] = cover_letter
    record["status"] = "docs_done"
    record["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(path, "w") as f:
        json.dump(record, f, indent=2)


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

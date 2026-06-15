"""History persistence helpers for saved analyses and generated documents.

This module writes and reads analysis records from disk so the UI can restore
previous job applications and generated outputs.
"""

import json
import os
import uuid
from datetime import datetime

HISTORY_DIR = "./data/history"  # Local folder for saved analysis records.


def _ensure_dir():
    """Create the history directory if it does not already exist.

    Returns:
        None
    """
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
    """Save a history record after the search phase.

    Args:
        job_name: Display name for the application.
        jd_text: Raw job description text.
        skills: Extracted skill data.
        gap_analysis: Skill gap analysis results.
        ranked_entries: Ranked search results.
        selected_ids: IDs of the entries selected for generation.
        analysis_id: Optional record identifier to update in place.

    Returns:
        The saved analysis ID.

    Side Effects:
        Writes a JSON record to data/history.
    """
    _ensure_dir()
    analysis_id = analysis_id or str(uuid.uuid4())[:8]

    # Keep previously generated documents when a record is refreshed.
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
    """Attach generated documents to an existing history record.

    Args:
        analysis_id: The record to update.
        summary: Generated summary text.
        projects: Generated projects section.
        experience: Generated experience section.
        cover_letter: Generated cover letter text.

    Returns:
        None

    Side Effects:
        Updates the corresponding JSON record on disk.
    """
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
    """Load all history records in reverse chronological filename order.

    Returns:
        A list of saved analysis records.
    """
    _ensure_dir()
    records = []
    for fname in sorted(os.listdir(HISTORY_DIR), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(HISTORY_DIR, fname)) as f:
                records.append(json.load(f))
    return records


def load_one(analysis_id: str) -> dict:
    """Load a single history record by ID.

    Args:
        analysis_id: The record identifier to load.

    Returns:
        The parsed history record.
    """
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    with open(path) as f:
        return json.load(f)


def delete_analysis(analysis_id: str) -> None:
    """Delete a saved history record by ID.

    Args:
        analysis_id: The record identifier to remove.

    Returns:
        None
    """
    path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    if os.path.exists(path):
        os.remove(path)

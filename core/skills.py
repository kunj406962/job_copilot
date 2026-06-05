import json
import os

SKILLS_PATH = "./data/skills.json"


def skills_exists() -> bool:
    return os.path.exists(SKILLS_PATH)


def load_skills() -> dict:
    if not skills_exists():
        return {}
    try:
        with open(SKILLS_PATH, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Skills file is corrupted: {e}")


def save_skills(data: dict) -> None:
    os.makedirs(os.path.dirname(SKILLS_PATH), exist_ok=True)
    with open(SKILLS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def add_category(category: str) -> None:
    skills = load_skills()
    if category not in skills:
        skills[category] = []
    save_skills(skills)


def remove_category(category: str) -> None:
    skills = load_skills()
    skills.pop(category, None)
    save_skills(skills)


def add_skill(category: str, skill: str) -> None:
    skills = load_skills()
    if category not in skills:
        skills[category] = []
    if skill not in skills[category]:
        skills[category].append(skill)
    save_skills(skills)


def remove_skill(category: str, skill: str) -> None:
    skills = load_skills()
    if category in skills and skill in skills[category]:
        skills[category].remove(skill)
    save_skills(skills)

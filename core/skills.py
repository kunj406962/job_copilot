"""Skill registry persistence helpers backed by data/skills.json.

This module stores categorized skills for gap analysis and resume generation.
"""

import json
import os

SKILLS_PATH = "./data/skills.json"  # Local JSON file for categorized skills.


def skills_exists() -> bool:
    """Return whether a skills registry file exists.

    Returns:
        True when data/skills.json is present, otherwise False.
    """
    return os.path.exists(SKILLS_PATH)


def load_skills() -> dict:
    """Load the categorized skills registry from disk.

    Returns:
        A dictionary keyed by category names.

    Raises:
        ValueError: If the JSON file exists but is malformed.
    """
    if not skills_exists():
        return {}
    try:
        with open(SKILLS_PATH, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Skills file is corrupted: {e}")


def save_skills(data: dict) -> None:
    """Persist the categorized skills registry to disk.

    Args:
        data: The full skills dictionary to save.

    Returns:
        None

    Side Effects:
        Creates the data directory if needed and overwrites skills.json.
    """
    os.makedirs(os.path.dirname(SKILLS_PATH), exist_ok=True)
    with open(SKILLS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def add_category(category: str) -> None:
    """Add a skills category if it does not already exist.

    Args:
        category: The category name to add.

    Returns:
        None
    """
    skills = load_skills()
    if category not in skills:
        skills[category] = []
    save_skills(skills)


def remove_category(category: str) -> None:
    """Remove a skills category if present.

    Args:
        category: The category name to remove.

    Returns:
        None
    """
    skills = load_skills()
    skills.pop(category, None)
    save_skills(skills)


def add_skill(category: str, skill: str) -> None:
    """Add a skill to a category without duplicating existing values.

    Args:
        category: The category to update.
        skill: The skill string to append.

    Returns:
        None
    """
    skills = load_skills()
    if category not in skills:
        skills[category] = []
    if skill not in skills[category]:
        skills[category].append(skill)
    save_skills(skills)


def remove_skill(category: str, skill: str) -> None:
    """Remove a skill from a category if it exists.

    Args:
        category: The category to update.
        skill: The skill string to remove.

    Returns:
        None
    """
    skills = load_skills()
    if category in skills and skill in skills[category]:
        skills[category].remove(skill)
    save_skills(skills)

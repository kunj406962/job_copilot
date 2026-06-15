"""Profile storage model for contact details and education history.

This module defines the dataclasses saved to data/profile.json and provides
load/save helpers for the first-run setup and settings screens.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

PROFILE_PATH = "./data/profile.json"  # Local JSON file for user profile data.


@dataclass
class Education:
    degree: str
    institution: str
    graduation_year: str
    gpa: Optional[str] = None


@dataclass
class Profile:
    name: str
    email: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None
    education: list[Education] = field(default_factory=list)

    def save(self) -> None:
        """Persist the profile to disk.

        Returns:
            None

        Side Effects:
            Creates the data directory if needed and overwrites profile.json.
        """
        os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
        with open(PROFILE_PATH, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load() -> "Profile":
        """Load the profile from disk and validate required fields.

        Returns:
            A populated Profile instance.

        Raises:
            FileNotFoundError: If profile.json does not exist.
            ValueError: If the file is corrupted or missing required fields.
        """
        if not os.path.exists(PROFILE_PATH):
            raise FileNotFoundError(f"No profile found at {PROFILE_PATH}. Run first-time setup.")

        try:
            with open(PROFILE_PATH, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Profile file is corrupted: {e}")

        for required in ("name", "email"):
            if not data.get(required):
                raise ValueError(f"Profile is missing required field: '{required}'")

        education = [Education(**e) for e in data.get("education", [])]

        return Profile(
            name=data["name"],
            email=data["email"],
            phone=data.get("phone"),
            linkedin=data.get("linkedin"),
            github=data.get("github"),
            location=data.get("location"),
            education=education,
        )


def profile_exists() -> bool:
    """Return whether a saved profile file exists.

    Returns:
        True when data/profile.json is present, otherwise False.
    """
    return os.path.exists(PROFILE_PATH)



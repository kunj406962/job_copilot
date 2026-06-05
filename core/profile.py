import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

PROFILE_PATH = "./data/profile.json"


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
        os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
        with open(PROFILE_PATH, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load() -> "Profile":
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
    return os.path.exists(PROFILE_PATH)



import os
import json
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv
from core.database import get_top_entries
from core.profile import Profile
from core.skills import load_skills

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_MODEL = "gemini-2.5-flash"

STRONG_MATCH = 0.40
PARTIAL_MATCH = 0.70


def _call_gemini(prompt: str) -> str:
    for attempt in range(5):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except ClientError as e:
            err = str(e)
            if ("429" in err or "503" in err) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"API limit hit — waiting {wait}s, retry {attempt + 1}/5...")
                time.sleep(wait)
            else:
                raise


def _format_skills_for_prompt(skills_data: dict) -> str:
    if not skills_data:
        return "No structured skills provided."
    lines = []
    for category, skills in skills_data.items():
        if skills:
            lines.append(f"{category}: {', '.join(skills)}")
    return "\n".join(lines)


def _format_entries_for_prompt(entries: list[dict]) -> str:
    if not entries:
        return ""
    sections = []
    for e in entries:
        lines = [f"{e['name']}"]
        if e.get("stack"):
            lines.append(f"Stack: {e['stack']}")
        if e.get("role"):
            lines.append(f"Role: {e['role']}")
        if e.get("description"):
            lines.append(f"Description: {e['description']}")
        for bullet in e["bullets"]:
            lines.append(f"- {bullet}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def extract_skills(jd_text: str) -> dict:
    prompt = f"""
    Extract skills and a role summary from this job description.
    Return ONLY a JSON object, no markdown, no explanation.

    Format:
    {{
    "role_summary": "one sentence describing the role",
    "required": ["skill1", "skill2"],
    "nice_to_have": ["skill3"],
    "soft": ["skill4"]
    }}

    Job Description:
    {jd_text}
    """
    raw = _call_gemini(prompt)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON for skill extraction: {e}\nRaw: {raw}")


def analyze_gaps(skills: dict, skills_data: dict) -> dict:
    all_skills = (
        [("required", s) for s in skills.get("required", [])] +
        [("nice_to_have", s) for s in skills.get("nice_to_have", [])] +
        [("soft", s) for s in skills.get("soft", [])]
    )

    all_known_skills = [
        s.lower()
        for skill_list in skills_data.values()
        for s in skill_list
    ]

    results = []
    total_score = 0

    for skill_type, skill in all_skills:
        skill_lower = skill.lower()
        skills_json_match = any(
            skill_lower in known or known in skill_lower
            for known in all_known_skills
        )

        if skills_json_match:
            status = "strong"
            confidence = 95
            distance = 0.05
        else:
            status = "missing"
            confidence = 0
            distance = 2.0

        total_score += confidence
        results.append({
            "skill": skill,
            "type": skill_type,
            "status": status,
            "confidence": confidence,
            "distance": round(distance, 4),
        })

    overall = round(total_score / len(results)) if results else 0
    missing = [r["skill"] for r in results if r["status"] == "missing"]

    return {
        "overall_match": overall,
        "skills": results,
        "missing_skills": missing,
    }


def generate_summary(jd_text: str, entries: dict, profile: Profile, skills_data: dict) -> str:
    all_entries = entries["projects"] + entries["jobs"] + entries["softskills"]
    context = _format_entries_for_prompt(all_entries)
    skills_text = _format_skills_for_prompt(skills_data)

    prompt = f"""
    Write a 3-4 sentence professional resume summary for {profile.name} tailored to this job.
    Tone should match the job — startup = energetic, corporate = polished.
    Do NOT use the phrase "results-driven". Return only the summary text, no labels or headings.

    Candidate skills:
    {skills_text}

    Relevant experience:
    {context}

    Job Description:
    {jd_text}
    """
    return _call_gemini(prompt)


def generate_projects(jd_text: str, projects: list[dict], profile: Profile, skills_data: dict) -> str:
    if not projects:
        return ""
    context = _format_entries_for_prompt(projects)
    skills_text = _format_skills_for_prompt(skills_data)

    prompt = f"""
    You are a professional resume writer. Create a Projects section for {profile.name}'s resume.

    Rules:
    - Use the project names provided as headings exactly as given
    - Select and include the most relevant bullets for this job (minimum 2, maximum 4 per project)
    - Rewrite bullets to match the job description language and keywords
    - Do NOT invent experience — only use what is provided
    - Use strong action verbs
    - Return ONLY the project headings and bullets, no extra commentary

    Format:
    Project Name
    - Bullet point
    - Bullet point

    Candidate skills:
    {skills_text}

    Projects:
    {context}

    Job Description:
    {jd_text}
    """
    return _call_gemini(prompt)


def generate_experience(jd_text: str, jobs: list[dict], profile: Profile, skills_data: dict) -> str:
    if not jobs:
        return ""
    context = _format_entries_for_prompt(jobs)
    skills_text = _format_skills_for_prompt(skills_data)

    prompt = f"""
    You are a professional resume writer. Create a Work Experience section for {profile.name}'s resume.

    Rules:
    - Use the job/company names as headings exactly as given
    - Select the most relevant bullets (minimum 2, maximum 4 per role)
    - Rewrite bullets to match the job description language and keywords
    - Do NOT invent experience — only use what is provided
    - Use strong action verbs
    - Return ONLY the headings and bullets, no extra commentary

    Format:
    Job Title — Company
    - Bullet point
    - Bullet point

    Candidate skills:
    {skills_text}

    Work Experience:
    {context}

    Job Description:
    {jd_text}
    """
    return _call_gemini(prompt)


def generate_cover_letter(jd_text: str, entries: dict, profile: Profile, skills_data: dict) -> str:
    all_entries = entries["projects"] + entries["jobs"]
    context = _format_entries_for_prompt(all_entries)
    skills_text = _format_skills_for_prompt(skills_data)
    edu = profile.education[0] if profile.education else None
    edu_line = f"{edu.degree} from {edu.institution}" if edu else ""

    prompt = f"""
    Write a professional cover letter for {profile.name} applying to this job.
    Contact: {profile.email} | {profile.location or ""}
    Education: {edu_line}

    Candidate skills:
    {skills_text}

    Relevant experience:
    {context}

    Job Description:
    {jd_text}

    Keep it to 3 paragraphs. Do not include a date or address header. Return only the cover letter text.
    """
    return _call_gemini(prompt)


def run_analysis(jd_text: str, profile: Profile) -> dict:
    skills_data = load_skills()

    # Step 1 — extract skills + role summary (1 Gemini call)
    skills = extract_skills(jd_text)
    gap_analysis = analyze_gaps(skills, skills_data)

    # Step 2 — build single retrieval query (1 embedding call)
    all_keywords = (
        skills.get("required", []) +
        skills.get("nice_to_have", []) +
        skills.get("soft", [])
    )
    role_summary = skills.get("role_summary", "")
    query_text = f"{role_summary} {' '.join(all_keywords)}"

    # Step 3 — retrieve top entries using hybrid scoring
    entries = get_top_entries(
        query_text=query_text,
        keywords=all_keywords,
        top_projects=3,
        top_jobs=2,
    )

    # Step 4 — generate all sections
    summary = generate_summary(jd_text, entries, profile, skills_data)
    projects = generate_projects(jd_text, entries["projects"], profile, skills_data)
    experience = generate_experience(jd_text, entries["jobs"], profile, skills_data)
    cover_letter = generate_cover_letter(jd_text, entries, profile, skills_data)

    return {
        "skills": skills,
        "gap_analysis": gap_analysis,
        "entries_used": entries,
        "summary": summary,
        "projects": projects,
        "experience": experience,
        "cover_letter": cover_letter,
    }
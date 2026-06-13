import os
import json
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv
from core.database import get_top_entries, query_entries, hybrid_score
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
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw}")


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
        match = any(
            skill_lower in known or known in skill_lower
            for known in all_known_skills
        )
        status = "strong" if match else "missing"
        confidence = 95 if match else 0
        total_score += confidence
        results.append({
            "skill": skill,
            "type": skill_type,
            "status": status,
            "confidence": confidence,
            "distance": 0.05 if match else 2.0,
        })

    overall = round(total_score / len(results)) if results else 0
    missing = [r["skill"] for r in results if r["status"] == "missing"]

    return {
        "overall_match": overall,
        "skills": results,
        "missing_skills": missing,
    }


def search_entries(jd_text: str, skills: dict) -> dict:
    """
    Phase 1 — vector search only.
    Returns all entries ranked by hybrid score with top picks flagged.
    No generation calls.
    """
    all_keywords = (
        skills.get("required", []) +
        skills.get("nice_to_have", []) +
        skills.get("soft", [])
    )
    role_summary = skills.get("role_summary", "")
    query_text = f"{role_summary} {' '.join(all_keywords)}"

    # Get all entries ranked by hybrid score
    from core.database import get_all_entries
    all_entries = get_all_entries()

    if not all_entries:
        return {"ranked": [], "keywords": all_keywords, "query_text": query_text}

    # Run semantic query for distances
    from core.database import query_entries
    semantic_results = query_entries(query_text, n_results=len(all_entries))

    # Build a distance lookup by entry id
    distance_map = {r["id"]: r["distance"] for r in semantic_results}

    # Score all entries
    ranked = []
    for entry in all_entries:
        entry["distance"] = distance_map.get(entry.get("id", ""), 1.0)
        # Build document string for keyword matching since get_all_entries doesnt include it
        entry["document"] = f"{entry.get('name', '')} {entry.get('stack', '')} {' '.join(entry.get('bullets', []))}"
        entry["score"] = hybrid_score(entry, all_keywords)
        ranked.append(entry)

    # Sort by score descending
    ranked.sort(key=lambda x: x["score"], reverse=True)

    # Flag top 3 projects and top 2 jobs as AI picks
    project_count = 0
    job_count = 0
    for entry in ranked:
        entry["ai_pick"] = False
        if entry["type"] == "project" and project_count < 3:
            entry["ai_pick"] = True
            project_count += 1
        elif entry["type"] == "job" and job_count < 2:
            entry["ai_pick"] = True
            job_count += 1

    return {
        "ranked": ranked,
        "keywords": all_keywords,
        "query_text": query_text,
    }


def generate_documents(
    jd_text: str,
    profile: Profile,
    selected_entries: list[dict],
    skills_data: dict,
) -> dict:
    """
    Phase 2 — document generation only.
    Takes pre-selected entries, runs 3 Gemini calls.
    """
    projects = [e for e in selected_entries if e["type"] == "project"]
    jobs = [e for e in selected_entries if e["type"] == "job"]
    softskills = [e for e in selected_entries if e["type"] == "softskill"]

    all_chunks = projects + jobs + softskills
    skills_text = _format_skills_for_prompt(skills_data)

    # Summary
    summary_prompt = f"""
    Write a 3-4 sentence professional resume summary for {profile.name} tailored to this job.
    Tone should match the job — startup = energetic, corporate = polished.
    Do NOT use the phrase "results-driven". Return only the summary text, no labels or headings.

    Candidate skills:
    {skills_text}

    Relevant experience:
    {_format_entries_for_prompt(all_chunks)}

    Job Description:
    {jd_text}
    """
    summary = _call_gemini(summary_prompt)

    # Projects section
    if projects:
        projects_prompt = f"""
    You are a professional resume writer. Create a Projects section for {profile.name}'s resume.

    Rules:
    - Use the project names as headings exactly as given
    - Select the most relevant bullets (minimum 2, maximum 4 per project)
    - Rewrite bullets to match the job description language and keywords
    - Do NOT invent experience
    - Use strong action verbs
    - Return ONLY headings and bullets, no extra commentary

    Format:
    Project Name
    - Bullet point
    - Bullet point

    Candidate skills:
    {skills_text}

    Projects:
    {_format_entries_for_prompt(projects)}

    Job Description:
    {jd_text}
    """
        projects_text = _call_gemini(projects_prompt)
    else:
        projects_text = ""

    # Experience section
    if jobs:
        experience_prompt = f"""
        You are a professional resume writer. Create a Work Experience section for {profile.name}'s resume.

        Rules:
        - Use job/company names as headings exactly as given
        - Select the most relevant bullets (minimum 2, maximum 4 per role)
        - Rewrite bullets to match the job description language
        - Do NOT invent experience
        - Use strong action verbs
        - Return ONLY headings and bullets, no extra commentary

        Format:
        Job Title — Company
        - Bullet point

        Candidate skills:
        {skills_text}

        Work Experience:
        {_format_entries_for_prompt(jobs)}

        Job Description:
        {jd_text}
        """
        experience_text = _call_gemini(experience_prompt)
    else:
        experience_text = ""

    # Cover letter
    edu = profile.education[0] if profile.education else None
    edu_line = f"{edu.degree} from {edu.institution}" if edu else ""
    cover_prompt = f"""
    Write a professional cover letter for {profile.name} applying to this job.
    Contact: {profile.email} | {profile.location or ""}
    Education: {edu_line}

    Candidate skills:
    {skills_text}

    Relevant experience:
    {_format_entries_for_prompt(all_chunks)}

    Job Description:
    {jd_text}

    Keep it to 3 paragraphs. Do not include a date or address header. Return only the cover letter text.
    """
    cover_letter = _call_gemini(cover_prompt)

    return {
        "summary": summary,
        "projects": projects_text,
        "experience": experience_text,
        "cover_letter": cover_letter,
    }


def run_analysis(jd_text: str, profile: Profile) -> dict:
    """Legacy single-call entry point. Used for backward compat."""
    skills_data = load_skills()
    skills = extract_skills(jd_text)
    gap_analysis = analyze_gaps(skills, skills_data)
    search_results = search_entries(jd_text, skills)
    selected = [e for e in search_results["ranked"] if e.get("ai_pick")]
    docs = generate_documents(jd_text, profile, selected, skills_data)

    return {
        "skills": skills,
        "gap_analysis": gap_analysis,
        "entries_used": {"projects": [e for e in selected if e["type"] == "project"],
                         "jobs": [e for e in selected if e["type"] == "job"],
                         "softskills": []},
        **docs,
    }
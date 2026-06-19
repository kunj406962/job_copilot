import os
import json
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv
from core.database import get_top_entries, query_entries, hybrid_score, get_all_entries
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


def _build_known_skills_set(skills_data: dict) -> set[str]:
    """
    Build a flat set of known skill strings from skills_data.
    Includes both category names AND individual skill values,
    all lowercased for case-insensitive matching.
    """
    known = set()
    for category, skills in skills_data.items():
        # Include the category name itself as a known skill
        known.add(category.lower())
        for skill in skills:
            known.add(skill.lower())
    return known


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

    # Include category names in matching so "Data Structures and Algorithms"
    # as a category name counts as a known skill
    known = _build_known_skills_set(skills_data)

    results = []
    total_score = 0

    for skill_type, skill in all_skills:
        skill_lower = skill.lower()

        # Match if skill is contained in any known term, or any known term
        # is contained in the skill (handles abbreviations and category names)
        match = any(
            skill_lower in known_term or known_term in skill_lower
            for known_term in known
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
    """Phase 1 — vector search only. Returns all entries ranked by hybrid score."""
    all_keywords = (
        skills.get("required", []) +
        skills.get("nice_to_have", []) +
        skills.get("soft", [])
    )
    role_summary = skills.get("role_summary", "")
    query_text = f"{role_summary} {' '.join(all_keywords)}"

    all_entries = get_all_entries()

    if not all_entries:
        return {"ranked": [], "keywords": all_keywords, "query_text": query_text}

    semantic_results = query_entries(query_text, n_results=len(all_entries))
    distance_map = {r["id"]: r["distance"] for r in semantic_results}

    ranked = []
    for entry in all_entries:
        entry["distance"] = distance_map.get(entry.get("id", ""), 1.0)
        entry["document"] = (
            f"{entry.get('name', '')} {entry.get('stack', '')} "
            f"{' '.join(entry.get('bullets', []))}"
        )
        entry["score"] = hybrid_score(entry, all_keywords)
        ranked.append(entry)

    ranked.sort(key=lambda x: x["score"], reverse=True)

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
    accepted_rewrites: dict = None,
) -> dict:
    """
    Phase 2 — document generation.
    accepted_rewrites: {original_bullet: new_bullet} — substituted before prompting.
    Does not touch ChromaDB.
    """
    # Apply accepted rewrites to entry bullets before building prompts
    if accepted_rewrites:
        patched = []
        for entry in selected_entries:
            e = dict(entry)
            e["bullets"] = [
                accepted_rewrites.get(b, b) for b in e.get("bullets", [])
            ]
            patched.append(e)
        selected_entries = patched

    projects = [e for e in selected_entries if e["type"] == "project"]
    jobs = [e for e in selected_entries if e["type"] == "job"]
    softskills = [e for e in selected_entries if e["type"] == "softskill"]

    all_chunks = projects + jobs + softskills
    skills_text = _format_skills_for_prompt(skills_data)

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


def suggest_gap_fixes(
    gap_analysis: dict,
    selected_entries: list[dict],
    skills_data: dict,
) -> list[dict]:
    """
    Analyse missing/partial skills against ONLY the selected entries.
    Returns suggestions with fix_type, suggested_category for skill additions,
    and per-suggestion status (pending/accepted/declined).
    Does NOT touch ChromaDB.
    """
    gaps = [
        s["skill"] for s in gap_analysis["skills"]
        if s["status"] in ("missing", "partial")
    ]

    if not gaps or not selected_entries:
        return []

    entries_context = _format_entries_for_prompt(selected_entries)
    skills_text = _format_skills_for_prompt(skills_data)

    # Pass existing category names so Gemini can suggest the right one
    existing_categories = list(skills_data.keys())
    categories_str = ", ".join(existing_categories) if existing_categories else "none"

    prompt = f"""
    You are a careful, conservative resume analyst. For each skill gap listed below,
    examine ONLY the candidate's experience and skills provided.

    Determine if each gap is:
    - GENUINE GAP: no related experience exists at all
    - PHRASING GAP: the experience clearly demonstrates this skill or a very close
    equivalent but it is not explicitly named

    CRITICAL RULES:
    - Be conservative. If uncertain, default to GENUINE GAP.
    - Never invent or imply experience not clearly present in the provided text.
    - Only flag PHRASING GAP if the connection is obvious and defensible in an interview.
    - For PHRASING GAP with fix_type "add_skill": suggest which EXISTING category it
    belongs to from the list provided. Only suggest a NEW category name if none of
    the existing ones fit at all.
    - For PHRASING GAP with fix_type "reword_bullet": the reworded bullet must be
    factually identical — only phrasing changes, no invented claims.
    - Before suggesting to add a skill, check if it or a very close synonym already
    exists in the candidate's skills or category names. If it does, mark as
    GENUINE GAP (already covered) and set fix_type to "none".

    Existing skill categories:
    {categories_str}

    Candidate's full skills registry:
    {skills_text}

    Candidate's selected experience:
    {entries_context}

    Skill gaps to evaluate:
    {', '.join(gaps)}

    Return ONLY a JSON array, no markdown. Each object:
    {{
    "skill": "gap skill name",
    "verdict": "phrasing_gap" | "genuine_gap",
    "reasoning": "one sentence explaining why",
    "fix_type": "add_skill" | "reword_bullet" | "none",
    "suggested_category": "existing or new category name, or null",
    "target_entry": "entry name if reword_bullet, else null",
    "suggested_skill": "skill string to add, or null",
    "original_bullet": "exact original bullet text, or null",
    "suggested_bullet": "reworded bullet, or null",
    "status": "pending"
    }}
    """
    raw = _call_gemini(prompt)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        suggestions = json.loads(clean)
        # Ensure every suggestion has a status field
        for s in suggestions:
            if "status" not in s:
                s["status"] = "pending"
        return suggestions
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON for gap suggestions: {e}\nRaw: {raw}")


def run_analysis(jd_text: str, profile: Profile) -> dict:
    """Legacy single-call entry point."""
    skills_data = load_skills()
    skills = extract_skills(jd_text)
    gap_analysis = analyze_gaps(skills, skills_data)
    search_results = search_entries(jd_text, skills)
    selected = [e for e in search_results["ranked"] if e.get("ai_pick")]
    docs = generate_documents(jd_text, profile, selected, skills_data)

    return {
        "skills": skills,
        "gap_analysis": gap_analysis,
        "entries_used": {
            "projects": [e for e in selected if e["type"] == "project"],
            "jobs": [e for e in selected if e["type"] == "job"],
            "softskills": [],
        },
        **docs,
    }
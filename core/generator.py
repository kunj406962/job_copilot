"""Job-description analysis and Gemini generation pipeline.

This module extracts skills from a job description, scores stored experience,
and generates resume and cover-letter content using Gemini.
"""

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
_MODEL = "gemini-2.5-flash"  # Primary text-generation model for analysis.

STRONG_MATCH = 0.40  # Reserved threshold for future match classification.
PARTIAL_MATCH = 0.70  # Reserved threshold for future match classification.


def _call_gemini(prompt: str) -> str:
    """Call Gemini with retry handling for transient quota errors.

    Args:
        prompt: The prompt to send to the model.

    Returns:
        The trimmed text response from Gemini.

    Side Effects:
        Retries on 429 and 503 errors with incremental sleeps.
    """
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
    """Format the structured skills registry for prompt inclusion.

    Args:
        skills_data: Skills grouped by category.

    Returns:
        A newline-delimited string ready for prompt insertion.
    """
    if not skills_data:
        return "No structured skills provided."
    lines = []
    for category, skills in skills_data.items():
        if skills:
            lines.append(f"{category}: {', '.join(skills)}")
    return "\n".join(lines)


def _format_entries_for_prompt(entries: list[dict]) -> str:
    """Format ranked experience entries for prompt inclusion.

    Args:
        entries: Entry dictionaries to render.

    Returns:
        A newline-delimited description of the provided entries.
    """
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
    """Extract a role summary and skill lists from a job description.

    Args:
        jd_text: Raw job description text.

    Returns:
        A parsed JSON object with role_summary, required, nice_to_have, and
        soft skill lists.

    Side Effects:
        Makes a Gemini text-generation call and may raise if the response is
        not valid JSON.
    """
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
    """Compare extracted skills against the saved skills registry.

    Args:
        skills: Skills parsed from the job description.
        skills_data: Categorized skills stored locally.

    Returns:
        A match summary with per-skill confidence and missing skills.
    """
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
    """Rank stored experience for a job description without generating text.

    Args:
        jd_text: Raw job description text.
        skills: Extracted job skills used to build the search query.

    Returns:
        Ranked entries plus the keywords and query text used for retrieval.

    Side Effects:
        Calls the ChromaDB retrieval layer and mutates the returned entries with
        score and ai_pick flags.
    """
    all_keywords = (
        skills.get("required", []) +
        skills.get("nice_to_have", []) +
        skills.get("soft", [])
    )
    role_summary = skills.get("role_summary", "")
    query_text = f"{role_summary} {' '.join(all_keywords)}"

    # Load the full store first so we can score every entry consistently.
    from core.database import get_all_entries
    all_entries = get_all_entries()

    if not all_entries:
        return {"ranked": [], "keywords": all_keywords, "query_text": query_text}

    # Use the semantic query only for distances, then blend with keyword score.
    from core.database import query_entries
    semantic_results = query_entries(query_text, n_results=len(all_entries))

    # Build a lookup so each stored entry can be scored even if it was not
    # returned in the exact semantic ranking order.
    distance_map = {r["id"]: r["distance"] for r in semantic_results}

    # Score every entry before sorting so the final list reflects both signals.
    ranked = []
    for entry in all_entries:
        entry["distance"] = distance_map.get(entry.get("id", ""), 1.0)
        # Build document string for keyword matching since get_all_entries doesnt include it
        entry["document"] = f"{entry.get('name', '')} {entry.get('stack', '')} {' '.join(entry.get('bullets', []))}"
        entry["score"] = hybrid_score(entry, all_keywords)
        ranked.append(entry)

    # Highest blended score should appear first in the UI.
    ranked.sort(key=lambda x: x["score"], reverse=True)

    # Preselect a small number of strong candidates to reduce manual review.
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
    """Generate resume sections and a cover letter from selected entries.

    Args:
        jd_text: Raw job description text.
        profile: The user's saved profile.
        selected_entries: Manually selected or AI-picked experience entries.
        skills_data: Structured skills registry for prompt context.

    Returns:
        A dictionary containing summary, projects, experience, and cover letter.

    Side Effects:
        Makes multiple Gemini calls to generate tailored content.
    """
    projects = [e for e in selected_entries if e["type"] == "project"]
    jobs = [e for e in selected_entries if e["type"] == "job"]
    softskills = [e for e in selected_entries if e["type"] == "softskill"]

    all_chunks = projects + jobs + softskills
    skills_text = _format_skills_for_prompt(skills_data)

    # Generate the summary first so the output has a concise top-level pitch.
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

    # Generate a projects section only when relevant entries exist.
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

    # Generate a work-experience section only when relevant job entries exist.
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

    # Use the generated context to produce a separate cover letter.
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


def suggest_gap_fixes(gap_analysis: dict, selected_entries: list[dict], skills_data: dict) -> list[dict]:
    """
    Analyze missing/partial skills against ONLY the selected entries.
    Distinguishes genuine gaps (no related experience) from phrasing gaps
    (experience exists but isn't worded to surface the skill).

    Returns a list of suggestion dicts:
    {
        "skill": "Relational Databases",
        "verdict": "phrasing_gap" | "genuine_gap",
        "reasoning": "...",
        "fix_type": "add_skill" | "reword_bullet" | "none",
        "target_entry": "YYC Track" or None,
        "suggested_skill": "SQL" or None,
        "original_bullet": "..." or None,
        "suggested_bullet": "..." or None,
    }
    """
    gaps = [
        s["skill"] for s in gap_analysis["skills"]
        if s["status"] in ("missing", "partial")
    ]

    if not gaps:
        return []

    if not selected_entries:
        return []

    entries_context = _format_entries_for_prompt(selected_entries)
    skills_text = _format_skills_for_prompt(skills_data)

    prompt = f"""
    You are a careful, conservative resume analyst. For each skill gap listed below,
    examine ONLY the candidate's experience provided. Determine if this is a
    GENUINE GAP (no related experience exists at all) or a PHRASING GAP
    (the experience clearly demonstrates this skill or a very close equivalent,
    but it is not explicitly named or surfaced).

    CRITICAL RULES:
    - Be conservative. If uncertain, default to GENUINE GAP and suggest nothing.
    - Never invent or imply experience that is not clearly present in the provided text.
    - Only flag a PHRASING GAP if the connection is obvious and defensible in an interview.
    - For phrasing gaps, suggest EITHER adding a skill to the registry (if clearly true)
    OR rewording one existing bullet to surface the skill (not both, pick the better fix).
    - Reworded bullets must stay factually identical — only phrasing changes.

    Candidate's current skills registry:
    {skills_text}

    Candidate's selected experience for this job:
    {entries_context}

    Skill gaps to evaluate:
    {', '.join(gaps)}

    Return ONLY a JSON array, no markdown, no explanation. Format:
    [
        {{
            "skill": "Relational Databases",
            "verdict": "phrasing_gap",
            "reasoning": "Candidate designed MongoDB schemas with aggregation pipelines, showing strong database design skills, but no relational DB is explicitly mentioned.",
            "fix_type": "add_skill",
            "target_entry": null,
            "suggested_skill": null,
            "original_bullet": null,
            "suggested_bullet": null
        }},
        {{
            "skill": "Ruby",
            "verdict": "genuine_gap",
            "reasoning": "No experience with Ruby or Ruby on Rails appears anywhere in the provided experience.",
            "fix_type": "none",
            "target_entry": null,
            "suggested_skill": null,
            "original_bullet": null,
            "suggested_bullet": null
        }}
    ]
    """
    raw = _call_gemini(prompt)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        suggestions = json.loads(clean)
        return suggestions
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON for gap suggestions: {e}\\nRaw: {raw}")


def run_analysis(jd_text: str, profile: Profile) -> dict:
    """Run the full analysis flow for a job description.

    Args:
        jd_text: Raw job description text.
        profile: The user's saved profile.

    Returns:
        A combined analysis result with skills, gap analysis, and generated
        document content.
    """
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
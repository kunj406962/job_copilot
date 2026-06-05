import os
import json
import time
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv
from core.database import query_chunks, get_chunks_by_category
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


def extract_skills(jd_text: str) -> dict:
    prompt = f"""
        Extract skills from this job description. Return ONLY a JSON object, no markdown, no explanation.

        Format:
        {{
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

    # Flatten skills.json into one searchable list
    all_known_skills = [
        s.lower()
        for skill_list in skills_data.values()
        for s in skill_list
    ]

    results = []
    total_score = 0

    for skill_type, skill in all_skills:
        # Check skills.json first — exact/partial string match
        skill_lower = skill.lower()
        skills_json_match = any(
            skill_lower in known or known in skill_lower
            for known in all_known_skills
        )

        if skills_json_match:
            # Strong match from structured skills registry
            status = "strong"
            confidence = 95
            distance = 0.05
        else:
            # Fall back to ChromaDB semantic search
            chunks = query_chunks(skill, n_results=1)
            if not chunks:
                distance = 2.0
            else:
                distance = chunks[0]["distance"]

            if distance < STRONG_MATCH:
                status = "strong"
                confidence = round((1 - distance / 2) * 100)
            elif distance < PARTIAL_MATCH:
                status = "partial"
                confidence = round((1 - distance / 2) * 100)
            else:
                status = "missing"
                confidence = 0

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


def retailor_chunks(chunks: list[dict], jd_text: str) -> list[dict]:
    if not chunks:
        return []

    bullets = "\n".join(f"{i+1}. {c['text']}" for i, c in enumerate(chunks))

    prompt = f"""
        You are a professional resume writer. Rewrite each of these experience bullets to better match the job description language and keywords.

        Rules:
        - Keep the same meaning and facts — do NOT invent experience
        - Match the terminology and phrasing used in the job description
        - Use strong action verbs
        - Keep each bullet concise (one line)
        - Return ONLY a numbered list in the same order, no extra commentary

        Experience bullets:
        {bullets}

        Job Description:
        {jd_text}
    """
    raw = _call_gemini(prompt)

    retailored = []
    for i, line in enumerate(raw.strip().split("\n")):
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit():
            line = line.split(".", 1)[-1].strip()
            line = line.split(")", 1)[-1].strip()
        if i < len(chunks):
            retailored.append({
                "text": line,
                "category": chunks[i]["category"],
                "distance": chunks[i]["distance"],
            })

    return retailored


def generate_summary(jd_text: str, chunks: list[dict], profile: Profile, skills_data: dict) -> str:
    chunk_text = "\n".join(f"- {c['text']}" for c in chunks)
    skills_text = _format_skills_for_prompt(skills_data)
    prompt = f"""
        Write a 3-4 sentence professional resume summary for {profile.name} tailored to this job.
        Tone should match the job — startup = energetic, corporate = polished.
        Do NOT use the phrase "results-driven". Return only the summary text, no labels or headings.

        Candidate's skills:
        {skills_text}

        Relevant experience:
        {chunk_text}

        Job Description:
        {jd_text}
    """
    return _call_gemini(prompt)


def generate_projects(jd_text: str, chunks: list[dict], profile: Profile, skills_data: dict) -> str:
    if not chunks:
        return ""
    chunk_text = "\n".join(f"- {c['text']}" for c in chunks)
    skills_text = _format_skills_for_prompt(skills_data)
    prompt = f"""
        You are a professional resume writer. Create a Projects section for {profile.name}'s resume.

        Rules:
        - Group bullets under project name headings
        - Each heading must have a MINIMUM of 2 bullets and MAXIMUM of 4 bullets
        - If a project only has 1 relevant bullet, combine it with the most related project
        - If a project has more than 4 relevant bullets, keep only the 4 most relevant
        - Use strong action verbs and match the job description language
        - Where relevant, reference the candidate's skills naturally in the bullets
        - Return ONLY the project headings and bullets, no extra commentary

        Format:
        Project Name
        - Bullet point
        - Bullet point

        Candidate's skills:
        {skills_text}

        Relevant project experience:
        {chunk_text}

        Job Description:
        {jd_text}
    """
    return _call_gemini(prompt)


def generate_experience(jd_text: str, chunks: list[dict], profile: Profile, skills_data: dict) -> str:
    if not chunks:
        return ""
    chunk_text = "\n".join(f"- {c['text']}" for c in chunks)
    skills_text = _format_skills_for_prompt(skills_data)
    prompt = f"""
        You are a professional resume writer. Create a Work Experience section for {profile.name}'s resume.

        Rules:
        - Group bullets under job title / company headings
        - Each heading must have a MINIMUM of 2 bullets and MAXIMUM of 4 bullets
        - Use strong action verbs and match the job description language
        - Where relevant, reference the candidate's skills naturally in the bullets
        - Return ONLY the headings and bullets, no extra commentary

        Format:
        Job Title — Company Name
        - Bullet point
        - Bullet point

        Candidate's skills:
        {skills_text}

        Relevant work experience:
        {chunk_text}

        Job Description:
        {jd_text}
    """
    return _call_gemini(prompt)


def generate_cover_letter(jd_text: str, chunks: list[dict], profile: Profile, skills_data: dict) -> str:
    chunk_text = "\n".join(f"- {c['text']}" for c in chunks)
    skills_text = _format_skills_for_prompt(skills_data)
    edu = profile.education[0] if profile.education else None
    edu_line = f"{edu.degree} from {edu.institution}" if edu else ""

    prompt = f"""
        Write a professional cover letter for {profile.name} applying to this job.
        Contact: {profile.email} | {profile.location or ""}
        Education: {edu_line}

        Candidate's skills:
        {skills_text}

        Relevant experience:
        {chunk_text}

        Job Description:
        {jd_text}

        Keep it to 3 paragraphs. Do not include a date or address header. Return only the cover letter text.
    """
    return _call_gemini(prompt)


def run_analysis(jd_text: str, profile: Profile) -> dict:
    skills_data = load_skills()

    # Step 1 — extract skills from JD
    skills = extract_skills(jd_text)

    # Step 2 — gap analysis (checks skills.json first, then ChromaDB)
    gap_analysis = analyze_gaps(skills, skills_data)

    # Step 3 — retrieve relevant experience chunks
    all_skill_names = (
        skills.get("required", []) +
        skills.get("nice_to_have", []) +
        skills.get("soft", [])
    )

    def retrieve_relevant(category: str) -> list[dict]:
        chunks = []
        seen = set()
        for skill in all_skill_names:
            for chunk in query_chunks(skill, n_results=3):
                if chunk["text"] not in seen and chunk["category"] == category:
                    seen.add(chunk["text"])
                    chunks.append(chunk)
        return chunks

    project_chunks = retrieve_relevant("project")
    job_chunks = retrieve_relevant("job")
    softskill_chunks = retrieve_relevant("softskill")

    # Step 4 — retailor bullets to match JD language
    project_chunks = retailor_chunks(project_chunks, jd_text)
    job_chunks = retailor_chunks(job_chunks, jd_text)

    # Step 5 — generate all sections with skills context
    all_chunks = project_chunks + job_chunks + softskill_chunks
    summary = generate_summary(jd_text, all_chunks, profile, skills_data)
    projects = generate_projects(jd_text, project_chunks, profile, skills_data)
    experience = generate_experience(jd_text, job_chunks, profile, skills_data)
    cover_letter = generate_cover_letter(jd_text, all_chunks, profile, skills_data)

    return {
        "skills": skills,
        "gap_analysis": gap_analysis,
        "chunks_used": all_chunks,
        "summary": summary,
        "projects": projects,
        "experience": experience,
        "cover_letter": cover_letter,
    }

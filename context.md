# Job Application Copilot — Project Context

## What This Project Is
A desktop application (.exe) that uses RAG (Retrieval Augmented Generation) and a local vector database to help users tailor resumes and cover letters to specific job descriptions. Stores experience as project-level documents, retrieves the most relevant ones using hybrid semantic + keyword scoring, and generates tailored Word documents via Gemini.

---

## Current Status — FEATURE COMPLETE

All core backend, UI screens, packaging, and architecture refactors are done. The app is fully functional as a Windows .exe.

---

## Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.12 | WSL for dev, Windows for build |
| UI | PyQt6 | Light theme via QSS |
| Vector DB | ChromaDB (persistent) | Project-level documents, not bullet chunks |
| Embeddings | gemini-embedding-001 | 3072 dims, with in-memory cache |
| LLM | gemini-2.5-flash | 6 calls per analysis |
| Word Output | python-docx | Editable .docx resume + cover letter |
| Skills Registry | skills.json | Static, categorized, always shown in resume |
| Profile Storage | profile.json | Name, contact, education |
| Packaging | PyInstaller | Folder build via --collect-all flags |
| Env vars | python-dotenv | GEMINI_API_KEY |

### ⚠️ Critical SDK Notes
```python
# CORRECT — new SDK
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# CORRECT model names
LLM:        gemini-2.5-flash
Embeddings: gemini-embedding-001  (3072 dimensions)

# OLD — deprecated, do not use
import google.generativeai
text-embedding-004
gemini-1.5-flash
```

---

## Environment Setup

```bash
# WSL
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### requirements.txt
```
PyQt6>=6.6.0
chromadb>=0.5.0
google-genai>=1.0.0
python-docx>=1.1.0
python-dotenv>=1.0.0
requests>=2.31.0
```

### .env
```
GEMINI_API_KEY=your_key_here
```

### Reset data (testing)
```bash
rm -f data/profile.json data/skills.json
rm -rf data/chromadb/*
```

---

## File Structure

```
job-copilot/
├── core/
│   ├── __init__.py
│   ├── profile.py        ← ✅ Profile + Education dataclasses
│   ├── embeddings.py     ← ✅ Gemini embedding wrapper + cache
│   ├── database.py       ← ✅ ChromaDB project-level store + hybrid retrieval
│   ├── generator.py      ← ✅ RAG pipeline, gap analysis, all generation
│   ├── docx_builder.py   ← ✅ Word document assembly
│   └── skills.py         ← ✅ skills.json read/write
├── ui/
│   ├── __init__.py
│   ├── styles.py         ← ✅ Global QSS stylesheet
│   ├── main_window.py    ← ✅ Sidebar nav, QStackedWidget
│   ├── setup_screen.py   ← ✅ First run profile + education
│   ├── add_experience.py ← ✅ Project/job structured form
│   ├── analyze_job.py    ← ✅ Gap analysis + generate docs
│   ├── skills_screen.py  ← ✅ Skills registry manager
│   └── settings.py       ← ✅ Edit profile
├── data/
│   ├── chromadb/         ← gitignored, auto created
│   ├── profile.json      ← gitignored, auto created
│   └── skills.json       ← gitignored, auto created
├── output/resumes/       ← gitignored, generated .docx files
├── main.py               ← ✅ Entry point, first run detection
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Architecture — Project-Level RAG

### Key Design Decision
Switched from bullet-level chunks to project-level documents. This was the most important architectural change.

**Old (broken):**
```
chunk_001: "Built React frontend — YYC Track"
chunk_002: "Led team of 5 — YYC Track"
chunk_003: "Configured Docker — YYC Track"
→ 8 skills × 8 embedding calls = rate limits, duplicate retrieval, prompt bloat
```

**New (correct):**
```
document_001: "YYC Track | React, Node.js, MongoDB, Docker | Built MERN app... Led team... Configured Docker..."
→ 1 embedding call per analysis, no duplicates, clean prompts
```

### Data Model

**ChromaDB document per project/job:**
```
Text (embedded):
"YYC Track | React, Node.js, MongoDB, Docker | Built MERN app..."

Metadata:
{
  "type": "project",          # project | job | softskill
  "name": "YYC Track",
  "stack": "React, Node.js, MongoDB, Docker",
  "role": "Team Member",
  "description": "Capstone Web Application (Live)",
  "bullets": "[...json encoded list...]"
}
```

### Hybrid Retrieval Scoring
```python
score = 0.7 * semantic_similarity + 0.3 * keyword_overlap
```
Keyword overlap handles tech names (GitHub Actions, Jest, Azure AI) that pure semantics misses.

### Collection Name
`experience_v2` — if you ever clear ChromaDB, this is the collection that gets recreated.

---

## How The App Works (Full Flow)

```
First Run:
1. main.py checks profile_exists() → False → SetupScreen
2. User fills profile + education → profile.json saved
3. on_complete() → MainWindow shown

Adding Experience:
4. User fills structured form (name, stack, role, description, bullets)
5. All bullets stored as ONE ChromaDB document per project/job
6. One embedding call per entry saved

Every Job Application:
7. User pastes JD → clicks Analyse
8. AnalysisWorker (QThread) runs run_analysis():
   a. Gemini extracts skills + role_summary from JD       [call 1]
   b. Gap analysis vs skills.json (string match, no API)
   c. Build single query: role_summary + all keywords
   d. ONE embedding call → ChromaDB hybrid search         [1 embed]
   e. Top 3 projects + top 2 jobs selected
   f. Gemini generates summary                            [call 2]
   g. Gemini generates Projects section                   [call 3]
   h. Gemini generates Experience section                 [call 4]
   i. Gemini generates cover letter                       [call 5]
9. Results rendered in UI
10. User clicks Generate → resume.docx + cover_letter.docx
11. Output folder opens automatically

Total per analysis: 5 Gemini calls + 1 embedding call
```

---

## Completed Modules

### ✅ core/profile.py
```python
@dataclass class Education: degree, institution, graduation_year, gpa(optional)
@dataclass class Profile: name*, email*, phone, linkedin, github, location, education[]

Profile.save()          # serializes to data/profile.json
Profile.load()          # deserializes, raises FileNotFoundError / ValueError
profile_exists() -> bool
```

### ✅ core/embeddings.py
```python
embed(text: str) -> list[float]   # gemini-embedding-001, 3072 dims
clear_cache()                      # clears in-memory cache

# Module-level cache: _cache dict[str, list[float]]
# Module-level callback: _status_callback (set by AnalysisWorker for UI updates)
# Retries on 429/503 with 30s * attempt backoff, max 5 attempts
```

### ✅ core/database.py
```python
# Collection: "experience_v2"
# Valid types: "project", "job", "softskill"

add_entry(entry_type, name, bullets, stack, role, description) -> None
query_entries(query_text, n_results=10) -> list[dict]
hybrid_score(entry, keywords) -> float   # 0.7 semantic + 0.3 keyword
get_top_entries(query_text, keywords, top_projects=3, top_jobs=2) -> dict
get_all_entries() -> list[dict]
entry_count() -> int
clear_all() -> None

# Entry dict format:
{
    "type": "project",
    "name": "YYC Track",
    "stack": "React, Node.js...",
    "role": "Team Member",
    "description": "Capstone (Live)",
    "bullets": ["Built MERN app...", "Integrated Azure AI..."],
    "distance": 0.312,
    "score": 0.847,   # hybrid score, only in query results
}
```

### ✅ core/generator.py
```python
extract_skills(jd_text) -> dict         # {role_summary, required, nice_to_have, soft}
analyze_gaps(skills, skills_data) -> dict  # checks skills.json only, no API calls
generate_summary(jd_text, entries, profile, skills_data) -> str
generate_projects(jd_text, projects, profile, skills_data) -> str
generate_experience(jd_text, jobs, profile, skills_data) -> str
generate_cover_letter(jd_text, entries, profile, skills_data) -> str
run_analysis(jd_text, profile) -> dict

# run_analysis() return format:
{
    "skills": {"role_summary": "...", "required": [...], "nice_to_have": [...], "soft": [...]},
    "gap_analysis": {
        "overall_match": 73,
        "skills": [{"skill": "React", "type": "required", "status": "strong", "confidence": 95}],
        "missing_skills": ["Kubernetes"]
    },
    "entries_used": {"projects": [...], "jobs": [...], "softskills": [...]},
    "summary": "...",
    "projects": "YYC Track\n- Bullet...",
    "experience": "Cashier — Superstore\n- Bullet...",
    "cover_letter": "Dear Hiring Manager..."
}
```

### ✅ core/skills.py
```python
SKILLS_PATH = "./data/skills.json"

load_skills() -> dict           # {"Languages": ["Python", "JS"], "Frameworks": [...]}
save_skills(data: dict) -> None
add_category(category: str) -> None
remove_category(category: str) -> None
add_skill(category: str, skill: str) -> None
remove_skill(category: str, skill: str) -> None
```

### ✅ core/docx_builder.py
```python
build_resume(profile, summary, projects, experience, filename) -> str
build_cover_letter(profile, cover_letter_text, filename) -> str

# Resume section order:
# 1. Name + contact (centered)
# 2. Summary
# 3. Experience (jobs) — skipped if empty
# 4. Projects — skipped if empty
# 5. Skills (from skills.json) — skipped if empty
# 6. Education (always shown)

# Key rules:
# - US Letter (8.5x11), 0.75in margins for resume, 1in for cover letter
# - Section headings: blue horizontal rule + uppercase label
# - Never unicode bullets — use List Bullet style
# - US Letter must be set explicitly (python-docx defaults to A4)
```

---

## UI Modules

### ✅ ui/styles.py
Global QSS stylesheet. Apply once: `app.setStyleSheet(STYLESHEET)`

**Design tokens:**
```
Background:  #F8F9FA   Surface:  #FFFFFF
Primary:     #4361EE   Text:     #1A1A2E
Muted:       #6C757D   Border:   #DEE2E6
Danger:      #E63946   Success:  #2E7D32
Warning:     #F57F17
```

**Named object styles (setObjectName):**
- `title` — 24px bold
- `subtitle` — 13px muted
- `section_label` — 11px bold uppercase muted
- `card` — white card with border + 12px radius
- `secondary` — outlined blue button
- `danger` — outlined red button, auto-sized (no fixed height)
- `nav_btn` — sidebar nav, checkable, supports :checked state

**Critical:** Never set fixed heights on buttons — use `min-height` in stylesheet only. Fixed heights cause text clipping on Windows.

### ✅ ui/main_window.py
Sidebar (220px) + QStackedWidget. 4 nav buttons: Add Experience, Analyze Job, Skills, Settings. All checkable, `_switch(index)` updates stack + button states.

### ✅ ui/setup_screen.py
First run only. Dynamic education entries (EducationEntry widget). Min 1 education required. Calls `on_complete()` after save.

### ✅ ui/add_experience.py
Structured form with type dropdown (Project / Work Experience / Job / Soft Skill). Fields swap based on type:
- Project: Name, Stack, Role, Description, Bullets
- Job: Name, Stack (optional), Job Title, Company, Bullets
- Softskill: Name, Bullets only

Right panel shows all stored entries as EntryCard widgets with badge + bullets.

### ✅ ui/analyze_job.py
Left: JD text input + Analyse button.
Right: renders after analysis — overall score card, skill breakdown rows (SkillRow with progress bar), missing skills as red pills, Generate button.

`AnalysisWorker(QThread)` runs `run_analysis()` in background. Emits:
- `finished(dict)` — triggers `_render_results()`
- `error(str)` — shows QMessageBox
- `status(str)` — updates status label (rate limit countdown)

Sets `core.embeddings._status_callback` before running so rate limit messages pipe to UI.

### ✅ ui/skills_screen.py
Top bar with category input + Add Category button. Scrollable CategoryCard list. Each card: header with Remove Category button, SkillPill list, inline Add skill input. All buttons auto-sized, no fixed heights.

### ✅ ui/settings.py
Mirrors setup_screen. Pre-fills all fields from `Profile.load()`. Dynamic education entries. Saves on "Save Changes".

---

## Key Gotchas

1. **ChromaDB `n_results` must be `int(min(...))`** — strict int required
2. **Button fixed heights cause text clipping on Windows** — use min-height in QSS only
3. **Emoji in nav buttons don't render on Windows** — use plain text
4. **`google-genai` not `google-generativeai`** — old package dead
5. **ChromaDB collection is `experience_v2`** — v1 (bullet chunks) is incompatible
6. **skills.json gap analysis is string match only** — no embedding call
7. **`_status_callback` must be reset to None after worker finishes** — prevents stale references
8. **US Letter must be set explicitly** — python-docx defaults to A4
9. **Never unicode bullets in docx** — use `List Bullet` style
10. **PyInstaller needs `--collect-all chromadb --collect-all google.genai`** — dynamic imports

---

## Building .exe (Windows)

```cmd
# In Windows Command Prompt with venv active
python -m PyInstaller --windowed --name JobCopilot --collect-all chromadb --collect-all google.genai main.py
```

Or with spec file (after first build, reuse `JobCopilot.spec`):
```cmd
python -m PyInstaller JobCopilot.spec
```

Output: `dist/JobCopilot/JobCopilot.exe` — share the entire `dist/JobCopilot/` folder.

---

## Recommended Chunk Strategy

**Per project: 6-8 focused bullets maximum.**
Each bullet should cover one distinct responsibility. If two bullets mention the same technology, merge them.

**Good format for Add Experience:**
```
Type:        Project
Name:        YYC Track
Stack:       React, Node.js, Express.js, MongoDB, Azure AI, Docker, GitHub Actions
Role:        Team Member
Description: Capstone Web Application (Live)
Bullets:
- Built full-stack MERN app for City of Calgary transit reviews with OpenStreetMap integration
- Integrated Azure AI Sentiment Analysis + Content Safety for review scoring and moderation
- Designed MongoDB schemas with aggregation pipelines for CEI computation and leaderboards
- Architected RESTful Node.js/Express API for review submissions and data retrieval
- Configured Docker + GitHub Actions CI/CD for automated testing and deployment
- Wrote Jest unit tests to validate API routes and data transformation logic
```

---

## Status

### ✅ Complete
- Full core backend (profile, embeddings, database, generator, docx builder, skills)
- Full UI (setup, add experience, analyze job, skills, settings, main window)
- Global stylesheet — light theme, no fixed-height buttons
- Project-level RAG architecture (not bullet chunks)
- Hybrid retrieval (70% semantic + 30% keyword)
- Embedding cache (zero duplicate API calls)
- Rate limit retry (429 + 503, exponential backoff, UI status updates)
- Gap analysis using skills.json (no embedding calls)
- Windows .exe build working
- README.md
- .gitignore

### ⏳ Future (Phase 2)
- [ ] Job application tracker (Applied / Interviewed / Offered / Rejected)
- [ ] Analytics dashboard
- [ ] Web app (React + FastAPI + PostgreSQL)
- [ ] Multi-user auth (Clerk or Supabase)
- [ ] GitHub Actions cross-platform builds (Windows .exe + Mac .app)
- [ ] Ollama hybrid (local embeddings + Gemini LLM) to eliminate rate limits entirely
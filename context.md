# Job Application Copilot — Project Context

## What This Project Is
A desktop application (.exe) that uses RAG (Retrieval Augmented Generation) and a vector database to help users tailor resumes and cover letters to specific job descriptions. It analyzes the user's stored experience against a job description, generates a match score, identifies skill gaps with confidence percentages, and outputs a tailored resume and cover letter as editable Word documents (.docx).

The long term vision is a Phase 2 web app with full job application tracking (applied, interviewed, rejected, offered) and analytics.

---

## Who This Is For
- The developer (Windows, WSL for development)
- Eventually: multiplatform (Mac support in Phase 2)

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.12 | Primary language (venv active) |
| UI | PyQt6 | Professional desktop UI, packages well |
| Vector DB | ChromaDB (persistent) | Free, local, no setup |
| Embeddings | gemini-embedding-001 | Replaced text-embedding-004 (deprecated Jan 2026) |
| LLM | gemini-2.5-flash | Replaced gemini-1.5-flash (not available on new SDK) |
| Word Output | python-docx | Editable .docx — user can tweak before sending |
| Static Storage | profile.json | Name, contact, education |
| Packaging | PyInstaller | Produces .exe |
| Env vars | python-dotenv | API key management |

### ⚠️ SDK Change — Critical
The old `google-generativeai` package is fully deprecated. Use the new `google-genai` package:
```python
# WRONG — old, deprecated
import google.generativeai as genai

# CORRECT — new SDK
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
```

### ⚠️ Model Names — Critical
Both the embedding model and LLM changed with the new SDK:

| Purpose | Old (broken) | New (correct) |
|---|---|---|
| Embeddings | text-embedding-004 | gemini-embedding-001 |
| LLM | gemini-1.5-flash | gemini-2.5-flash |

- `gemini-embedding-001` produces **3072-dimensional** vectors (up from 768)
- ChromaDB handles the new dimensions automatically

### ⚠️ Output Format
Originally planned as PDF (fpdf2). Changed to **Word (.docx)** via `python-docx` so users can edit before sending.

### Future LLM Swap Path
```
Now:       gemini-2.5-flash  (free)
Later:     Gemini Pro        (paid, same API — minimal code change)
Rich mode: Claude API        (swap ~5 lines in generator.py only)
Offline:   Ollama llama3     (fully local, no API costs)
```

---

## Environment Setup

```bash
# WSL — from project root
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### requirements.txt
```
PyQt6>=6.6.0
chromadb>=0.5.0
google-genai>=1.0.0
python-docx>=1.1.0
python-dotenv>=1.0.0
```

Note: `fpdf2` removed — replaced by `python-docx`.

### .env (never commit)
```
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## File Structure

```
job-copilot/
│
├── core/
│   ├── __init__.py
│   ├── profile.py        ← ✅ DONE — Profile + Education dataclasses, load/save/exists
│   ├── embeddings.py     ← ✅ DONE — Gemini embedding wrapper (gemini-embedding-001)
│   ├── database.py       ← ✅ DONE — ChromaDB add/query logic (4 categories)
│   ├── generator.py      ← ✅ DONE — RAG pipeline, skill extraction, gap analysis, all sections
│   └── docx_builder.py   ← ✅ DONE — python-docx Word document assembly
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py    ← ⏳ TODO — main PyQt6 window
│   ├── setup_screen.py   ← ⏳ NEXT — first time profile + education setup
│   ├── add_experience.py ← ⏳ TODO — form to add chunks (projects, skills, soft skills, jobs)
│   ├── analyze_job.py    ← ⏳ TODO — JD input + results display
│   └── settings.py       ← ⏳ TODO — edit profile anytime
│
├── data/
│   ├── chromadb/         ← persistent vector DB (auto created by ChromaDB)
│   └── profile.json      ← static user data (auto created on first run)
│
├── output/
│   └── resumes/          ← generated .docx files saved here
│
├── .env                  ← GEMINI_API_KEY (never commit)
├── .env.example          ← template showing required keys
├── .gitignore            ← venv/, .env, data/chromadb/, output/resumes/, __pycache__/
├── main.py               ← ⏳ TODO — app entry point
├── requirements.txt      ← all dependencies
└── context.md            ← this file
```

---

## Completed Modules

### ✅ core/profile.py
Uses Python dataclasses. Two classes: `Profile` and `Education`.

**Key design decisions:**
- Required fields: `name`, `email`. Everything else is `Optional`
- `Education.gpa` is optional
- Supports multiple degrees via `education: list[Education]`
- `save()` is a method on `Profile` — serializes via `asdict()` to JSON
- `load()` is a `@staticmethod` — deserializes and reconstructs dataclasses
- `profile_exists()` is a standalone module-level function (needed before any object exists)

**Error handling:**
- `FileNotFoundError` if profile.json doesn't exist
- `ValueError` if JSON is malformed
- `ValueError` if `name` or `email` are missing

**Usage:**
```python
from core.profile import Profile, Education, profile_exists

if not profile_exists():
    show_setup_screen()

p = Profile(
    name="Jane",
    email="jane@email.com",
    education=[Education(degree="BSc CS", institution="U of C", graduation_year="2025", gpa="3.8")]
)
p.save()

p = Profile.load()
```

---

### ✅ core/embeddings.py
Single function `embed(text)` — converts a string to a vector of floats.

**Key design decisions:**
- Gemini client initialized once at module level (`_client`) — not per call
- Model: `gemini-embedding-001` (3072 dimensions)
- Raises `ValueError` on empty/whitespace input

**Usage:**
```python
from core.embeddings import embed
vector = embed("Led a team of 5 developers")
# returns list of 3072 floats
```

---

### ✅ core/database.py
ChromaDB wrapper. Stores and queries experience chunks.

**Valid categories (4 total):**
- `project` — individual bullets from personal/academic projects
- `job` — bullets from part-time or full-time work experience
- `skill` — technical skills with context
- `softskill` — soft skills with context

**Key design decisions:**
- `PersistentClient` at `./data/chromadb` — survives restarts
- Single collection named `"experience"` — all chunks in one place
- `query_chunks()` caps `n_results` with `int(min(n_results, count))` — ChromaDB requires strict int
- `query_chunks_by_category()` filters by category using ChromaDB `where` clause
- `get_chunks_by_category()` retrieves all stored chunks of a given category (used for Skills section)

**Functions:**
```python
add_chunk(text: str, category: str) -> None
query_chunks(skill_text: str, n_results: int = 5) -> list[dict]
query_chunks_by_category(skill_text: str, category: str, n_results: int = 5) -> list[dict]
get_all_chunks() -> list[dict]
get_chunks_by_category(category: str) -> list[dict]
chunk_count() -> int
```

**Return format:**
```python
[{"text": "Led a team of 5...", "category": "project", "distance": 0.312}]
```

---

### ✅ core/generator.py
The brain of the app. Orchestrates all Gemini calls and ChromaDB queries.

**5 Gemini calls per job application:**
1. `extract_skills(jd_text)` — parses JD into structured skill categories
2. `retailor_chunks(chunks, jd_text)` — rewrites retrieved bullets to match JD language
3. `generate_summary(jd_text, chunks, profile)` — 3-4 sentence tailored summary
4. `generate_projects(jd_text, chunks, profile)` — projects section (2-4 bullets per heading)
5. `generate_experience(jd_text, chunks, profile)` — work experience section (2-4 bullets per heading)
6. `generate_skills(skill_chunks)` — grouped skills section
7. `generate_cover_letter(jd_text, chunks, profile)` — 3 paragraph cover letter

Note: `analyze_gaps()` makes NO Gemini calls — pure ChromaDB distance math.

**Key design decisions:**
- `retailor_chunks()` rewrites bullets to match JD language WITHOUT inventing experience
- Projects and jobs are retrieved and generated separately — distinct sections in the doc
- Skills section pulls ALL skill chunks (not just relevant ones) via `get_chunks_by_category()`
- Softskill chunks feed into summary and cover letter, not a dedicated section
- `run_analysis()` is the single entry point the UI calls — returns everything in one dict
- Chunks deduplicated across skill queries using a `seen` set

**Distance thresholds:**
```
distance < 0.40   → ✅ Strong match
distance 0.40–0.70 → ⚠️ Partial match
distance > 0.70   → ❌ Missing (confidence = 0%)
```

**run_analysis() return format:**
```python
{
    "skills": {"required": [...], "nice_to_have": [...], "soft": [...]},
    "gap_analysis": {
        "overall_match": 73,
        "skills": [
            {"skill": "React", "type": "required", "status": "strong", "confidence": 87, "distance": 0.261},
        ],
        "missing_skills": ["Docker", "Kubernetes"]
    },
    "chunks_used": [{"text": "...", "category": "project", "distance": 0.3}],
    "summary": "Jane is a full stack developer...",
    "projects": "YYC Track\n- Built React frontend...\n- Led team of 5...",
    "experience": "Cashier — Superstore\n- Processed transactions...",
    "skills_section": "Languages: Python, JavaScript\nFrameworks: React, Node.js",
    "cover_letter": "Dear Hiring Manager..."
}
```

---

### ✅ core/docx_builder.py
Assembles Word documents from generator output.

**Resume section order:**
1. Name + contact header (centered)
2. Summary
3. Experience (job chunks) — only rendered if job chunks exist
4. Projects (project chunks) — only rendered if project chunks exist
5. Skills (grouped category: skill, skill, skill format)
6. Education (always shown in full from profile.json)

**Key design decisions:**
- US Letter (8.5x11), 0.75in margins for resume, 1in for cover letter
- Section headings: blue horizontal rule + uppercase label
- `_render_bulleted_section()` parses Gemini output — lines starting with `-` or `•` = bullets, everything else = subsection heading
- `_render_skills_section()` parses `Category: skill1, skill2` lines — category label is bold
- Experience and Projects sections are conditionally rendered — skipped if no chunks exist
- Both functions return the output path as a string

**Functions:**
```python
build_resume(profile, summary, projects, experience, skills_section, filename) -> str
build_cover_letter(profile, cover_letter_text, filename) -> str
```

**Usage:**
```python
from core.docx_builder import build_resume, build_cover_letter

resume_path = build_resume(
    p,
    result["summary"],
    result["projects"],
    result["experience"],
    result["skills_section"],
    "resume.docx"
)
cover_path = build_cover_letter(p, result["cover_letter"], "cover_letter.docx")
```

---

## Data Architecture

### 1. Static Data — profile.json
Always included in every resume. Does NOT live in ChromaDB.

```json
{
  "name": "Your Name",
  "email": "you@email.com",
  "phone": "403-555-0000",
  "linkedin": "linkedin.com/in/yourname",
  "github": "github.com/yourname",
  "location": "Calgary, AB",
  "education": [
    {
      "degree": "BSc Computer Science",
      "institution": "University of Calgary",
      "graduation_year": "2025",
      "gpa": "3.8"
    }
  ]
}
```

### 2. Dynamic Data — ChromaDB (4 categories)

| Category | What goes in | Used for |
|---|---|---|
| `project` | Bullets from personal/academic projects | Projects section |
| `job` | Bullets from part-time/full-time jobs | Experience section |
| `skill` | Technical skills with context | Skills section (all chunks) |
| `softskill` | Soft skills with context | Summary + cover letter |

### 3. Generated On The Fly — Never Stored
Summary, resume content, and cover letter generated fresh every time per job.

---

## How The App Works (Full Flow)

```
First Run:
1. Setup screen collects name, contact info, education → saved to profile.json

Every Job Application:
2. User adds experience chunks via form → embedded + stored in ChromaDB
3. User pastes a job description
4. Gemini extracts required/nice-to-have/soft skills from JD as JSON        [call 1]
5. App queries ChromaDB for each skill → distance score per skill
6. Skills categorized: ✅ Strong / ⚠️ Partial / ❌ Missing
7. Gemini rewrites retrieved chunks to match JD language                     [call 2]
8. Gemini generates personal summary                                         [call 3]
9. Gemini generates Projects section (2-4 bullets per heading)               [call 4]
10. Gemini generates Experience section (2-4 bullets per heading)            [call 5]
11. Gemini generates Skills section (grouped by category)                    [call 6]
12. Gemini generates cover letter                                            [call 7]
13. python-docx assembles resume.docx and cover_letter.docx
14. User opens and edits in Word before sending
```

---

## Skill Gap Analysis

```
Overall Match: 73%

✅ React          87%   strong match
✅ CI/CD          82%   strong match
⚠️  PostgreSQL    55%   you have MongoDB, they want PostgreSQL
❌ Kubernetes      0%   not in your experience
❌ GraphQL         0%   not in your experience
```

---

## Word Document Structure

### resume.docx
```
Name                                    ← profile.json (large, centered)
email | phone | linkedin | github       ← profile.json (small, centered)
─────────────────────────────
SUMMARY
3-4 sentence tailored summary
─────────────────────────────
EXPERIENCE                              ← only shown if job chunks exist
Job Title — Company
  • Retailored bullet (2-4 per heading)
─────────────────────────────
PROJECTS                                ← only shown if project chunks exist
Project Name
  • Retailored bullet (2-4 per heading)
─────────────────────────────
SKILLS
Languages:   Python, JavaScript
Frameworks:  React, Node.js
Tools:       Docker, Git
─────────────────────────────
EDUCATION
BSc Computer Science — University of Calgary
2025 | GPA: 3.8
```

### cover_letter.docx
```
Name (centered)
email | phone | location

Paragraph 1...
Paragraph 2...
Paragraph 3...
```

---

## Key Things To Remember

1. **Use `google-genai`, not `google-generativeai`** — old package is dead.

2. **Model strings:**
   - LLM: `gemini-2.5-flash`
   - Embeddings: `gemini-embedding-001` (3072 dimensions)

3. **ChromaDB `n_results` must be plain `int`:**
   ```python
   capped = int(min(n_results, count))
   ```

4. **4 chunk categories:** `project`, `job`, `skill`, `softskill` — enforced in `database.py`.

5. **Skills section uses ALL skill chunks** — not just relevant ones. `get_chunks_by_category("skill")` not `query_chunks()`.

6. **Experience section will be empty** until `job` chunks are added — this is correct behaviour, section is skipped in the doc.

7. **ChromaDB PersistentClient:**
   ```python
   client = chromadb.PersistentClient(path="./data/chromadb")
   ```

8. **API key always from .env:**
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   api_key = os.getenv("GEMINI_API_KEY")
   ```

9. **Check profile.json on startup:**
   ```python
   from core.profile import profile_exists
   if not profile_exists():
       show_setup_screen()
   ```

10. **Personal summary never stored** — generated fresh per job.

11. **Education in profile.json not ChromaDB** — always shown in full.

12. **Never use unicode bullets in docx** — use `List Bullet` style.

13. **US Letter page size must be set explicitly** — python-docx defaults to A4.

14. **Swapping LLMs** only requires changing `_MODEL` in `generator.py`.

15. **WSL for development**, Windows for final .exe build and testing.

16. **PyInstaller build command:**
    ```bash
    pyinstaller --onefile --windowed --icon=app_icon.ico --name="JobCopilot" main.py
    ```

17. **Gemini free tier:** gemini-2.5-flash 1500 req/day, gemini-embedding-001 generous free limit.

---

## Build Order
1. `core/profile.py`       ← ✅ done
2. `core/embeddings.py`    ← ✅ done
3. `core/database.py`      ← ✅ done
4. `core/generator.py`     ← ✅ done
5. `core/docx_builder.py`  ← ✅ done
6. `ui/setup_screen.py`    ← ⏳ NEXT
7. `ui/add_experience.py`  ← ⏳ todo
8. `ui/analyze_job.py`     ← ⏳ todo
9. `ui/settings.py`        ← ⏳ todo
10. `ui/main_window.py`    ← ⏳ todo
11. `main.py`              ← ⏳ todo
12. PyInstaller packaging  ← ⏳ todo

---

## Status

### ✅ Done
- Project planning and architecture
- Tech stack finalized (with SDK/model corrections)
- venv created, all dependencies installed
- `core/profile.py` ✅
- `core/embeddings.py` ✅
- `core/database.py` ✅ (updated — added `job` category, `query_chunks_by_category`, `get_chunks_by_category`)
- `core/generator.py` ✅ (updated — separate Projects/Experience/Skills sections, retailoring, 2-4 bullet rule)
- `core/docx_builder.py` ✅ (updated — 4 sections: Experience, Projects, Skills, Education; conditional rendering)

### ⏳ To Do

#### Phase 1 — UI
- [ ] `ui/setup_screen.py` — first time setup form (name, contact, education)
- [ ] `ui/add_experience.py` — form to add chunks (project / job / skill / softskill)
- [ ] `ui/analyze_job.py` — JD input, match score, gap analysis display, generate button
- [ ] `ui/settings.py` — edit profile and education anytime
- [ ] `ui/main_window.py` — main app window tying all screens together

#### Phase 1 — Finishing
- [ ] `main.py` — entry point with first run detection
- [ ] End to end pipeline test with real chunks
- [ ] PyInstaller .exe build
- [ ] Test .exe on clean Windows machine

#### Phase 2 — Future
- [ ] Web app scaffold (React + FastAPI)
- [ ] PostgreSQL job application tracker
- [ ] Application status tracking (Applied / Interviewed / Offered / Rejected)
- [ ] Analytics dashboard
- [ ] Multi user auth (Clerk or Supabase)
- [ ] Deploy to Railway or Render
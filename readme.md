<!--
Project overview and setup guide for Job Copilot. This file documents the app
purpose, architecture, installation steps, and packaging workflow for users.
-->

# Job Copilot

A desktop application that uses RAG (Retrieval Augmented Generation) and a local vector database to help you tailor resumes and cover letters to specific job descriptions. Paste a job description, get a match score, see exactly which skills you're missing, and generate a tailored resume and cover letter as editable Word documents.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-green)
![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-orange)
![Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-purple)

---

## What It Does

- **Skill Gap Analysis** — paste any job description and instantly see how well your experience matches, with a confidence score per skill
- **Tailored Resume** — generates a resume that rewrites your experience bullets to match the job's language and keywords
- **Cover Letter** — generates a 3-paragraph cover letter tailored to the specific role
- **Editable Output** — everything exports as `.docx` so you can tweak it in Word before sending
- **Structured Skills Registry** — maintain a categorized skills list (Languages, Frameworks, Tools etc.) that always appears in your resume Skills section
- **Project-level RAG** — stores entire projects as single documents for accurate, efficient retrieval

---

## How It Works

Your experience is stored as project/job documents in a local vector database (ChromaDB). When you paste a job description:

1. Gemini extracts required skills and a role summary from the JD
2. A single semantic query retrieves your most relevant projects and jobs
3. Hybrid scoring (70% semantic + 30% keyword) ranks results accurately
4. Skills are matched against your structured skills registry for gap analysis
5. Gemini rewrites your experience bullets to match the JD language
6. A tailored resume and cover letter are generated and saved as `.docx`

**Total API calls per analysis: 6 Gemini calls, 1 embedding call.**

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| UI | PyQt6 (light theme) |
| Vector DB | ChromaDB (local, persistent) |
| Embeddings | Gemini gemini-embedding-001 |
| LLM | Gemini gemini-2.5-flash |
| Word Output | python-docx |
| Packaging | PyInstaller (.exe) |

---

## Setup

### Prerequisites
- Python 3.12+
- A Gemini API key — get one free at [aistudio.google.com](https://aistudio.google.com)

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/job-copilot.git
cd job-copilot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and paste your Gemini API key
```

### Running

```bash
python main.py
```

On first run you will be prompted to set up your profile (name, contact info, education).

---

## Usage

### 1. Add Your Experience
Go to **Add Experience** and add your projects and jobs. Each entry includes:
- Name, tech stack, role, description
- Multiple bullet points per entry

One entry = one project or job. All bullets are stored together as a single document for accurate retrieval.

### 2. Add Your Skills
Go to **Skills** and create categories (e.g. Languages, Frameworks, Tools) then add your skills. These always appear in the Skills section of your resume and are used for gap analysis scoring.

### 3. Analyze a Job
Go to **Analyze Job**, paste a job description, and click Analyse. You will see:
- Overall match percentage
- Per-skill confidence scores
- Missing skills to address

Click **Generate Resume & Cover Letter** to export your tailored `.docx` files.

### 4. Settings
Edit your profile, contact info, and education anytime from the Settings tab.

---

## Building the .exe (Windows)

```cmd
pip install pyinstaller
python -m PyInstaller --windowed --name JobCopilot --collect-all chromadb --collect-all google.genai main.py
```

The built app will be in `dist/JobCopilot/`. Share the entire folder — run `JobCopilot.exe` from inside it.

---

## Project Structure

```
job-copilot/
├── core/
│   ├── profile.py        # Profile dataclass, load/save
│   ├── embeddings.py     # Gemini embedding wrapper with caching
│   ├── database.py       # ChromaDB project-level store, hybrid retrieval
│   ├── generator.py      # RAG pipeline, gap analysis, generation
│   ├── docx_builder.py   # Word document assembly
│   └── skills.py         # Skills registry load/save
├── ui/
│   ├── styles.py         # Global QSS stylesheet (light theme)
│   ├── main_window.py    # Main window with sidebar navigation
│   ├── setup_screen.py   # First run profile setup
│   ├── add_experience.py # Add projects and jobs
│   ├── analyze_job.py    # Job analysis and document generation
│   ├── skills_screen.py  # Skills registry manager
│   └── settings.py       # Edit profile and education
├── data/
│   ├── chromadb/         # Vector DB — gitignored, auto created
│   ├── profile.json      # Your profile — gitignored, auto created
│   └── skills.json       # Your skills — gitignored, auto created
├── output/
│   └── resumes/          # Generated .docx files — gitignored
├── main.py               # Entry point
├── requirements.txt      # Dependencies
└── .env.example          # API key template
```

---

## Rate Limits

Job Copilot uses the Gemini free tier which allows 1500 requests per day. The app:
- Caches embeddings so the same text is never embedded twice in a session
- Uses hybrid retrieval so only 1 embedding call is needed per analysis
- Automatically retries on 429/503 errors with exponential backoff

If you hit rate limits, wait a minute and try again.

---

## Data Privacy

All your experience data is stored **entirely locally** in `data/`. Nothing is sent anywhere except the Gemini API calls for embedding and generation. Your profile, skills, and experience never leave your machine.

---

## Roadmap

- [ ] Application tracker (Applied / Interviewed / Offered / Rejected)
- [ ] Analytics dashboard (response rate by industry, which skills get interviews)
- [ ] Web app version (React + FastAPI + PostgreSQL)
- [ ] Multi-user support with auth

---

## License

MIT
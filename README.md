# Autonomous AI Job Application & Outreach Agent
live on : http://127.0.0.1:5000/
A production-grade, multi-agent AI job application platform orchestrated with **LangGraph** and **Google Gemini 2.5 Flash**[cite: 1, 3, 9]. The system scrapes live openings across 6 job portals[cite: 1, 5], filters and scores matches against the candidate's profile[cite: 2, 5], dynamically generates **ATS-optimized 1-page PDF resumes** per job, submits portal applications via **Playwright** with persistent login sessions[cite: 2, 6, 9], sends MX-verified **HR cold follow-up emails** with tailored resumes attached[cite: 2, 6, 9], monitors recruiter replies via **IMAP**[cite: 3, 6, 9], and serves a real-time **Flask + Chart.js** monitoring dashboard[cite: 2, 7, 10].



## Key Features

- **Multi-Portal Job Scraping (`[02] scrape`)**: Collects openings from **RemoteOK** (JSON API), **WeWorkRemotely** (HTML/BeautifulSoup), **Internshala**, **LinkedIn**, **Naukri**, and **Wellfound** (Playwright + `playwright-stealth`) with per-scraper exception isolation[cite: 3, 5, 9].
- **Intelligent Filtering & SHA-256 Deduplication (`[03] filter`)**: Generates deterministic `SHA-256[:16]` URL hashes stored in SQLite to prevent duplicate processing, while applying configurable whitelist/blacklist keywords and senior-role exclusions[cite: 3, 5, 11].
- **Batched LLM Semantic Scoring (`[04] score`)**: Evaluates all filtered listings in a single structured JSON prompt using **Gemini 2.5 Flash** (`0–10` relevance scale) with exponential backoff retry for `429` rate limits, selecting top matches scoring $\ge 7.0$[cite: 3, 5, 6, 14].
- **Dynamic ATS Resume Tailoring & Portal Auto-Apply (`[05] apply`)**: Extracts top JD keywords via Gemini 2.5 Flash, generates an ATS-verified 1-page single-column PDF resume (`data/tailored_resumes/`), answers custom screening questions, and submits applications via Playwright using persistent session cookies (`data/browser_profile`)[cite: 3, 6].
- **Waterfall HR Email Discovery & Cold Follow-Up (`[06] email`)**: Discovers company HR/careers addresses via SQLite cache $\rightarrow$ Tavily web search $\rightarrow$ domain pattern generation with `dnspython` MX record verification, then sends personalized cold emails with the job's ATS-tailored PDF resume attached via Gmail SMTP SSL[cite: 2, 3, 6, 9].
- **Sequential HR Drip Campaign (`[07] hr_drip`)**: Sends daily batches of personalized outreach emails to a curated HR contact list without ever repeating contacts[cite: 3, 6, 12].
- **Cross-Session Memory & Daily HTML Summary Report (`[01] load_memory`, `[08] save_memory`, `[09] report`)**: Persists daily KPI metrics in SQLite, classifies incoming recruiter replies (`positive` / `bounce` / `auto-reply`) via Gmail IMAP, and emails a formatted HTML summary report at the end of every run[cite: 3, 6, 7, 8].
- **Real-Time Flask Monitoring Dashboard**: Interactive web UI featuring live KPI cards, 7-day Chart.js trend charts, filterable Jobs Table with direct apply links, CSV export, Outreach Emails log, inline Daily HTML Report viewer, and System Logs[cite: 2, 7].



## System Architecture (9-Node LangGraph Pipeline)


START
  │
  ▼
[01] load_memory   ──► Loads historical job hashes & previous session context from SQLite[cite: 3]
  │
  ▼
[02] scrape        ──► Scrapes RemoteOK, WeWorkRemotely, Internshala, LinkedIn, Naukri, Wellfound[cite: 3, 5]
  │
  ▼
[03] filter        ──► SHA-256 deduplication, whitelist/blacklist & senior-role exclusion[cite: 3, 5]
  │
  ├── (total_new == 0) ───────────────────────────────────────────┐
  ▼ (total_new > 0)                                               │[cite: 3]
[04] score         ──► Batched Gemini 2.5 Flash scoring (0–10) & threshold selection (>= 7.0)[cite: 3, 5, 6]
  │                                                               │
  ▼                                                               │
[05] apply         ──► ATS keyword extraction + tailored PDF generation + Playwright auto-apply[cite: 3, 6]
  │                                                               │
  ▼                                                               │
[06] email         ──► Waterfall HR email discovery (Cache -> Tavily -> MX DNS) + SMTP cold email[cite: 2, 3, 6]
  │                                                               │
  ▼                                                               │
[07] hr_drip       ◄──────────────────────────────────────────────┘
  │                ──► Sequential daily batch outreach from HR contact list[cite: 3, 6]
  ▼
[08] save_memory   ──► Persists daily KPI metrics & session summary to SQLite[cite: 3, 7]
  │
  ▼
[09] report        ──► IMAP inbox reply classifier + HTML summary report via Gmail SMTP SSL[cite: 3, 6, 8]
  │
  ▼
 END

Project Structure

autonomous-job-agent/
├── agent/
│   ├── graph.py                 # LangGraph StateGraph & conditional routing
│   ├── state.py                 # Shared AgentState TypedDict contract[cite: 3, 4]
│   └── nodes/                   # Modular agent nodes (01 through 09)[cite: 3, 14]
├── scrapers/                    # Portal scrapers (RemoteOK, WWR, Internshala, LinkedIn, Naukri, Wellfound)[cite: 5, 14]
├── tools/
│   ├── resume_tailor.py         # Gemini ATS keyword extraction + fpdf2 tailored PDF generator
│   ├── email_finder.py          # Waterfall HR email discovery + dnspython MX validation[cite: 6, 9, 14]
│   ├── email_sender.py          # Gmail SMTP SSL cold email & HTML report sender[cite: 6, 9, 14]
│   └── inbox_monitor.py         # Gmail IMAP recruiter reply classifier[cite: 6, 9, 14]
├── database/
│   └── db_manager.py            # Centralized SQLite schema & CRUD operations[cite: 11, 14]
├── dashboard/
│   ├── app.py                   # Flask routes, REST API endpoints & CSV export[cite: 7, 14]
│   └── templates/index.html     # Real-time UI with Chart.js & live metrics
├── data/
│   ├── user_profile.json        # Candidate skills, education, projects & links[cite: 13]
│   ├── hr_contacts.csv          # Curated HR contact list for drip campaigns[cite: 6, 10]
│   └── resume.pdf               # Base fallback PDF resume
├── .github/workflows/
│   └── daily_agent.yml          # Optional GitHub Actions scheduled workflow
├── config.py                    # Centralized environment & threshold settings[cite: 5, 14]
├── setup_logins.py              # One-time Playwright persistent portal login helper
├── main.py                      # Entry point: CLI parser, APScheduler & Flask server[cite: 7, 14]
├── requirements.txt             # Python dependencies
├── .env.template                # Environment variable template[cite: 14, 15]
└── .gitignore                   # Excludes .env, SQLite DBs, browser cookies, tailored PDFs & logs[cite: 14, 15]

Setup & Installation
1. Clone the Repository & Create a Virtual Environment:
git clone [https://github.com/Thanujchaduvu/autonomous-job-agent.git](https://github.com/Thanujchaduvu/autonomous-job-agent.git)
cd autonomous-job-agent

python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

2. Configure Environment Variables
Copy .env.template to .env and fill in your credentials:
cp .env.template .env

3. One-Time Persistent Portal Login Setup
Authenticate once into Internshala, Naukri, and Wellfound so Playwright stores active session cookies locally in data/browser_profile/:
python setup_logins.py

CLI Usage
# 1. Safe Dry-Run Simulation + Launch Dashboard (no live applications or emails sent)[cite: 7]
python main.py --run-now --dry-run

# 2. Live Pipeline Execution + Launch Dashboard[cite: 7]
python main.py --run-now

# 3. Headless Live Pipeline Run Only (exits after sending daily HTML report)
python main.py --run-now --no-dashboard

# 4. Start Background Scheduler (09:00 IST daily) + Dashboard Only[cite: 7, 10]
python main.py

<img width="1920" height="1080" alt="Screenshot (82)" src="https://github.com/user-attachments/assets/67a735f2-e275-414e-82ea-5bdb76ba8dea" />
<img width="1920" height="1080" alt="Screenshot (83)" src="https://github.com/user-attachments/assets/2db310af-7c7a-4f16-814c-22017cbc57da" />
<img width="1920" height="1080" alt="Screenshot (84)" src="https://github.com/user-attachments/assets/2ddbeeec-7613-4ef0-9bba-3c6310ec5f1c" />
<img width="1920" height="1080" alt="Screenshot (85)" src="https://github.com/user-attachments/assets/71e90677-243a-438b-975f-2590bbf6bff4" />
<img width="1920" height="1080" alt="Screenshot (86)" src="https://github.com/user-attachments/assets/0693a6ce-6e3f-4fec-b816-1d1d3401bc43" />

<img width="1920" height="1080" alt="Screenshot (87)" src="https://github.com/user-attachments/assets/68f16eb0-2500-451f-94ff-70f90b74ac71" />
<img width="1920" height="1080" alt="Screenshot (88)" src="https://github.com/user-attachments/assets/d66016ff-1e06-420f-a8fc-44756c710869" />

<img width="1920" height="1080" alt="Screenshot (81)" src="https://github.com/user-attachments/assets/134e144c-da57-4881-a12f-98ea857a53d3" />

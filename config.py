import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LLM
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_MAX_RPM: int = int(os.getenv("GEMINI_MAX_RPM", 12))
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    MEM0_API_KEY: str = os.getenv("MEM0_API_KEY", "")

    # Email
    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    REPORT_RECIPIENT_EMAIL: str = os.getenv("REPORT_RECIPIENT_EMAIL", "")

    # Search & Filtering
    SEARCH_KEYWORDS: list[str] = [
        k.strip() for k in os.getenv("SEARCH_KEYWORDS", "Python,AI").split(",") if k.strip()
    ]
    SEARCH_LOCATION: list[str] = [
        loc.strip() for loc in os.getenv("SEARCH_LOCATION", "Remote").split(",") if loc.strip()
    ]
    WHITELIST_KEYWORDS: list[str] = [
        k.strip().lower() for k in os.getenv("WHITELIST_KEYWORDS", "").split(",") if k.strip()
    ]
    BLACKLIST_KEYWORDS: list[str] = [
        k.strip().lower() for k in os.getenv("BLACKLIST_KEYWORDS", "").split(",") if k.strip()
    ]
    MAX_EXPERIENCE_YEARS: int = int(os.getenv("MAX_EXPERIENCE_YEARS", 4))

    # Limits & Schedule
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", 7.0))
    MAX_APPLY_PER_DAY: int = int(os.getenv("MAX_APPLY_PER_DAY", 10))
    MAX_EMAILS_PER_DAY: int = int(os.getenv("MAX_EMAILS_PER_DAY", 15))
    DRIP_BATCH_SIZE: int = int(os.getenv("DRIP_BATCH_SIZE", 5))
    SCHEDULE_HOUR: int = int(os.getenv("SCHEDULE_HOUR", 9))
    SCHEDULE_MINUTE: int = int(os.getenv("SCHEDULE_MINUTE", 0))
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")

    # Paths & Server
    DB_PATH: str = os.getenv("DB_PATH", "data/job_agent.db")
    RESUME_PATH: str = os.getenv("RESUME_PATH", "data/resume.pdf")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", 5000))
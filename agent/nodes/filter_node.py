import re
from typing import Any, Dict, List
from agent.state import AgentState
from config import Config
from database.db_manager import DBManager

SENIOR_TITLE_TERMS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff",
    "director", "vp ", "vice president", "cto", "head of", "architect", "manager"
]


def _is_senior_role(title: str, description: str) -> bool:
    title_lower = title.lower()
    if any(term in title_lower for term in SENIOR_TITLE_TERMS):
        return True

    # Detect explicit experience requirements like "5+ years", "6-8 yrs", "7 years of experience"
    exp_matches = re.findall(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years|yrs)\b", description.lower())
    for yrs_str in exp_matches:
        if int(yrs_str) > Config.MAX_EXPERIENCE_YEARS:
            return True
    return False


def filter_node(state: AgentState) -> dict:
    """Node 03: Deduplicate via SHA-256 hash and apply keyword + seniority filters."""
    db = DBManager()
    raw_jobs = state.get("raw_jobs", [])
    surviving_jobs: List[Dict[str, Any]] = []
    seen_batch_hashes = set()

    for job in raw_jobs:
        url = job.get("job_url", "").strip()
        title = job.get("job_title", "").strip()
        desc = job.get("job_description", "")
        if not url or not title:
            continue

        job_hash = DBManager.compute_job_hash(url)
        if job_hash in seen_batch_hashes or db.job_exists(job_hash):
            continue

        combined_text = f"{title.lower()} {desc.lower()}"

        # 1. Blacklist check[cite: 5]
        if Config.BLACKLIST_KEYWORDS and any(bk in combined_text for bk in Config.BLACKLIST_KEYWORDS):
            continue

        # 2. Seniority exclusion[cite: 5]
        if _is_senior_role(title, desc):
            continue

        # 3. Whitelist check (must match at least one target stack keyword)[cite: 5]
        if Config.WHITELIST_KEYWORDS and not any(wk in combined_text for wk in Config.WHITELIST_KEYWORDS):
            continue

        job_record = {**job, "job_hash": job_hash, "status": "new"}
        if db.insert_job(job_record):
            seen_batch_hashes.add(job_hash)
            surviving_jobs.append(job_record)

    print(f"[03] filter: {len(surviving_jobs)} new relevant jobs survived out of {len(raw_jobs)} raw.")
    return {
        "new_jobs": surviving_jobs,
        "total_new": len(surviving_jobs),
    }
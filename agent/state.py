from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict):
    # --- Runtime Controls ---
    dry_run: bool                          # True = simulate actions, no live apply/SMTP
    start_time: float                      # Unix timestamp to compute run_time_seconds
    errors: List[str]                      # Non-fatal errors collected across nodes

    # --- 01. Memory ---
    memory_context: str                    # Context loaded from previous sessions[cite: 4]

    # --- 02. Scrape ---
    raw_jobs: List[Dict[str, Any]]         # All scraped job listings[cite: 4]
    total_scraped: int                     # Count of raw listings fetched[cite: 4]

    # --- 03. Filter ---
    new_jobs: List[Dict[str, Any]]         # Deduplicated & filtered jobs[cite: 4]
    total_new: int                         # Count of surviving new jobs[cite: 4]

    # --- 04. Score ---
    scored_jobs: List[Dict[str, Any]]      # Jobs annotated with LLM score (0.0 - 10.0)[cite: 4]
    jobs_to_apply: List[Dict[str, Any]]    # Top-N jobs above SCORE_THRESHOLD[cite: 4]

    # --- 05. Apply ---
    application_results: List[Dict[str, Any]]  # Per-job outcome (applied | route_email | failed)[cite: 4, 6]
    total_applied: int                     # Count of successful portal auto-applies[cite: 4]
    total_failed: int                      # Count of failed application attempts[cite: 4]

    # --- 06. Email ---
    emails_sent: List[Dict[str, Any]]      # Job-specific cold email records[cite: 4]
    total_emailed: int                     # Count of job-specific cold emails sent[cite: 4]

    # --- 07. HR Drip ---
    drip_emails_sent: int                  # Count for today's CSV drip batch[cite: 4]

    # --- 09. Report ---
    report_html: str                       # Final formatted HTML summary report[cite: 4]
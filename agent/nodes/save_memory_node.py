import time
from agent.state import AgentState
from database.db_manager import DBManager


def save_memory_node(state: AgentState) -> dict:
    """Node 08: Persist daily statistics and session summary to SQLite[cite: 3, 7]."""
    db = DBManager()
    elapsed = round(time.time() - state.get("start_time", time.time()), 2)

    total_scraped = state.get("total_scraped", 0)
    total_new = state.get("total_new", 0)
    total_applied = state.get("total_applied", 0)
    total_emailed = state.get("total_emailed", 0)
    total_failed = state.get("total_failed", 0)
    drip_sent = state.get("drip_emails_sent", 0)

    db.upsert_daily_stats(
        total_scraped=total_scraped,
        total_new=total_new,
        total_applied=total_applied,
        total_emailed=total_emailed + drip_sent,
        total_failed=total_failed,
        run_time_seconds=elapsed,
    )

    mode_tag = "DRY-RUN" if state.get("dry_run", True) else "LIVE"
    summary = (
        f"[{mode_tag}] Scraped={total_scraped}, New={total_new}, Applied={total_applied}, "
        f"JobEmails={total_emailed}, DripEmails={drip_sent}, Failed={total_failed}, Time={elapsed}s"
    )
    db.save_session_summary(summary)
    print(f"[08] save_memory: {summary}")
    return {}
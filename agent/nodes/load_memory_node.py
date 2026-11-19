from agent.state import AgentState
from database.db_manager import DBManager


def load_memory_node(state: AgentState) -> dict:
    """Node 01: Load cross-session memory context and seed drip contacts."""
    db = DBManager()
    db.seed_drip_contacts_from_csv()

    memories = db.get_recent_memories(limit=5)
    metrics = db.get_overall_metrics()

    context_str = (
        f"Historical Totals -> Jobs Tracked: {metrics.get('total_jobs', 0)}, "
        f"Applied: {metrics.get('total_applied', 0)}, "
        f"Emailed: {metrics.get('total_emailed', 0)}\n"
        f"Recent Session Summaries:\n{memories}"
    )
    print(f"[01] load_memory: Loaded context ({metrics.get('total_jobs', 0)} historical jobs).")
    return {"memory_context": context_str}
import time
from langgraph.graph import END, START, StateGraph
from agent.nodes.apply_node import apply_node
from agent.nodes.email_node import email_node
from agent.nodes.filter_node import filter_node
from agent.nodes.hr_drip_node import hr_drip_node
from agent.nodes.load_memory_node import load_memory_node
from agent.nodes.report_node import report_node
from agent.nodes.save_memory_node import save_memory_node
from agent.nodes.score_node import score_node
from agent.nodes.scrape_node import scrape_node
from agent.state import AgentState


def route_after_filter(state: AgentState) -> str:
    """Skip scoring, auto-apply, and job-specific emails if no new jobs exist today[cite: 3]."""
    if state.get("total_new", 0) == 0:
        print(" -> Conditional Route: 0 new jobs found. Jumping directly to hr_drip.")
        return "hr_drip"
    print(f" -> Conditional Route: {state['total_new']} new jobs found. Proceeding to score.")
    return "score"


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("load_memory", load_memory_node)
    workflow.add_node("scrape", scrape_node)
    workflow.add_node("filter", filter_node)
    workflow.add_node("score", score_node)
    workflow.add_node("apply", apply_node)
    workflow.add_node("email", email_node)
    workflow.add_node("hr_drip", hr_drip_node)
    workflow.add_node("save_memory", save_memory_node)
    workflow.add_node("report", report_node)

    workflow.add_edge(START, "load_memory")
    workflow.add_edge("load_memory", "scrape")
    workflow.add_edge("scrape", "filter")

    workflow.add_conditional_edges(
        "filter",
        route_after_filter,
        {
            "score": "score",
            "hr_drip": "hr_drip",
        },
    )

    workflow.add_edge("score", "apply")
    workflow.add_edge("apply", "email")
    workflow.add_edge("email", "hr_drip")
    workflow.add_edge("hr_drip", "save_memory")
    workflow.add_edge("save_memory", "report")
    workflow.add_edge("report", END)

    return workflow.compile()


def get_initial_state(dry_run: bool = True) -> AgentState:
    return {
        "dry_run": dry_run,
        "start_time": time.time(),
        "errors": [],
        "memory_context": "",
        "raw_jobs": [],
        "total_scraped": 0,
        "new_jobs": [],
        "total_new": 0,
        "scored_jobs": [],
        "jobs_to_apply": [],
        "application_results": [],
        "total_applied": 0,
        "total_failed": 0,
        "emails_sent": [],
        "total_emailed": 0,
        "drip_emails_sent": 0,
        "report_html": "",
    }
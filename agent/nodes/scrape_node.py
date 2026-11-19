from typing import Any, Dict, List
from agent.state import AgentState
from scrapers.internshala_scraper import scrape_internshala
from scrapers.linkedin_scraper import scrape_linkedin
from scrapers.naukri_scraper import scrape_naukri
from scrapers.remoteok_scraper import scrape_remoteok
from scrapers.wellfound_scraper import scrape_wellfound
from scrapers.weworkremotely_scraper import scrape_weworkremotely


def scrape_node(state: AgentState) -> dict:
    """Node 02: Execute all configured job scrapers safely."""
    scrapers = [
        ("RemoteOK", scrape_remoteok),
        ("WeWorkRemotely", scrape_weworkremotely),
        ("Internshala", scrape_internshala),
        ("LinkedIn", scrape_linkedin),
        ("Naukri", scrape_naukri),
        ("Wellfound", scrape_wellfound),
    ]

    all_jobs: List[Dict[str, Any]] = []
    errors: List[str] = list(state.get("errors", []))

    for name, fn in scrapers:
        try:
            fetched = fn()
            print(f"[02] scrape -> {name}: {len(fetched)} jobs")
            all_jobs.extend(fetched)
        except Exception as exc:
            err_msg = f"{name} scraper failed: {exc}"
            print(f"[02] scrape -> ERROR: {err_msg}")
            errors.append(err_msg)

    print(f"[02] scrape: Total raw jobs collected = {len(all_jobs)}")
    return {
        "raw_jobs": all_jobs,
        "total_scraped": len(all_jobs),
        "errors": errors,
    }
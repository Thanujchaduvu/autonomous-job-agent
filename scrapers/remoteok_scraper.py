import re
from typing import Any, Dict, List
import requests
from bs4 import BeautifulSoup
from config import Config


def _clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def scrape_remoteok() -> List[Dict[str, Any]]:
    """Fetch recent jobs from RemoteOK public JSON API."""
    url = "https://remoteok.com/api"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousJobAgent/1.0"}
    jobs: List[Dict[str, Any]] = []

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        # Index 0 on RemoteOK API is legal/metadata notice; actual jobs start at index 1
        listings = data[1:] if isinstance(data, list) and len(data) > 1 else []
        keywords = [k.lower() for k in Config.SEARCH_KEYWORDS]

        for item in listings:
            title = str(item.get("position", "")).strip()
            company = str(item.get("company", "")).strip()
            job_url = str(item.get("url", "")).strip()
            if not title or not job_url:
                continue

            if job_url.startswith("/"):
                job_url = f"https://remoteok.com{job_url}"

            tags = " ".join(item.get("tags", [])).lower()
            desc = _clean_html(item.get("description", ""))
            searchable_text = f"{title.lower()} {tags} {desc[:500].lower()}"

            # Light pre-filter using configured search keywords
            if keywords and not any(kw in searchable_text for kw in keywords):
                continue

            jobs.append(
                {
                    "job_url": job_url,
                    "job_title": title,
                    "company": company or "Unknown Company",
                    "location": str(item.get("location") or "Remote").strip(),
                    "portal": "remoteok",
                    "job_description": desc[:3000],
                    "apply_type": "email",  # RemoteOK external links route cleanly to HR outreach
                }
            )
    except Exception as exc:
        print(f"[Scraper:RemoteOK] Error fetching listings: {exc}")

    return jobs[:30]


if __name__ == "__main__":
    results = scrape_remoteok()
    print(f"RemoteOK fetched: {len(results)} jobs")
    if results:
        print("Sample:", results[0]["job_title"], "@", results[0]["company"])
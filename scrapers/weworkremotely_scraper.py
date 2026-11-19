import re
from typing import Any, Dict, List
import requests
from bs4 import BeautifulSoup
from config import Config


def scrape_weworkremotely() -> List[Dict[str, Any]]:
    """Scrape Programming & DevOps/Sysadmin feeds from WeWorkRemotely using BeautifulSoup4."""
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousJobAgent/1.0"}
    jobs: List[Dict[str, Any]] = []
    seen_urls = set()
    keywords = [k.lower() for k in Config.SEARCH_KEYWORDS]

    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, headers=headers, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "xml")

            for item in soup.find_all("item"):
                raw_title = item.title.get_text(strip=True) if item.title else ""
                job_url = item.link.get_text(strip=True) if item.link else ""
                region = item.region.get_text(strip=True) if item.find("region") else "Remote"
                raw_desc = item.description.get_text(" ", strip=True) if item.description else ""

                if not raw_title or not job_url or job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                # WWR titles follow "Company Name: Job Title"
                if ":" in raw_title:
                    company, title = [part.strip() for part in raw_title.split(":", 1)]
                else:
                    company, title = "Unknown Company", raw_title

                clean_desc = re.sub(r"\s+", " ", BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True))
                searchable = f"{title.lower()} {clean_desc[:600].lower()}"

                if keywords and not any(kw in searchable for kw in keywords):
                    continue

                jobs.append(
                    {
                        "job_url": job_url,
                        "job_title": title,
                        "company": company,
                        "location": region or "Remote",
                        "portal": "weworkremotely",
                        "job_description": clean_desc[:3000],
                        "apply_type": "email",
                    }
                )
        except Exception as exc:
            print(f"[Scraper:WeWorkRemotely] Error on {feed_url}: {exc}")

    return jobs[:30]


if __name__ == "__main__":
    results = scrape_weworkremotely()
    print(f"WeWorkRemotely fetched: {len(results)} jobs")
    if results:
        print("Sample:", results[0]["job_title"], "@", results[0]["company"])
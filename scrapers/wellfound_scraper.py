from typing import Any, Dict, List
import requests
from bs4 import BeautifulSoup
from config import Config


def scrape_wellfound() -> List[Dict[str, Any]]:
    """Fetch startup AI/Python roles from Wellfound (with optional Tavily AI Search discovery)."""
    jobs: List[Dict[str, Any]] = []
    seen_urls = set()

    # Strategy 1: Tavily AI Search discovery (F1 Bonus - bypasses Cloudflare cleanly)
    if Config.TAVILY_API_KEY:
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=Config.TAVILY_API_KEY)
            resp = client.search(
                query='site:wellfound.com/jobs ("AI Engineer" OR "Python" OR "Machine Learning")',
                max_results=15,
            )
            for item in resp.get("results", []):
                url = item.get("url", "").split("?")[0].strip()
                raw_title = item.get("title", "").strip()
                content = item.get("content", "").strip()
                if not url or url in seen_urls or "/jobs/" not in url:
                    continue
                seen_urls.add(url)

                # Wellfound page titles often format as "Role at Company | Wellfound"
                clean_title = raw_title.replace("| Wellfound", "").strip()
                if " at " in clean_title:
                    title, company = [p.strip() for p in clean_title.split(" at ", 1)]
                else:
                    title, company = clean_title, "Startup (Wellfound)"

                jobs.append(
                    {
                        "job_url": url,
                        "job_title": title,
                        "company": company,
                        "location": "Remote / Startup",
                        "portal": "wellfound",
                        "job_description": content[:2500],
                        "apply_type": "email",
                    }
                )
        except Exception as exc:
            print(f"[Scraper:Wellfound/Tavily] Error: {exc}")

    # Strategy 2: Direct HTTP fallback if Tavily key isn't set or returned 0
    if not jobs:
        url = "https://wellfound.com/role/r/artificial-intelligence-engineer"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.select("a[href*='/jobs/']")[:20]:
                    href = a_tag.get("href", "")
                    job_url = f"https://wellfound.com{href}" if href.startswith("/") else href
                    title = a_tag.get_text(" ", strip=True)
                    if not title or len(title) < 4 or job_url in seen_urls:
                        continue
                    seen_urls.add(job_url)
                    jobs.append(
                        {
                            "job_url": job_url,
                            "job_title": title,
                            "company": "Wellfound Startup",
                            "location": "Remote",
                            "portal": "wellfound",
                            "job_description": f"{title} listed on Wellfound.",
                            "apply_type": "email",
                        }
                    )
            else:
                print(f"[Scraper:Wellfound] Direct HTTP returned {resp.status_code} (add TAVILY_API_KEY in .env for full bypass).")
        except Exception as exc:
            print(f"[Scraper:Wellfound] Direct request error: {exc}")

    return jobs[:25]


if __name__ == "__main__":
    results = scrape_wellfound()
    print(f"Wellfound fetched: {len(results)} jobs")
    if results:
        print("Sample:", results[0]["job_title"], "@", results[0]["company"])
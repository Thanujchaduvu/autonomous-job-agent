import random
import time
from typing import Any, Dict, List
import requests
from bs4 import BeautifulSoup
from config import Config


def scrape_linkedin() -> List[Dict[str, Any]]:
    """Fetch public entry-level/mid AI & Python job cards from LinkedIn's guest endpoint."""
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    search_queries = ["AI Engineer", "Python Developer", "Machine Learning"]
    location = Config.SEARCH_LOCATION[0] if Config.SEARCH_LOCATION else "India"
    jobs: List[Dict[str, Any]] = []
    seen_urls = set()

    for kw in search_queries:
        try:
            params = {
                "keywords": kw,
                "location": location,
                "f_TPR": "r604800",  # Past 7 days
                "f_E": "1,2",        # 1=Internship, 2=Entry level
                "start": 0,
            }
            resp = requests.get(base_url, params=params, headers=headers, timeout=20)
            if resp.status_code == 429:
                print("[Scraper:LinkedIn] Rate-limited (429); skipping remaining queries.")
                break
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            for card in cards:
                title_el = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")
                loc_el = card.find("span", class_="job-search-card__location")
                link_el = card.find("a", class_="base-card__full-link")

                if not title_el or not link_el:
                    continue

                raw_url = link_el.get("href", "").split("?")[0].strip()
                if not raw_url or raw_url in seen_urls:
                    continue
                seen_urls.add(raw_url)

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown Company"
                job_loc = loc_el.get_text(strip=True) if loc_el else location

                jobs.append(
                    {
                        "job_url": raw_url,
                        "job_title": title,
                        "company": company,
                        "location": job_loc,
                        "portal": "linkedin",
                        "job_description": f"{title} at {company} ({job_loc}) - Sourced via LinkedIn public board.",
                        "apply_type": "email",  # Route to cold email to avoid ToS auto-apply violations[cite: 17]
                    }
                )

            time.sleep(random.uniform(2.0, 4.0))
        except Exception as exc:
            print(f"[Scraper:LinkedIn] Error for query '{kw}': {exc}")

    return jobs[:30]


if __name__ == "__main__":
    results = scrape_linkedin()
    print(f"LinkedIn fetched: {len(results)} jobs")
    if results:
        print("Sample:", results[0]["job_title"], "@", results[0]["company"])
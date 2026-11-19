from typing import Any, Dict, List
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def scrape_internshala() -> List[Dict[str, Any]]:
    """Scrape AI/Python fresher jobs & internships from Internshala via Playwright + Stealth."""
    target_urls = [
        "https://internshala.com/jobs/python-developer,artificial-intelligence-ai,machine-learning-jobs/",
        "https://internshala.com/internships/artificial-intelligence-ai,machine-learning,python-django-internship/",
    ]
    jobs: List[Dict[str, Any]] = []
    seen_urls = set()

    try:
        with Stealth().use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            for url in target_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(2000)

                    cards = page.query_selector_all(".individual_internship")
                    for card in cards[:20]:
                        title_el = card.query_selector(".job-internship-name a, .profile a")
                        company_el = card.query_selector(".company-name, .link_display_like_text")
                        loc_el = card.query_selector(".locations span a, #location_names span a")

                        if not title_el:
                            continue

                        title = title_el.inner_text().strip()
                        href = title_el.get_attribute("href") or ""
                        job_url = f"https://internshala.com{href}" if href.startswith("/") else href
                        company = company_el.inner_text().strip() if company_el else "Unknown Company"
                        location = loc_el.inner_text().strip() if loc_el else "India / Remote"

                        if not job_url or job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)

                        # Extract card snippet as description
                        snippet = " ".join(card.inner_text().split())[:1500]

                        jobs.append(
                            {
                                "job_url": job_url,
                                "job_title": title,
                                "company": company,
                                "location": location,
                                "portal": "internshala",
                                "job_description": snippet,
                                "apply_type": "auto_apply",  # Eligible for Playwright auto-apply
                            }
                        )
                except Exception as inner_exc:
                    print(f"[Scraper:Internshala] Page error on {url}: {inner_exc}")

            browser.close()
    except Exception as exc:
        print(f"[Scraper:Internshala] Browser error: {exc}")

    return jobs[:30]


if __name__ == "__main__":
    results = scrape_internshala()
    print(f"Internshala fetched: {len(results)} jobs")
    if results:
        print("Sample:", results[0]["job_title"], "@", results[0]["company"])
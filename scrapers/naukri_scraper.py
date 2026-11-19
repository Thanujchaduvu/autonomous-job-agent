from typing import Any, Dict, List
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def scrape_naukri() -> List[Dict[str, Any]]:
    """Scrape fresher/junior Python & AI listings from Naukri.com via Playwright + Stealth."""
    target_urls = [
        "https://www.naukri.com/ai-engineer-python-developer-jobs?experience=0",
        "https://www.naukri.com/machine-learning-generative-ai-jobs?experience=1",
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
                ),
                viewport={"width": 1366, "height": 768},
            )
            page = context.new_page()

            for url in target_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)

                    # Naukri job tuple selectors
                    cards = page.query_selector_all(".srp-jobtuple-wrapper, article.jobTuple")
                    for card in cards[:20]:
                        title_el = card.query_selector("a.title")
                        company_el = card.query_selector("a.comp-name, .subTitle a")
                        loc_el = card.query_selector(".locWdth, .location span")
                        desc_el = card.query_selector(".job-desc, .ellipsis.job-description")

                        if not title_el:
                            continue

                        title = title_el.inner_text().strip()
                        job_url = (title_el.get_attribute("href") or "").split("?")[0].strip()
                        if not job_url or job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)

                        company = company_el.inner_text().strip() if company_el else "Unknown Company"
                        location = loc_el.inner_text().strip() if loc_el else "India"
                        desc = desc_el.inner_text().strip() if desc_el else " ".join(card.inner_text().split())

                        jobs.append(
                            {
                                "job_url": job_url,
                                "job_title": title,
                                "company": company,
                                "location": location,
                                "portal": "naukri",
                                "job_description": desc[:2500],
                                "apply_type": "email",
                            }
                        )
                except Exception as inner_exc:
                    print(f"[Scraper:Naukri] Page error on {url}: {inner_exc}")

            browser.close()
    except Exception as exc:
        print(f"[Scraper:Naukri] Browser error: {exc}")

    return jobs[:30]


if __name__ == "__main__":
    results = scrape_naukri()
    print(f"Naukri fetched: {len(results)} jobs")
    if results:
        print("Sample:", results[0]["job_title"], "@", results[0]["company"])
import random
import time
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from config import Config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_guest_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select("li"):
        title_el = card.select_one("h3.base-search-card__title")
        company_el = card.select_one("h4.base-search-card__subtitle")
        loc_el = card.select_one("span.job-search-card__location")
        link_el = card.select_one("a.base-card__full-link")
        if not (title_el and link_el):
            continue
        url = link_el.get("href", "").split("?")[0].strip()
        if not url:
            continue
        jobs.append({
            "title": title_el.get_text(strip=True),
            "company": company_el.get_text(strip=True) if company_el else "Unknown",
            "location": loc_el.get_text(strip=True) if loc_el else "India",
            "url": url,
            "portal": "linkedin",
            "description": "",
        })
    return jobs


def _scrape_authenticated_playwright(queries: list[str], location: str) -> list[dict]:
    jobs = []
    seen = set()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="data/browser_profile",
            headless=True,
            viewport={"width": 1366, "height": 768},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for q in queries[:2]:
            search_url = (
                f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(q)}"
                f"&location={quote_plus(location)}&f_TPR=r604800"
            )
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(3500)
                cards = page.query_selector_all("div.job-card-container, li.jobs-search-results__list-item")
                for card in cards[:15]:
                    link = card.query_selector("a.job-card-list__title--link, a.job-card-container__link")
                    company_el = card.query_selector(".artdeco-entity-lockup__subtitle, .job-card-container__primary-description")
                    loc_el = card.query_selector(".artdeco-entity-lockup__caption, .job-card-container__metadata-wrapper li")
                    if not link:
                        continue
                    href = link.get_attribute("href") or ""
                    full_url = f"https://www.linkedin.com{href.split('?')[0]}" if href.startswith("/") else href.split("?")[0]
                    if not full_url or full_url in seen:
                        continue
                    seen.add(full_url)
                    jobs.append({
                        "title": link.inner_text().strip().split("\n")[0],
                        "company": company_el.inner_text().strip() if company_el else "Unknown",
                        "location": loc_el.inner_text().strip() if loc_el else location,
                        "url": full_url,
                        "portal": "linkedin",
                        "description": "",
                    })
            except Exception as exc:
                print(f"[Scraper:LinkedIn:Playwright] Warning for '{q}': {exc}")
        ctx.close()
    return jobs


def scrape_linkedin() -> list[dict]:
    queries = getattr(Config, "SEARCH_QUERIES", None) or [
        "AI Engineer",
        "Machine Learning Engineer",
        "Full Stack Developer",
    ]
    location = getattr(Config, "TARGET_LOCATION", "India")
    collected = []
    seen_urls = set()
    rate_limited = False

    for q in queries[:3]:
        api_url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={quote_plus(q)}&location={quote_plus(location)}&f_TPR=r604800&start=0"
        )
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                print("[Scraper:LinkedIn] Guest API rate-limited (429); switching to authenticated session.")
                rate_limited = True
                break
            if resp.status_code == 200:
                for item in _parse_guest_cards(resp.text):
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        collected.append(item)
            time.sleep(random.uniform(3.0, 5.5))
        except Exception as exc:
            print(f"[Scraper:LinkedIn] Guest API error: {exc}")
            rate_limited = True
            break

    if not collected or rate_limited:
        pw_jobs = _scrape_authenticated_playwright(queries, location)
        for item in pw_jobs:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                collected.append(item)

    return collected
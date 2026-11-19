import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import dns.resolver
from email_validator import EmailNotValidError, validate_email
from config import Config
from database.db_manager import DBManager


def _clean_company_name(company: str) -> str:
    """Strip Wellfound/portal location suffixes like '• Bengaluru • Remote (Work from Home)'."""
    base = re.split(r"[•|\(\[]|\s+-\s+", company)[0].strip()
    return base


def _candidate_domains(company: str, job_url: str) -> List[str]:
    """Generate probable company domains from job URL or cleaned company name."""
    aggregator_domains = (
        "remoteok.com",
        "weworkremotely.com",
        "internshala.com",
        "linkedin.com",
        "naukri.com",
        "wellfound.com",
    )
    parsed = urlparse(job_url)
    host = parsed.netloc.lower().replace("www.", "")
    if host and not any(agg in host for agg in aggregator_domains):
        return [host]

    clean_name = _clean_company_name(company).lower()
    # If company name already includes a domain (e.g., "vaiu.ai", "Jobaaj.com")
    domain_match = re.search(r"\b([a-z0-9-]+\.(?:com|ai|io|in|co|org|net|tech))\b", clean_name)
    if domain_match:
        return [domain_match.group(1)]

    slug = re.sub(
        r"\b(pvt|ltd|inc|llc|corp|technologies|technology|solutions|private|limited|group|india|global|labs|systems)\b",
        "",
        clean_name,
    )
    slug = re.sub(r"[^a-z0-9]", "", slug)
    if not slug:
        return []

    return [f"{slug}.com", f"{slug}.ai", f"{slug}.io", f"{slug}.in", f"{slug}.co"]


def has_valid_mx(domain: str) -> bool:
    """Verify domain has active MX mail servers using dnspython."""
    if not domain or "." not in domain:
        return False
    try:
        records = dns.resolver.resolve(domain, "MX", lifetime=5.0)
        return len(records) > 0
    except Exception:
        return False


def discover_hr_email(company: str, job_url: str) -> Tuple[Optional[str], str]:
    """
    Waterfall HR email discovery:
    1. SQLite hr_contacts cache
    2. Tavily web search (if API key configured)
    3. Pattern generation + MX record verification across probable domains
    """
    db = DBManager()
    clean_company = _clean_company_name(company)
    domains = _candidate_domains(company, job_url)
    if not domains:
        return None, "no_domain"

    # 1. Cache lookup
    for domain in domains:
        cached = db.get_cached_hr_contact(domain)
        if cached and cached.get("hr_email"):
            return cached["hr_email"], f"cache:{cached.get('source', 'db')}"

    # 2. Optional Tavily search for public recruiter/careers email
    if Config.TAVILY_API_KEY:
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=Config.TAVILY_API_KEY)
            res = client.search(query=f'"{clean_company}" careers OR HR email "@{domains[0]}"', max_results=3)
            blob = " ".join(r.get("content", "") for r in res.get("results", []))
            for domain in domains:
                found = re.findall(rf"[a-zA-Z0-9._%+-]+@{re.escape(domain)}", blob)
                for candidate in found:
                    try:
                        valid = validate_email(candidate, check_deliverability=False).normalized
                        if has_valid_mx(domain):
                            db.save_hr_contact(clean_company, domain, valid, source="tavily", verified=1)
                            return valid, "tavily"
                    except EmailNotValidError:
                        continue
        except Exception:
            pass

    # 3. Pattern generation + MX validation across candidate domains
    for domain in domains:
        if has_valid_mx(domain):
            for prefix in ("careers", "hr", "jobs", "talent", "hiring"):
                candidate = f"{prefix}@{domain}"
                try:
                    valid = validate_email(candidate, check_deliverability=False).normalized
                    db.save_hr_contact(clean_company, domain, valid, source="pattern", verified=1)
                    return valid, "pattern"
                except EmailNotValidError:
                    continue

    return None, "mx_failed"
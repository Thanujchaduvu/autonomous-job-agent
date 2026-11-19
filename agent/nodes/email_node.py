import json
import os
import random
import re
import time
from typing import Any, Dict, List
from google import genai
from agent.state import AgentState
from config import Config
from database.db_manager import DBManager
from tools.email_finder import discover_hr_email
from tools.email_sender import send_cold_email_smtp


def _load_profile() -> Dict[str, Any]:
    try:
        with open("data/user_profile.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"name": "Thanuj Chaduvu", "skills": ["Python", "AI", "LangGraph"]}


def _generate_emails_batch(jobs: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Generate personalized cold emails referencing the portal application & tailored resume."""
    email_map: Dict[str, Dict[str, str]] = {}
    if not jobs:
        return email_map

    if Config.GEMINI_API_KEY and "your_gemini" not in Config.GEMINI_API_KEY:
        compact = [
            {
                "job_hash": j["job_hash"],
                "title": j["job_title"],
                "company": j["company"],
                "portal": j.get("portal", "job portal"),
                "already_applied": j.get("apply_outcome") == "applied",
                "desc": j["job_description"][:400],
            }
            for j in jobs
        ]
        prompt = f"""Write concise, high-impact cold emails (under 130 words each) from this candidate to each company's hiring team.
If "already_applied" is true, mention in the first sentence that the candidate just submitted their application on the portal and is following up directly with their tailored resume attached.

CANDIDATE:
Name: {profile.get('name')}
Education: {profile.get('education')}
Top Skills: {', '.join(profile.get('skills', [])[:10])}
Links: {json.dumps(profile.get('links', {}))}

JOBS:
{json.dumps(compact, indent=2)}

Return ONLY valid JSON as a list of objects with keys "job_hash", "subject", and "body". No markdown, no explanation."""

        try:
            client = genai.Client(api_key=Config.GEMINI_API_KEY)
            resp = client.models.generate_content(model=Config.GEMINI_MODEL, contents=prompt)
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (resp.text or "").strip(), flags=re.IGNORECASE).strip()
            for item in json.loads(cleaned):
                email_map[item["job_hash"]] = {
                    "subject": item["subject"],
                    "body": item["body"],
                }
        except Exception as exc:
            print(f"[06] email -> Gemini batch generation fallback triggered: {exc}")

    for j in jobs:
        if j["job_hash"] not in email_map:
            applied_intro = (
                f"I just submitted my application for the {j['job_title']} role at {j['company']} via {j.get('portal', 'your portal')} "
                f"and wanted to follow up directly with my tailored resume attached."
                if j.get("apply_outcome") == "applied"
                else f"I came across the {j['job_title']} opening at {j['company']} and would love to be considered."
            )
            email_map[j["job_hash"]] = {
                "subject": f"Application Follow-Up: {j['job_title']} — {profile.get('name', 'Thanuj Chaduvu')}",
                "body": (
                    f"Hi {j['company']} Hiring Team,\n\n"
                    f"{applied_intro} I hold a {profile.get('education', 'B.Tech in Data Science')} and specialize in "
                    f"building production Generative AI, LLM, RAG, and FastAPI/Next.js applications.\n\n"
                    f"You can review my projects at {profile.get('links', {}).get('github', '')}.\n\n"
                    f"Best regards,\n{profile.get('name', 'Thanuj Chaduvu')}"
                ),
            }
    return email_map


def email_node(state: AgentState) -> dict:
    """Node 06: Send cold follow-up emails (with ATS-tailored PDF attached) for applied & routed jobs >= 7.0."""
    db = DBManager()
    dry_run = state.get("dry_run", True)

    # Prioritize jobs that were just applied on portals first, followed by external-ATS routed jobs
    all_candidates = [
        r
        for r in state.get("application_results", [])
        if r.get("apply_outcome") in ("applied", "route_email")
        and float(r.get("relevance_score", 0)) >= Config.SCORE_THRESHOLD
    ]
    all_candidates.sort(key=lambda x: (0 if x.get("apply_outcome") == "applied" else 1, -float(x.get("relevance_score", 0))))
    target_jobs = all_candidates[: Config.MAX_EMAILS_PER_DAY]

    if not target_jobs:
        print("[06] email: No eligible jobs to email.")
        return {"emails_sent": [], "total_emailed": 0}

    profile = _load_profile()
    drafts = _generate_emails_batch(target_jobs, profile)
    sent_records: List[Dict[str, Any]] = []

    for idx, job in enumerate(target_jobs):
        hr_email, source = discover_hr_email(job["company"], job["job_url"])
        was_applied = job.get("apply_outcome") == "applied"

        if not hr_email:
            # Preserve 'applied' status if the portal application already succeeded!
            if not was_applied:
                db.update_job_status(job["job_hash"], "manual_required", notes=f"HR email not found ({source})")
            continue

        draft = drafts[job["job_hash"]]
        tailored_pdf = job.get("tailored_resume_path") or Config.RESUME_PATH
        ats_score = job.get("ats_score", 0)

        ok = send_cold_email_smtp(
            to_email=hr_email,
            subject=draft["subject"],
            body_text=draft["body"],
            attach_resume=True,
            resume_path=tailored_pdf,
            dry_run=dry_run,
        )
        if ok:
            final_status = "applied" if was_applied else "email_sent"
            note_prefix = "Applied on portal + cold email sent" if was_applied else "Cold email sent"
            db.update_job_status(
                job_hash=job["job_hash"],
                status=final_status,
                hr_email=hr_email,
                email_sent=1,
                notes=f"{note_prefix} ({source}) | ATS {ats_score}% ({os.path.basename(tailored_pdf)})",
            )
            sent_records.append(
                {
                    "job_title": job["job_title"],
                    "company": job["company"],
                    "hr_email": hr_email,
                    "source": source,
                    "subject": draft["subject"],
                }
            )
            if not dry_run and idx < len(target_jobs) - 1:
                time.sleep(random.uniform(15.0, 25.0))

    print(f"[06] email: Sent {len(sent_records)} cold emails with ATS-tailored resumes attached.")
    return {
        "emails_sent": sent_records,
        "total_emailed": len(sent_records),
    }
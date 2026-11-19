import json
import os
import random
import time
from typing import Any, Dict, List
from google import genai
from playwright.sync_api import Page, sync_playwright
from playwright_stealth import Stealth
from agent.state import AgentState
from config import Config
from database.db_manager import DBManager
from tools.resume_tailor import generate_tailored_resume


def _load_profile() -> Dict[str, Any]:
    with open("data/user_profile.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _generate_screening_answer(question: str, job: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """Use Gemini to answer portal screening questions accurately."""
    fallback = (
        f"I am a Generative AI Engineer (B.Tech Data Science, 2026, CGPA 8.39) with hands-on experience "
        f"building LLM, RAG, and FastAPI/Next.js applications using Python, Google Gemini API, and LangChain. "
        f"I am immediately available and excited to contribute to {job['company']}."
    )
    if not Config.GEMINI_API_KEY or "your_gemini" in Config.GEMINI_API_KEY:
        return fallback

    try:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)
        prompt = (
            f"Answer this job application question concisely in 2 sentences from the candidate's perspective.\n"
            f"Role: {job['job_title']} at {job['company']}\n"
            f"Candidate: {profile.get('name')}, {profile.get('education')}, Skills: {', '.join(profile.get('skills', [])[:10])}\n"
            f"Question: {question}\n"
            f"Return plain text only."
        )
        resp = client.models.generate_content(model=Config.GEMINI_MODEL, contents=prompt)
        return (resp.text or fallback).strip()
    except Exception:
        return fallback


def _fill_and_submit_modal(page: Page, job: Dict[str, Any], profile: Dict[str, Any], resume_path: str) -> bool:
    """Upload the ATS-tailored PDF resume, fill screening textareas/inputs, and click Submit."""
    # 1. Upload tailored ATS resume if file input exists
    file_input = page.query_selector("input[type='file']")
    if file_input and resume_path and os.path.exists(resume_path):
        try:
            file_input.set_input_files(os.path.abspath(resume_path))
            time.sleep(1.5)
        except Exception:
            pass

    # 2. Fill visible textareas (cover letter / 'Why should we hire you?')
    textareas = page.query_selector_all("textarea:visible")
    for idx, ta in enumerate(textareas):
        current_val = (ta.input_value() or "").strip()
        if not current_val:
            placeholder = ta.get_attribute("placeholder") or f"Application question {idx + 1}"
            answer = _generate_screening_answer(placeholder, job, profile)
            ta.fill(answer)
            time.sleep(random.uniform(0.8, 1.4))

    # 3. Click final Submit / Apply button
    submit_selectors = [
        "input[type='submit']:visible",
        "button[type='submit']:visible",
        "button:has-text('Submit'):visible",
        "button:has-text('Submit application'):visible",
        "button:has-text('Send application'):visible",
        "button:has-text('Save and Apply'):visible",
    ]
    for sel in submit_selectors:
        btn = page.query_selector(sel)
        if btn and btn.is_enabled():
            btn.click()
            time.sleep(2.5)
            return True
    return False


def apply_node(state: AgentState) -> dict:
    """Node 05: Tailor ATS resume & apply FIRST on job portals for all jobs scoring >= SCORE_THRESHOLD."""
    db = DBManager()
    profile = _load_profile()
    jobs = state.get("jobs_to_apply", [])
    dry_run = state.get("dry_run", False)

    # Ensure only jobs >= threshold (7.0) are processed
    eligible_jobs = [j for j in jobs if float(j.get("relevance_score", 0)) >= Config.SCORE_THRESHOLD]

    results: List[Dict[str, Any]] = []
    applied_count = 0
    failed_count = 0

    for job in eligible_jobs:
        job_hash = job["job_hash"]
        portal = (job.get("portal") or "").lower()

        # Step A: Tailor an ATS-optimized PDF resume specifically for this job
        tailored_pdf, ats_score = generate_tailored_resume(job)
        job_enriched = {
            **job,
            "tailored_resume_path": tailored_pdf,
            "ats_score": ats_score,
        }

        if dry_run:
            print(
                f"[05] apply [DRY-RUN]: Applied with ATS-tailored PDF ({ats_score}% match) -> "
                f"{job['job_title']} @ {job['company']} ({portal})"
            )
            db.update_job_status(
                job_hash,
                "applied",
                notes=f"Dry-run applied (ATS {ats_score}%: {os.path.basename(tailored_pdf)})",
            )
            results.append({**job_enriched, "apply_outcome": "applied"})
            applied_count += 1
            continue

        # Step B: Attempt live browser portal application using persistent login profile
        try:
            with Stealth().use_sync(sync_playwright()) as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir="data/browser_profile",
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(job["job_url"], wait_until="domcontentloaded", timeout=25000)
                time.sleep(random.uniform(2.0, 3.5))

                page_html_lower = page.content().lower()

                # Check if already applied on portal
                if "already applied" in page_html_lower or "application submitted" in page_html_lower:
                    db.update_job_status(
                        job_hash,
                        "applied",
                        notes=f"Applied on {portal} (ATS {ats_score}%: {os.path.basename(tailored_pdf)})",
                    )
                    results.append({**job_enriched, "apply_outcome": "applied"})
                    applied_count += 1
                    context.close()
                    continue

                # Check if listing redirects to external company ATS ("Apply on company site")
                if "apply on company site" in page_html_lower:
                    db.update_job_status(
                        job_hash,
                        "manual_required",
                        notes=f"External company site; sending cold email with ATS resume ({ats_score}%)",
                    )
                    results.append({**job_enriched, "apply_outcome": "route_email"})
                    context.close()
                    continue

                # Portal-specific & generic Apply button selectors
                apply_selectors = [
                    "#easy_apply_button",          # Internshala
                    "#apply-button",               # Naukri
                    "button.apply-button",         # Naukri variant
                    "button:has-text('Apply now')",
                    "button:has-text('Apply')",
                    "a:has-text('Apply now')",
                    "a:has-text('Apply for this job')",
                ]
                clicked_apply = False
                for sel in apply_selectors:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        clicked_apply = True
                        time.sleep(random.uniform(2.5, 4.0))
                        break

                if not clicked_apply:
                    db.update_job_status(
                        job_hash,
                        "manual_required",
                        notes=f"Direct portal button unavailable; sending cold email ({ats_score}% ATS)",
                    )
                    results.append({**job_enriched, "apply_outcome": "route_email"})
                    context.close()
                    continue

                # Check if 1-click submit succeeded or if a modal/form opened
                updated_html = page.content().lower()
                if (
                    "application has been submitted" in updated_html
                    or "successfully applied" in updated_html
                    or "applied successfully" in updated_html
                ):
                    db.update_job_status(
                        job_hash,
                        "applied",
                        notes=f"Applied on {portal} (ATS {ats_score}%: {os.path.basename(tailored_pdf)})",
                    )
                    results.append({**job_enriched, "apply_outcome": "applied"})
                    applied_count += 1
                elif _fill_and_submit_modal(page, job, profile, tailored_pdf):
                    db.update_job_status(
                        job_hash,
                        "applied",
                        notes=f"Form filled & applied on {portal} (ATS {ats_score}%)",
                    )
                    results.append({**job_enriched, "apply_outcome": "applied"})
                    applied_count += 1
                else:
                    db.update_job_status(
                        job_hash,
                        "manual_required",
                        notes=f"Multi-step ATS form; sending cold email ({ats_score}% ATS)",
                    )
                    results.append({**job_enriched, "apply_outcome": "route_email"})

                context.close()
        except Exception as exc:
            db.update_job_status(job_hash, "failed", notes=f"Playwright error: {exc}")
            results.append({**job_enriched, "apply_outcome": "failed"})
            failed_count += 1

    print(
        f"[05] apply: Portal Applied={applied_count}, Failed={failed_count}, "
        f"External/Email Fallback={sum(1 for r in results if r['apply_outcome'] == 'route_email')}"
    )
    return {
        "application_results": results,
        "total_applied": applied_count,
        "total_failed": failed_count,
    }
import json
import re
import time
from typing import Any, Dict, List
from google import genai
from agent.state import AgentState
from config import Config
from database.db_manager import DBManager


def _load_profile() -> Dict[str, Any]:
    try:
        with open("data/user_profile.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"skills": ["Python", "AI", "LLM"], "experience_level": "Fresher"}


def _fallback_score(jobs: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Deterministic fallback scorer if Gemini API is unavailable or rate-limited[cite: 13]."""
    skills = [s.lower() for s in profile.get("skills", [])]
    scores = {}
    for j in jobs:
        text = f"{j['job_title']} {j['job_description']}".lower()
        matches = sum(1 for s in skills if s in text)
        score = min(9.5, round(5.0 + matches * 0.8, 1))
        scores[j["job_hash"]] = {
            "score": score,
            "reason": f"Fallback keyword match ({matches} profile skills matched).",
        }
    return scores


def score_node(state: AgentState) -> dict:
    """Node 04: Score all filtered jobs in one batched Gemini prompt[cite: 3, 5]."""
    db = DBManager()
    new_jobs = state.get("new_jobs", [])
    if not new_jobs:
        return {"scored_jobs": [], "jobs_to_apply": []}

    profile = _load_profile()

    # Compact payload to stay well within context & token limits
    compact_jobs = [
        {
            "job_hash": j["job_hash"],
            "title": j["job_title"],
            "company": j["company"],
            "location": j["location"],
            "description": j["job_description"][:600],
        }
        for j in new_jobs
    ]

    prompt = f"""You are an expert technical recruiter matching a candidate to job openings.

CANDIDATE PROFILE:
{json.dumps(profile, indent=2)}

JOB LISTINGS TO SCORE:
{json.dumps(compact_jobs, indent=2)}

TASK:
Score each job from 0.0 to 10.0 based on skill alignment, entry-level/fresher suitability, and role relevance.
- 8.0 - 10.0: Strong skill match + entry-level/junior/AI/Python fit.
- 5.0 - 7.9: Partial match or unclear seniority.
- 0.0 - 4.9: Poor stack fit or overly senior.

Return ONLY valid JSON as a list of objects with keys "job_hash", "score" (float), and "reason" (short 1-sentence string). No markdown, no explanation."""

    score_map: Dict[str, Dict[str, Any]] = {}

    if Config.GEMINI_API_KEY and "your_gemini" not in Config.GEMINI_API_KEY:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)
        backoff = 5
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=Config.GEMINI_MODEL,
                    contents=prompt,
                )
                raw_text = (response.text or "").strip()
                # Strip markdown code fences if present[cite: 13]
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()
                parsed = json.loads(cleaned)

                for item in parsed:
                    h = str(item.get("job_hash", ""))
                    if h:
                        score_map[h] = {
                            "score": float(item.get("score", 0.0)),
                            "reason": str(item.get("reason", "")),
                        }
                break
            except Exception as exc:
                err_str = str(exc)
                print(f"[04] score -> Gemini attempt {attempt + 1} failed: {err_str}")
                if "429" in err_str and attempt < 3:
                    print(f"[04] score -> Rate limited (429). Backing off {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    break

    if not score_map:
        print("[04] score -> Using deterministic fallback scorer.")
        score_map = _fallback_score(new_jobs, profile)

    scored_jobs: List[Dict[str, Any]] = []
    for job in new_jobs:
        info = score_map.get(job["job_hash"], {"score": 5.0, "reason": "Default score"})
        job_scored = {
            **job,
            "relevance_score": info["score"],
            "score_reason": info["reason"],
        }
        db.update_job_score(job["job_hash"], info["score"], info["reason"])
        scored_jobs.append(job_scored)

    # Sort descending by score and select Top-N above threshold[cite: 4, 6]
    scored_jobs.sort(key=lambda x: x["relevance_score"], reverse=True)
    jobs_to_apply = [
        j for j in scored_jobs if j["relevance_score"] >= Config.SCORE_THRESHOLD
    ][: Config.MAX_APPLY_PER_DAY]

    print(
        f"[04] score: Scored {len(scored_jobs)} jobs. "
        f"Selected {len(jobs_to_apply)} jobs >= {Config.SCORE_THRESHOLD} for action."
    )
    return {
        "scored_jobs": scored_jobs,
        "jobs_to_apply": jobs_to_apply,
    }
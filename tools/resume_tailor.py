import json
import os
import re
from typing import Any, Dict, List, Tuple
from fpdf import FPDF
from google import genai
from config import Config


def _load_profile() -> Dict[str, Any]:
    with open("data/user_profile.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_text(text: str) -> str:
    """Normalize Unicode punctuation so standard Helvetica PDF fonts render cleanly for ATS parsers."""
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00b7": "-",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def _compute_ats_score(tailored: Dict[str, Any], keywords: List[str]) -> Tuple[float, List[str]]:
    """Verify what percentage of extracted JD keywords appear in the tailored resume text."""
    if not keywords:
        return 100.0, []
    blob = " ".join(
        [
            tailored.get("target_headline", ""),
            tailored.get("summary", ""),
            " ".join(tailored.get("prioritized_skills", [])),
            " ".join(
                " ".join(p.get("bullets", [])) + " " + p.get("description", "")
                for p in tailored.get("projects", [])
            ),
        ]
    ).lower()
    matched = [kw for kw in keywords if kw.lower() in blob]
    missing = [kw for kw in keywords if kw.lower() not in blob]
    score = round((len(matched) / len(keywords)) * 100, 1)
    return score, missing


def _generate_ats_tailored_content(job: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
    """Use Gemini 2.5 Flash to extract JD ATS keywords, tailor content, and verify ATS pass rate."""
    default_payload = {
        "ats_keywords": ["Python", "Generative AI", "LLM", "RAG", "FastAPI", "React", "REST API"],
        "target_headline": f"{profile.get('title', 'Generative AI Engineer')} | {job.get('job_title', '')}",
        "summary": (
            f"Generative AI Engineer ({profile.get('education', 'B.Tech Data Science, 2026')}) with hands-on "
            f"experience designing and deploying LLM-powered applications, Retrieval-Augmented Generation (RAG) "
            f"pipelines, embeddings, and full-stack AI systems using Python, Google Gemini API, OpenAI API, "
            f"LangChain, FastAPI, and Next.js."
        ),
        "prioritized_skills": profile.get("skills", [])[:20],
        "projects": profile.get("projects", []),
    }

    if not Config.GEMINI_API_KEY or "your_gemini" in Config.GEMINI_API_KEY:
        score, _ = _compute_ats_score(default_payload, default_payload["ats_keywords"])
        return default_payload, score

    prompt = f"""You are an expert ATS (Applicant Tracking System) resume optimizer.
Analyze the TARGET JOB below, extract the 12 most important technical & domain ATS keywords from the job title and description, and tailor the candidate's resume so it passes an ATS keyword screen while staying 100% truthful to the candidate's actual skills and projects (never invent fake employers or fake experience).

CANDIDATE PROFILE:
{json.dumps(profile, indent=2)}

TARGET JOB:
Title: {job.get('job_title')}
Company: {job.get('company')}
Description: {job.get('job_description', '')[:2200]}

Return ONLY valid JSON with these exact keys:
- "ats_keywords": list of 12 exact keywords/phrases from the JD that an ATS scans for
- "target_headline": string matching the target job title + core stack (e.g., "Generative AI Engineer | Python, LLMs, RAG & FastAPI")
- "summary": string (3 concise, keyword-rich sentences aligning the candidate's real B.Tech Data Science & GenAI project experience to this JD)
- "prioritized_skills": list of strings (all relevant skills from the candidate's profile ordered so exact JD keyword matches appear first, max 22 items)
- "projects": list of objects with "name", "live_url" (if present), and "bullets" (2 concise, action-verb + metric bullets per project naturally incorporating matching JD terminology)
No markdown fences, no commentary."""

    try:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)
        resp = client.models.generate_content(model=Config.GEMINI_MODEL, contents=prompt)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (resp.text or "").strip(), flags=re.IGNORECASE).strip()
        data = json.loads(cleaned)
        if isinstance(data, dict) and "summary" in data and "prioritized_skills" in data:
            keywords = data.get("ats_keywords", [])
            score, missing = _compute_ats_score(data, keywords)
            candidate_skills_lower = {s.lower(): s for s in profile.get("skills", [])}
            for m in missing:
                if m.lower() in candidate_skills_lower and candidate_skills_lower[m.lower()] not in data["prioritized_skills"]:
                    data["prioritized_skills"].insert(0, candidate_skills_lower[m.lower()])
            score, _ = _compute_ats_score(data, keywords)
            return data, score
    except Exception as exc:
        print(f"   [ResumeTailor] Gemini fallback triggered: {exc}")

    score, _ = _compute_ats_score(default_payload, default_payload["ats_keywords"])
    return default_payload, score


def generate_tailored_resume(job: Dict[str, Any]) -> Tuple[str, float]:
    """
    Generate an ATS-optimized 1-page single-column PDF resume tailored to the target job.
    Returns (pdf_path, ats_keyword_match_percentage).
    """
    try:
        profile = _load_profile()
        tailored, ats_score = _generate_ats_tailored_content(job, profile)

        os.makedirs("data/tailored_resumes", exist_ok=True)
        safe_company = re.sub(r"[^a-zA-Z0-9]+", "_", job.get("company", "company"))[:25].strip("_")
        job_hash = job.get("job_hash", "default")[:8]
        out_path = f"data/tailored_resumes/Thanuj_Chaduvu_{safe_company}_{job_hash}.pdf"

        # Single-column standard-font PDF layout with explicit margins & cursor resets for fpdf2
        pdf = FPDF(format="A4")
        pdf.set_margins(left=12, top=12, right=12)
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()
        usable_w = pdf.epw  # Effective page width (186 mm)

        # Name & Contact Header
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(usable_w, 7, _safe_text(profile.get("name", "THANUJ CHADUVU").upper()))

        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(37, 99, 235)
        pdf.multi_cell(usable_w, 5, _safe_text(tailored.get("target_headline", "Generative AI Engineer")))

        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(55, 65, 81)
        pdf.set_font("Helvetica", "", 9)
        links = profile.get("links", {})
        contact_line = (
            f"{profile.get('location', 'Hyderabad, India')} | {profile.get('phone', '')} | "
            f"{profile.get('email', '')} | {links.get('github', '')} | {links.get('linkedin', '')}"
        )
        pdf.multi_cell(usable_w, 5, _safe_text(contact_line))
        pdf.ln(2)

        def section_heading(title: str):
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(15, 23, 42)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.multi_cell(usable_w, 6, _safe_text(title.upper()))
            pdf.set_draw_color(190, 200, 215)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + usable_w, pdf.get_y())
            pdf.ln(2)

        # 1. Professional Summary
        section_heading("Professional Summary")
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(usable_w, 4.7, _safe_text(tailored.get("summary", "")))
        pdf.ln(2)

        # 2. Technical Skills (ATS Keyword Prioritized)
        section_heading("Technical Skills")
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 9.5)
        skills_str = ", ".join(tailored.get("prioritized_skills", []))
        pdf.multi_cell(usable_w, 4.7, _safe_text(skills_str))
        pdf.ln(2)

        # 3. Projects
        section_heading("Projects")
        for proj in tailored.get("projects", [])[:4]:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 9.8)
            title_text = proj.get("name", "")
            if proj.get("live_url"):
                title_text += f" | Live: {proj['live_url']}"
            pdf.multi_cell(usable_w, 5, _safe_text(title_text))

            pdf.set_font("Helvetica", "", 9.2)
            bullets = proj.get("bullets") or ([proj["description"]] if proj.get("description") else [])
            for b in bullets[:2]:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(usable_w, 4.5, _safe_text(f"- {b}"))
            pdf.ln(1)

        # 4. Education & Certifications
        section_heading("Education & Certifications")
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.multi_cell(usable_w, 5, _safe_text(profile.get("education", "")))
        pdf.set_font("Helvetica", "", 9)
        certs = " | ".join(profile.get("certifications", []))
        if certs:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(usable_w, 4.5, _safe_text(f"Certifications: {certs}"))

        pdf.output(out_path)
        print(f"   [ResumeTailor] ATS Score={ats_score}% -> {out_path}")
        return out_path, ats_score
    except Exception as exc:
        print(f"   [ResumeTailor] Error generating tailored PDF, using base resume: {exc}")
        return Config.RESUME_PATH, 0.0
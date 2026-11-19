import json
import random
import time
from agent.state import AgentState
from config import Config
from database.db_manager import DBManager
from tools.email_finder import has_valid_mx
from tools.email_sender import send_cold_email_smtp


def hr_drip_node(state: AgentState) -> dict:
    """Node 07: Send sequential daily batch of cold emails from HR contact list[cite: 3, 6]."""
    db = DBManager()
    dry_run = state.get("dry_run", True)
    batch = db.get_pending_drip_contacts(limit=Config.DRIP_BATCH_SIZE)

    if not batch:
        print("[07] hr_drip: No pending HR drip contacts remaining.")
        return {"drip_emails_sent": 0}

    try:
        with open("data/user_profile.json", "r", encoding="utf-8") as f:
            profile = json.load(f)
    except Exception:
        profile = {"name": "Chaduvu Thanuj", "education": "B.Tech in Data Science"}

    sent_count = 0
    for idx, contact in enumerate(batch):
        recipient = contact["email"]
        domain = recipient.split("@")[-1]

        if not has_valid_mx(domain):
            db.update_drip_status(recipient, "invalid")
            continue

        company = contact.get("company") or "your team"
        name = contact.get("name") or "Hiring Manager"
        subject = f"AI / Python Developer Inquiry — {profile.get('name', 'Chaduvu Thanuj')}"
        body = (
            f"Hi {name},\n\n"
            f"I admire the engineering work at {company} and wanted to share my profile for any upcoming "
            f"AI, Machine Learning, or Python backend openings. I hold a {profile.get('education', 'B.Tech in Data Science')} "
            f"and specialize in LLM orchestration (LangGraph/LangChain), RAG systems, and full-stack web apps.\n\n"
            f"I have attached my resume for reference and would welcome the chance to connect.\n\n"
            f"Best regards,\n{profile.get('name', 'Chaduvu Thanuj')}"
        )

        if send_cold_email_smtp(recipient, subject, body, attach_resume=True, dry_run=dry_run):
            db.update_drip_status(recipient, "sent")
            sent_count += 1
            if not dry_run and idx < len(batch) - 1:
                time.sleep(random.uniform(15.0, 25.0))
        else:
            db.update_drip_status(recipient, "failed")

    print(f"[07] hr_drip: Processed {len(batch)} contacts, sent {sent_count}.")
    return {"drip_emails_sent": sent_count}
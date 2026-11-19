import email
import imaplib
from typing import Dict
from config import Config


def check_inbox_replies(max_check: int = 15) -> Dict[str, int]:
    """Read recent Gmail inbox messages via IMAP and classify recruiter replies[cite: 6, 8]."""
    counts = {"positive": 0, "bounce": 0, "auto-reply": 0}
    if not Config.GMAIL_USER or not Config.GMAIL_APP_PASSWORD or "your_email" in Config.GMAIL_USER:
        return counts

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(Config.GMAIL_USER, Config.GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            mail.logout()
            return counts

        msg_ids = data[0].split()[-max_check:]
        for num in msg_ids:
            _, msg_data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if not msg_data or not msg_data[0]:
                continue
            raw_header = msg_data[0][1].decode("utf-8", errors="ignore")
            parsed = email.message_from_string(raw_header)
            sender = (parsed.get("From") or "").lower()
            subject = (parsed.get("Subject") or "").lower()

            if "mailer-daemon" in sender or "delivery status" in subject or "undeliverable" in subject:
                counts["bounce"] += 1
            elif any(k in subject for k in ("out of office", "automatic reply", "auto-reply", "received your application")):
                counts["auto-reply"] += 1
            elif any(k in subject for k in ("interview", "shortlisted", "opportunity", "schedule", "call", "assessment")):
                counts["positive"] += 1

        mail.logout()
    except Exception as exc:
        print(f"[IMAP Monitor] Warning: {exc}")

    return counts
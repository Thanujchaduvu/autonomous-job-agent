import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from config import Config


def send_cold_email_smtp(
    to_email: str,
    subject: str,
    body_text: str,
    attach_resume: bool = True,
    resume_path: Optional[str] = None,
    dry_run: bool = True,
) -> bool:
    """Send personalized cold email with tailored PDF resume attached via Gmail SMTP SSL."""
    target_resume = resume_path or Config.RESUME_PATH

    if dry_run:
        print(f"   [DRY-RUN SMTP] To: {to_email} | Resume: {os.path.basename(target_resume)} | Subject: {subject}")
        return True

    if not Config.GMAIL_USER or not Config.GMAIL_APP_PASSWORD:
        print("   [SMTP ERROR] GMAIL_USER or GMAIL_APP_PASSWORD missing in .env")
        return False

    msg = MIMEMultipart()
    msg["From"] = Config.GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    if attach_resume and target_resume and os.path.exists(target_resume):
        with open(target_resume, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(target_resume)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(Config.GMAIL_USER, Config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"   [SMTP ERROR] Failed sending to {to_email}: {exc}")
        return False


def send_html_report_smtp(subject: str, html_body: str, dry_run: bool = True) -> bool:
    """Deliver daily HTML summary report via Gmail SMTP SSL."""
    recipient = Config.REPORT_RECIPIENT_EMAIL or Config.GMAIL_USER
    if dry_run:
        print(f"   [DRY-RUN REPORT] Would email HTML report to {recipient}")
        return True

    if not Config.GMAIL_USER or not Config.GMAIL_APP_PASSWORD or not recipient:
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = Config.GMAIL_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(Config.GMAIL_USER, Config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"   [REPORT SMTP ERROR] {exc}")
        return False
import csv
import io
import os
from flask import Flask, Response, jsonify, render_template
from flask_cors import CORS
from config import Config
from database.db_manager import DBManager

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)


def _get_email_records():
    db = DBManager()
    with db._get_conn() as conn:
        job_emails = conn.execute(
            """
            SELECT job_title, company, hr_email, applied_date, notes
            FROM applications
            WHERE email_sent = 1
            ORDER BY applied_date DESC LIMIT 100
            """
        ).fetchall()
        drip_emails = conn.execute(
            """
            SELECT email, name, company, designation, sent_date, status
            FROM drip_outreach
            ORDER BY id DESC LIMIT 100
            """
        ).fetchall()
    return [dict(r) for r in job_emails], [dict(r) for r in drip_emails]


def _read_recent_logs(max_lines: int = 120) -> str:
    log_file = "logs/agent.log"
    if not os.path.exists(log_file):
        return "No log entries recorded yet. Run `python main.py --run-now --dry-run` to generate logs."
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()[-max_lines:]
    return "".join(lines)


def _read_latest_report() -> str:
    report_path = "logs/latest_report.html"
    if not os.path.exists(report_path):
        return "<p style='color:#6b7280;'>No HTML summary report generated yet.</p>"
    with open(report_path, "r", encoding="utf-8") as f:
        return f.read()


@app.route("/")
def index():
    db = DBManager()
    metrics = db.get_overall_metrics()
    recent_stats = db.get_recent_stats(days=7)
    jobs = db.get_all_applications(limit=200)
    job_emails, drip_emails = _get_email_records()
    logs_text = _read_recent_logs()
    latest_report = _read_latest_report()

    total_jobs = metrics.get("total_jobs") or 0
    total_applied = metrics.get("total_applied") or 0
    total_emailed = metrics.get("total_emailed") or 0
    success_rate = round(((total_applied + total_emailed) / total_jobs * 100), 1) if total_jobs else 0.0

    return render_template(
        "index.html",
        metrics=metrics,
        success_rate=success_rate,
        recent_stats=recent_stats,
        jobs=jobs,
        job_emails=job_emails,
        drip_emails=drip_emails,
        logs_text=logs_text,
        latest_report=latest_report,
    )


@app.route("/api/metrics")
def api_metrics():
    """REST API endpoint for live dashboard metrics & 7-day trend chart."""
    db = DBManager()
    return jsonify(
        {
            "overall": db.get_overall_metrics(),
            "trend_7d": db.get_recent_stats(days=7),
        }
    )


@app.route("/api/jobs")
def api_jobs():
    """REST API endpoint for live jobs table."""
    db = DBManager()
    return jsonify(db.get_all_applications(limit=200))


@app.route("/api/apply-links")
def api_apply_links():
    """Return all scraped jobs with direct apply URLs sorted by relevance score."""
    db = DBManager()
    with db._get_conn() as conn:
        rows = conn.execute(
            """
            SELECT job_title, company, portal, location, relevance_score, status, job_url
            FROM applications
            ORDER BY relevance_score DESC, created_at DESC
            """
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/export/apply-links.csv")
def export_apply_links_csv():
    """Download all scraped job apply links as a CSV spreadsheet."""
    db = DBManager()
    with db._get_conn() as conn:
        rows = conn.execute(
            """
            SELECT job_title, company, portal, location, relevance_score, status, job_url, applied_date
            FROM applications
            ORDER BY relevance_score DESC, created_at DESC
            """
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Job Title", "Company", "Portal", "Location", "Relevance Score", "Status", "Direct Apply Link", "Applied Date"])
    for r in rows:
        writer.writerow([
            r["job_title"],
            r["company"],
            r["portal"],
            r["location"],
            r["relevance_score"],
            r["status"],
            r["job_url"],
            r["applied_date"] or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=scraped_apply_links.csv"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.FLASK_PORT, debug=True)
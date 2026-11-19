import os
import time
from datetime import datetime
from agent.state import AgentState
from tools.email_sender import send_html_report_smtp
from tools.inbox_monitor import check_inbox_replies


def report_node(state: AgentState) -> dict:
    """Node 09: Classify inbox replies, build HTML summary report with direct apply links, and send via SMTP."""
    dry_run = state.get("dry_run", True)
    elapsed = round(time.time() - state.get("start_time", time.time()), 2)
    replies = check_inbox_replies()

    top_jobs = state.get("scored_jobs", [])[:10]
    top_rows = "".join(
        f"<tr>"
        f"<td style='padding:8px;border:1px solid #ddd;'>{j['job_title']}</td>"
        f"<td style='padding:8px;border:1px solid #ddd;'>{j['company']}</td>"
        f"<td style='padding:8px;border:1px solid #ddd;text-transform:capitalize;'>{j['portal']}</td>"
        f"<td style='padding:8px;border:1px solid #ddd;'><b>{j['relevance_score']}/10</b></td>"
        f"<td style='padding:8px;border:1px solid #ddd;text-align:center;'>"
        f"<a href='{j['job_url']}' target='_blank' rel='noopener noreferrer' "
        f"style='display:inline-block;background:#2563eb;color:#ffffff;padding:5px 10px;"
        f"border-radius:5px;text-decoration:none;font-size:12px;font-weight:bold;'>Apply Now &nearr;</a>"
        f"</td>"
        f"</tr>"
        for j in top_jobs
    ) or "<tr><td colspan='5' style='padding:8px;'>No new scored jobs in this run.</td></tr>"

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1f2937; max-width: 760px; margin: auto;">
      <div style="background: #2563eb; color: white; padding: 18px; border-radius: 8px 8px 0 0;">
        <h2 style="margin:0;">Autonomous AI Job Agent — Daily Summary</h2>
        <p style="margin:4px 0 0 0; font-size: 13px;">Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M IST')} | Mode: {'DRY-RUN' if dry_run else 'LIVE'} | Duration: {elapsed}s</p>
      </div>
      <div style="border: 1px solid #e5e7eb; padding: 18px; border-radius: 0 0 8px 8px;">
        <h3>Pipeline Metrics</h3>
        <table style="width:100%; border-collapse: collapse; margin-bottom: 16px;">
          <tr style="background:#f3f4f6;">
            <th style="padding:8px;border:1px solid #ddd;">Scraped</th>
            <th style="padding:8px;border:1px solid #ddd;">New Filtered</th>
            <th style="padding:8px;border:1px solid #ddd;">Auto-Applied</th>
            <th style="padding:8px;border:1px solid #ddd;">Cold Emails</th>
            <th style="padding:8px;border:1px solid #ddd;">HR Drip</th>
            <th style="padding:8px;border:1px solid #ddd;">Failed</th>
          </tr>
          <tr style="text-align:center; font-size:16px;">
            <td style="padding:8px;border:1px solid #ddd;">{state.get('total_scraped', 0)}</td>
            <td style="padding:8px;border:1px solid #ddd;">{state.get('total_new', 0)}</td>
            <td style="padding:8px;border:1px solid #ddd;">{state.get('total_applied', 0)}</td>
            <td style="padding:8px;border:1px solid #ddd;">{state.get('total_emailed', 0)}</td>
            <td style="padding:8px;border:1px solid #ddd;">{state.get('drip_emails_sent', 0)}</td>
            <td style="padding:8px;border:1px solid #ddd;">{state.get('total_failed', 0)}</td>
          </tr>
        </table>

        <h3>Inbox Recruiter Replies (IMAP)</h3>
        <p>Positive: <b>{replies['positive']}</b> | Auto-Replies: <b>{replies['auto-reply']}</b> | Bounces: <b>{replies['bounce']}</b></p>

        <h3>Top Scored Matches Today (Direct Apply Links)</h3>
        <table style="width:100%; border-collapse: collapse;">
          <tr style="background:#f3f4f6; text-align:left;">
            <th style="padding:8px;border:1px solid #ddd;">Role</th>
            <th style="padding:8px;border:1px solid #ddd;">Company</th>
            <th style="padding:8px;border:1px solid #ddd;">Portal</th>
            <th style="padding:8px;border:1px solid #ddd;">Score</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:center;">Direct Apply Link</th>
          </tr>
          {top_rows}
        </table>
      </div>
    </body>
    </html>
    """

    os.makedirs("logs", exist_ok=True)
    with open("logs/latest_report.html", "w", encoding="utf-8") as f:
        f.write(html)

    send_html_report_smtp(
        subject=f"Job Agent Report ({datetime.now().strftime('%Y-%m-%d')}): {state.get('total_new', 0)} New Matches",
        html_body=html,
        dry_run=dry_run,
    )
    print("[09] report: Generated HTML report with direct apply links (saved to logs/latest_report.html).")
    return {"report_html": html}
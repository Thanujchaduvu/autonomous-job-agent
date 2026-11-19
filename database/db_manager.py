import hashlib
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from config import Config


class DBManager:
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def compute_job_hash(job_url: str) -> str:
        """Return first 16 chars of SHA-256 hash of normalized job URL."""
        clean_url = job_url.strip().lower().rstrip("/")
        return hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]

    def init_db(self) -> None:
        """Create all required SQLite tables and indexes if they do not exist."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1. Applications table[cite: 11]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_hash TEXT UNIQUE NOT NULL,
                    job_url TEXT,
                    job_title TEXT,
                    company TEXT,
                    location TEXT,
                    portal TEXT,
                    job_description TEXT,
                    status TEXT DEFAULT 'new',
                    applied_date TEXT,
                    hr_email TEXT,
                    email_sent INTEGER DEFAULT 0,
                    relevance_score REAL DEFAULT 0.0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. HR Contacts cache table[cite: 11]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT,
                    company_domain TEXT,
                    hr_name TEXT,
                    hr_email TEXT,
                    source TEXT,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (company_domain, hr_email)
                )
            """)

            # 3. Daily Stats table[cite: 12]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_scraped INTEGER DEFAULT 0,
                    total_new INTEGER DEFAULT 0,
                    total_applied INTEGER DEFAULT 0,
                    total_emailed INTEGER DEFAULT 0,
                    total_failed INTEGER DEFAULT 0,
                    run_time_seconds REAL DEFAULT 0.0
                )
            """)

            # 4. HR Drip Outreach table[cite: 12]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drip_outreach (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    company TEXT,
                    designation TEXT,
                    sent_date TEXT,
                    status TEXT DEFAULT 'pending'
                )
            """)

            # 5. Cross-Session Memory logs[cite: 6, 7]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT,
                    summary TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # =========================================================================
    # APPLICATIONS CRUD
    # =========================================================================
    def job_exists(self, job_hash: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM applications WHERE job_hash = ?", (job_hash,)
            ).fetchone()
            return row is not None

    def insert_job(self, job: Dict[str, Any]) -> bool:
        """Insert a new filtered job. Returns True if inserted, False if duplicate."""
        job_hash = job.get("job_hash") or self.compute_job_hash(job["job_url"])
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO applications (
                        job_hash, job_url, job_title, company, location,
                        portal, job_description, status, relevance_score, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_hash,
                        job.get("job_url", ""),
                        job.get("job_title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        job.get("portal", ""),
                        job.get("job_description", ""),
                        job.get("status", "new"),
                        job.get("relevance_score", 0.0),
                        job.get("notes", ""),
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update_job_score(self, job_hash: str, score: float, notes: str = "") -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE applications
                SET relevance_score = ?, notes = ?
                WHERE job_hash = ?
                """,
                (score, notes, job_hash),
            )
            conn.commit()

    def update_job_status(
        self,
        job_hash: str,
        status: str,
        hr_email: Optional[str] = None,
        email_sent: int = 0,
        notes: Optional[str] = None,
    ) -> None:
        applied_date = (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if status in ("applied", "email_sent")
            else None
        )
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE applications
                SET status = ?,
                    applied_date = COALESCE(?, applied_date),
                    hr_email = COALESCE(?, hr_email),
                    email_sent = CASE WHEN ? = 1 THEN 1 ELSE email_sent END,
                    notes = COALESCE(?, notes)
                WHERE job_hash = ?
                """,
                (status, applied_date, hr_email, email_sent, notes, job_hash),
            )
            conn.commit()

    def get_all_applications(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # HR CONTACTS CACHE CRUD
    # =========================================================================
    def get_cached_hr_contact(self, company_domain: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM hr_contacts
                WHERE company_domain = ?
                ORDER BY verified DESC, created_at DESC LIMIT 1
                """,
                (company_domain.lower(),),
            ).fetchone()
            return dict(row) if row else None

    def save_hr_contact(
        self,
        company: str,
        company_domain: str,
        hr_email: str,
        source: str,
        hr_name: str = "Hiring Team",
        verified: int = 0,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO hr_contacts (
                    company, company_domain, hr_name, hr_email, source, verified
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (company, company_domain.lower(), hr_name, hr_email.lower(), source, verified),
            )
            conn.commit()

    # =========================================================================
    # HR DRIP OUTREACH CRUD
    # =========================================================================
    def seed_drip_contacts_from_csv(self, csv_path: str = "data/hr_contacts.csv") -> int:
        """Load new contacts from CSV into drip_outreach without duplicating existing emails."""
        if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
            return 0
        df = pd.read_csv(csv_path)
        inserted = 0
        with self._get_conn() as conn:
            for _, row in df.iterrows():
                email = str(row.get("email", "")).strip().lower()
                if not email or "@" not in email:
                    continue
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO drip_outreach (email, name, company, designation, status)
                    VALUES (?, ?, ?, ?, 'pending')
                    """,
                    (
                        email,
                        str(row.get("name", "Hiring Manager")).strip(),
                        str(row.get("company", "")).strip(),
                        str(row.get("designation", "Recruiter")).strip(),
                    ),
                )
                inserted += cur.rowcount
            conn.commit()
        return inserted

    def get_pending_drip_contacts(self, limit: int = Config.DRIP_BATCH_SIZE) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM drip_outreach WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_drip_status(self, email: str, status: str) -> None:
        sent_date = datetime.now().strftime("%Y-%m-%d") if status == "sent" else None
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE drip_outreach SET status = ?, sent_date = ? WHERE email = ?",
                (status, sent_date, email.lower()),
            )
            conn.commit()

    # =========================================================================
    # DAILY STATS & MEMORY CRUD
    # =========================================================================
    def upsert_daily_stats(
        self,
        total_scraped: int,
        total_new: int,
        total_applied: int,
        total_emailed: int,
        total_failed: int,
        run_time_seconds: float,
        date_str: Optional[str] = None,
    ) -> None:
        date_key = date_str or datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO daily_stats (
                    date, total_scraped, total_new, total_applied,
                    total_emailed, total_failed, run_time_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_scraped = total_scraped + excluded.total_scraped,
                    total_new = total_new + excluded.total_new,
                    total_applied = total_applied + excluded.total_applied,
                    total_emailed = total_emailed + excluded.total_emailed,
                    total_failed = total_failed + excluded.total_failed,
                    run_time_seconds = excluded.run_time_seconds
                """,
                (
                    date_key,
                    total_scraped,
                    total_new,
                    total_applied,
                    total_emailed,
                    total_failed,
                    round(run_time_seconds, 2),
                ),
            )
            conn.commit()

    def get_recent_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_stats ORDER BY date DESC LIMIT ?", (days,)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def get_overall_metrics(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) AS total_jobs,
                    SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) AS total_applied,
                    SUM(CASE WHEN email_sent = 1 THEN 1 ELSE 0 END) AS total_emailed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS total_failed
                FROM applications
            """).fetchone()
            return dict(row) if row else {}

    def save_session_summary(self, summary: str) -> None:
        run_date = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO session_memory (run_date, summary) VALUES (?, ?)",
                (run_date, summary),
            )
            conn.commit()

    def get_recent_memories(self, limit: int = 5) -> str:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT run_date, summary FROM session_memory ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            if not rows:
                return "No previous sessions recorded."
            return "\n".join([f"[{r['run_date']}] {r['summary']}" for r in rows])
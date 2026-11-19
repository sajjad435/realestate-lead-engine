import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from src.models import Lead

class LeadTrackerDB:
    def __init__(self, db_path: str = "leads_tracker.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacted_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    city TEXT,
                    state TEXT,
                    source TEXT,
                    website TEXT,
                    phone TEXT,
                    profile_url TEXT,
                    status TEXT DEFAULT 'SENT',
                    email_content TEXT,
                    contacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    followup_due_date TIMESTAMP,
                    followup_status TEXT DEFAULT 'PENDING'
                )
            """)
            # Check if profile_url column exists for existing DB
            cursor.execute("PRAGMA table_info(contacted_leads)")
            cols = [info[1] for info in cursor.fetchall()]
            if "profile_url" not in cols:
                cursor.execute("ALTER TABLE contacted_leads ADD COLUMN profile_url TEXT")
            conn.commit()

    def is_already_contacted(self, email: str) -> bool:
        if not email:
            return False
        clean_email = email.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM contacted_leads WHERE LOWER(email) = ?", (clean_email,))
            return cursor.fetchone() is not None

    def record_lead_contacted(self, lead: Lead, email_content: str, status: str = "SENT"):
        clean_email = lead.email.strip().lower() if lead.email else ""
        if not clean_email:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        followup_due = now + datetime.timedelta(days=3)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO contacted_leads 
                (email, name, city, state, source, website, phone, profile_url, status, email_content, contacted_at, followup_due_date, followup_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (
                clean_email,
                lead.name,
                lead.city,
                lead.state,
                lead.source,
                lead.website or "",
                lead.phone or "",
                lead.profile_url or "",
                status,
                email_content,
                now.isoformat(),
                followup_due.isoformat()
            ))
            conn.commit()

    def get_records_for_report(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, name, city, state, source, website, phone, profile_url, status, email_content, contacted_at, followup_due_date, followup_status
                FROM contacted_leads
                ORDER BY contacted_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_leads_due_for_followup(self, days_threshold: int = 3) -> List[Dict[str, Any]]:
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_threshold)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, name, city, state, source, status, email_content, contacted_at, followup_due_date, followup_status
                FROM contacted_leads
                WHERE followup_status = 'PENDING'
                AND contacted_at <= ?
                ORDER BY contacted_at ASC
            """, (cutoff_date.isoformat(),))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_followup_sent(self, email: str):
        clean_email = email.strip().lower()
        now = datetime.datetime.now(datetime.timezone.utc)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE contacted_leads
                SET followup_status = 'FOLLOWUP_SENT', followup_due_date = ?
                WHERE LOWER(email) = ?
            """, (now.isoformat(), clean_email))
            conn.commit()

    def close(self):
        # sqlite connection in context manager closes automatically
        pass

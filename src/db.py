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
                    followup_status TEXT DEFAULT 'PENDING',
                    followup_stage INTEGER DEFAULT 0,
                    last_followup_at TIMESTAMP
                )
            """)
            # Check if additional columns exist for existing DB
            cursor.execute("PRAGMA table_info(contacted_leads)")
            cols = [info[1] for info in cursor.fetchall()]
            if "profile_url" not in cols:
                cursor.execute("ALTER TABLE contacted_leads ADD COLUMN profile_url TEXT")
            if "message_id" not in cols:
                cursor.execute("ALTER TABLE contacted_leads ADD COLUMN message_id TEXT")
            if "followup_stage" not in cols:
                cursor.execute("ALTER TABLE contacted_leads ADD COLUMN followup_stage INTEGER DEFAULT 0")
            if "last_followup_at" not in cols:
                cursor.execute("ALTER TABLE contacted_leads ADD COLUMN last_followup_at TIMESTAMP")
            conn.commit()

    def is_already_contacted(self, email: str) -> bool:
        if not email:
            return False
        clean_email = email.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM contacted_leads WHERE LOWER(email) = ?", (clean_email,))
            return cursor.fetchone() is not None

    def record_lead_contacted(self, lead: Lead, email_content: str, status: str = "SENT", message_id: Optional[str] = None):
        clean_email = lead.email.strip().lower() if lead.email else ""
        if not clean_email:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        followup_due = now + datetime.timedelta(days=3)
        msg_id = message_id or getattr(lead, "message_id", None) or ""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO contacted_leads 
                (email, name, city, state, source, website, phone, profile_url, status, email_content, contacted_at, followup_due_date, followup_status, message_id, followup_stage, last_followup_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, 0, NULL)
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
                followup_due.isoformat(),
                msg_id
            ))
            conn.commit()

    def get_records_for_report(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, name, city, state, source, website, phone, profile_url, status, email_content, contacted_at, followup_due_date, followup_status, message_id,
                       COALESCE(followup_stage, 0) as followup_stage, last_followup_at
                FROM contacted_leads
                ORDER BY contacted_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_leads_due_for_followup(
        self,
        days_threshold: Optional[int] = None,
        stage_1_days: int = 3,
        stage_2_days: int = 4,
        stage_3_days: int = 5
    ) -> List[Dict[str, Any]]:
        if days_threshold is not None:
            stage_1_days = days_threshold

        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff_stage_1 = now - datetime.timedelta(days=stage_1_days)
        cutoff_stage_2 = now - datetime.timedelta(days=stage_2_days)
        cutoff_stage_3 = now - datetime.timedelta(days=stage_3_days)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, name, city, state, source, status, email_content, contacted_at, followup_due_date, followup_status, message_id,
                       COALESCE(followup_stage, 0) as followup_stage, last_followup_at
                FROM contacted_leads
                WHERE followup_status NOT IN ('COMPLETED', 'UNSUBSCRIBED', 'RESPONDED')
                ORDER BY contacted_at ASC
            """)
            rows = cursor.fetchall()

            due_leads = []
            for r in rows:
                d = dict(r)
                stage = d.get("followup_stage") or 0
                status = (d.get("followup_status") or "").upper()
                last_followup = d.get("last_followup_at")
                contacted_at = d.get("contacted_at")

                # If stage was 0 or status is PENDING, next target is Stage 1
                if stage == 0 and status in ("PENDING", "SENT"):
                    if contacted_at:
                        try:
                            dt = datetime.datetime.fromisoformat(contacted_at)
                            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                                dt = dt.replace(tzinfo=datetime.timezone.utc)
                        except Exception:
                            dt = cutoff_stage_1
                        if dt <= cutoff_stage_1:
                            d["target_stage"] = 1
                            due_leads.append(d)
                elif stage == 1 or status == "FOLLOWUP_SENT" or status == "FOLLOWUP_1_SENT":
                    # Stage 2 check
                    ref_dt_str = last_followup or contacted_at
                    if ref_dt_str:
                        try:
                            dt = datetime.datetime.fromisoformat(ref_dt_str)
                            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                                dt = dt.replace(tzinfo=datetime.timezone.utc)
                        except Exception:
                            dt = cutoff_stage_2
                        if dt <= cutoff_stage_2:
                            d["target_stage"] = 2
                            due_leads.append(d)
                elif stage == 2 or status == "FOLLOWUP_2_SENT":
                    # Stage 3 check
                    ref_dt_str = last_followup or contacted_at
                    if ref_dt_str:
                        try:
                            dt = datetime.datetime.fromisoformat(ref_dt_str)
                            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                                dt = dt.replace(tzinfo=datetime.timezone.utc)
                        except Exception:
                            dt = cutoff_stage_3
                        if dt <= cutoff_stage_3:
                            d["target_stage"] = 3
                            due_leads.append(d)

            return due_leads

    def mark_followup_sent(self, email: str, stage: int = 1):
        clean_email = email.strip().lower()
        now = datetime.datetime.now(datetime.timezone.utc)
        status_label = f"FOLLOWUP_{stage}_SENT" if stage < 3 else "COMPLETED"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE contacted_leads
                SET followup_stage = ?,
                    followup_status = ?,
                    last_followup_at = ?,
                    followup_due_date = ?
                WHERE LOWER(email) = ?
            """, (stage, status_label, now.isoformat(), now.isoformat(), clean_email))
            conn.commit()

    def close(self):
        # sqlite connection in context manager closes automatically
        pass

import pytest
import datetime
from unittest.mock import MagicMock, patch
from src.models import Lead
from src.mailer import EmailTemplate, ColdEmailer
from src.db import LeadTrackerDB

def test_followup_body_is_clean_without_quote_markers():
    lead = Lead(name="Aarif Buddha", city="Patna", email="aarifkumar24@gmail.com")
    original_content = (
        "Subject: Quick question regarding patna real estate listings - Buddha\n\n"
        "Hi Buddha,\n\n"
        "I came across your real estate profile in patna and really liked your property listings.\n"
        "Best regards,\nSajjad Wali"
    )

    for stage in [1, 2, 3]:
        subject, body = EmailTemplate.render_followup(
            lead=lead,
            stage=stage,
            sender_name="Sajjad Wali",
            portfolio_url="https://sajjad-wali-portfolio.vercel.app/",
            original_content=original_content,
            contacted_date="2026-11-11"
        )
        # 1. Subject must preserve threading Re:
        assert subject.startswith("Re: ")
        assert "patna" in subject.lower()

        # 2. Body must NOT contain manual quote markers or raw pasted history
        assert "--------------------------------------------------" not in body
        assert "wrote:" not in body
        assert not any(line.strip().startswith(">") for line in body.splitlines())

def test_followup_has_distinct_templates_for_stages():
    lead = Lead(name="Aarif Buddha", city="Patna", email="aarifkumar24@gmail.com")
    
    _, body_1 = EmailTemplate.render_followup(lead=lead, stage=1, sender_name="Sajjad Wali")
    _, body_2 = EmailTemplate.render_followup(lead=lead, stage=2, sender_name="Sajjad Wali")
    _, body_3 = EmailTemplate.render_followup(lead=lead, stage=3, sender_name="Sajjad Wali")

    # All three stages must be distinct messages
    assert body_1 != body_2
    assert body_2 != body_3
    assert body_1 != body_3

    # Stage 1: polite floating back
    assert "floating this back" in body_1.lower()
    # Stage 2: new angle / buyer ideas
    assert "ideas" in body_2.lower() or "mobile" in body_2.lower()
    # Stage 3: closing loop / final follow-up
    assert "final" in body_3.lower() or "clutter" in body_3.lower()

def test_followup_mime_threading_headers_without_quote_in_body():
    emailer = ColdEmailer(dry_run=True, sender_email="sajjadwali257@gmail.com", sender_name="Sajjad Wali")
    lead = Lead(name="Buddha Property Dealer", city="Patna", email="aarifkumar24@gmail.com")
    original_msg_id = "<orig-message-uuid-123@gmail.com>"
    original_content = "Subject: Hi Buddha\n\nOriginal outreach text"

    msg = emailer.build_followup_mime_message(
        lead=lead,
        stage=1,
        original_msg_id=original_msg_id,
        original_content=original_content,
        contacted_date="2026-11-11"
    )

    assert msg["In-Reply-To"] == original_msg_id
    assert msg["References"] == original_msg_id
    assert msg["Subject"].startswith("Re: ")

    payload = msg.get_payload(decode=True).decode("utf-8")
    assert "--------------------------------------------------" not in payload
    assert "> Original outreach text" not in payload

def test_db_multi_stage_tracking_and_transitions(tmp_path):
    db_file = tmp_path / "test_leads.db"
    db = LeadTrackerDB(str(db_file))

    lead = Lead(name="Buddha", city="Patna", email="buddha@patna.com")
    db.record_lead_contacted(lead, email_content="Subject: Initial\n\nBody", message_id="<msg-1@patna.com>")

    # Stage 1 Due (0 days threshold for test)
    due_leads = db.get_leads_due_for_followup(stage_1_days=0, stage_2_days=0, stage_3_days=0)
    assert len(due_leads) == 1
    assert due_leads[0]["email"] == "buddha@patna.com"
    assert due_leads[0]["target_stage"] == 1

    # Mark Stage 1 Sent
    db.mark_followup_sent("buddha@patna.com", stage=1)
    
    # Immediately check: Stage 1 must NOT be due again
    due_leads_after_1 = db.get_leads_due_for_followup(stage_1_days=0, stage_2_days=999, stage_3_days=999)
    assert len(due_leads_after_1) == 0

    # With stage 2 days=0, Stage 2 becomes due
    due_leads_stage_2 = db.get_leads_due_for_followup(stage_1_days=0, stage_2_days=0, stage_3_days=999)
    assert len(due_leads_stage_2) == 1
    assert due_leads_stage_2[0]["target_stage"] == 2

    # Mark Stage 2 Sent
    db.mark_followup_sent("buddha@patna.com", stage=2)

    # Check Stage 3
    due_leads_stage_3 = db.get_leads_due_for_followup(stage_1_days=0, stage_2_days=0, stage_3_days=0)
    assert len(due_leads_stage_3) == 1
    assert due_leads_stage_3[0]["target_stage"] == 3

    # Mark Stage 3 Sent (Final)
    db.mark_followup_sent("buddha@patna.com", stage=3)

    # No more followups allowed
    due_final = db.get_leads_due_for_followup(stage_1_days=0, stage_2_days=0, stage_3_days=0)
    assert len(due_final) == 0

def test_duplicate_prevention_same_stage_never_sent_twice(tmp_path):
    db_file = tmp_path / "test_leads_dup.db"
    db = LeadTrackerDB(str(db_file))

    lead = Lead(name="Buddha", city="Patna", email="buddha@patna.com")
    db.record_lead_contacted(lead, email_content="Subject: Initial\n\nBody", message_id="<msg-1@patna.com>")

    db.mark_followup_sent("buddha@patna.com", stage=1)
    
    # Query multiple times under any condition: stage 1 must never be returned
    for _ in range(3):
        due = db.get_leads_due_for_followup(stage_1_days=0, stage_2_days=999, stage_3_days=999)
        assert len(due) == 0

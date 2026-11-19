import pytest
from unittest.mock import MagicMock, patch
from src.models import Lead
from src.mailer import EmailTemplate, ColdEmailer
from src.db import LeadTrackerDB
from src.pipeline import LeadAcquisitionPipeline

def test_render_followup_includes_quoted_previous_email():
    lead = Lead(name="Deen Ahmed", city="Montreal", email="deen@realtor.com")
    original_email = (
        "Subject: Quick question regarding Montreal real estate listings - Deen\n\n"
        "Hi Deen,\n\n"
        "I noticed your Montreal listings and saw you don't have a personal portfolio site.\n"
        "Would you like a free preview?\n\n"
        "Best,\nSajjad Wali"
    )
    
    subject, body = EmailTemplate.render_followup(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad.dev",
        original_content=original_email,
        contacted_date="2026-11-16"
    )
    
    # 1. Subject should preserve original subject with Re: prefix
    assert subject.startswith("Re: ")
    assert "Montreal" in subject
    
    # 2. Body must contain the new follow-up greeting & message
    assert "Hi Deen," in body
    assert "floating this back to the top of your inbox" in body

    # 3. Body must include quoted history of the previous email below
    assert "On 2026-11-16, Sajjad Wali wrote:" in body
    assert "> Hi Deen," in body
    assert "> I noticed your Montreal listings" in body

def test_build_followup_mime_message_has_threading_headers():
    emailer = ColdEmailer(
        dry_run=True,
        sender_email="sajjadwali007@gmail.com",
        sender_name="Sajjad Wali"
    )
    lead = Lead(name="Michaël Marcotte", city="Montreal", email="m.marcotte@remax.com")
    original_msg_id = "<initial.123456@gmail.com>"
    original_content = "Subject: Hello\n\nOriginal outreach message."
    
    msg = emailer.build_followup_mime_message(
        lead=lead,
        original_msg_id=original_msg_id,
        original_content=original_content,
        contacted_date="2026-11-16"
    )
    
    assert msg["In-Reply-To"] == original_msg_id
    assert msg["References"] == original_msg_id
    assert msg["Subject"].startswith("Re: ")
    # Ensure quoted content is in the payload (decoded from base64/utf-8)
    payload = msg.get_payload(decode=True).decode("utf-8")
    assert "> Original outreach message." in payload

def test_db_tracks_and_retrieves_message_id(tmp_path):
    db_file = tmp_path / "test_tracker.db"
    db = LeadTrackerDB(str(db_file))
    
    lead = Lead(name="Sarah Connor", city="Los Angeles", email="sarah@realty.com")
    orig_msg_id = "<msg-uuid-999@domain.com>"
    email_content = "Subject: Hi Sarah\n\nDo you need a modern website?"
    
    db.record_lead_contacted(lead, email_content=email_content, message_id=orig_msg_id)
    
    # Retrieve due followups (threshold=0 to get it immediately)
    leads = db.get_leads_due_for_followup(days_threshold=0)
    assert len(leads) == 1
    record = leads[0]
    assert record["email"] == "sarah@realty.com"
    assert record["message_id"] == orig_msg_id
    assert record["email_content"] == email_content

def test_pipeline_followup_passes_thread_context_to_mailer(tmp_path):
    db_file = tmp_path / "leads.db"
    csv_file = tmp_path / "locations.csv"
    csv_file.write_text("city,state\nMontreal,QC\n", encoding="utf-8")
    
    db = LeadTrackerDB(str(db_file))
    lead = Lead(name="Deen Ahmed", city="Montreal", email="deen@realtor.com")
    orig_msg_id = "<original-msg-12345@gmail.com>"
    orig_content = "Subject: Web Design Offer\n\nInitial email body."
    db.record_lead_contacted(lead, email_content=orig_content, message_id=orig_msg_id)
    
    pipeline = LeadAcquisitionPipeline(
        csv_path=str(csv_file),
        db_path=str(db_file),
        dry_run=True,
        sender_email="test@gmail.com",
        sender_name="Sajjad Wali"
    )
    
    with patch.object(pipeline.emailer, "send_followup", wraps=pipeline.emailer.send_followup) as mock_send:
        count = pipeline.run_followups(days_threshold=0, enforce_business_hours=False)
        assert count == 1
        
        # Verify send_followup was called with original_msg_id and original_content
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs.get("original_msg_id") == orig_msg_id
        assert kwargs.get("original_content") == orig_content

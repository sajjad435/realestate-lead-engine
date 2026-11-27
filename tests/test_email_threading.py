import pytest
from unittest.mock import MagicMock, patch
from src.models import Lead
from src.mailer import EmailTemplate, ColdEmailer
from src.db import LeadTrackerDB
from src.pipeline import LeadAcquisitionPipeline

def test_render_followup_includes_quoted_previous_email_history():
    lead = Lead(name="Deen Ahmed", city="Montreal", email="deen@realtor.com")
    original_email = (
        "Subject: Quick question regarding Montreal real estate listings - Deen\n\n"
        "Hi Deen,\n\n"
        "I noticed your Montreal listings and saw you don't have a personal portfolio site.\n"
        "Would you like a sample preview?\n\n"
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
    
    # 2. Body must contain the clean new follow-up greeting & message
    assert "Hi Deen," in body
    assert "floating this back to the top of your inbox" in body

    # 3. Body must include quoted history of the previous email below
    assert "On 2026-11-16, Sajjad Wali wrote:" in body
    assert "--------------------------------------------------" in body
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
    payload = msg.get_payload(decode=True).decode("utf-8")
    assert "--------------------------------------------------" in payload
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


def test_build_followup_mime_message_never_uses_fake_thread_ref():
    emailer = ColdEmailer(
        dry_run=True,
        sender_email="sajjadwali007@gmail.com",
        sender_name="Sajjad Wali"
    )
    lead = Lead(name="Test Agent", city="Columbus", email="agent@realty.com")
    
    # 1. When original_msg_id is None, must NOT invent dummy thread.ref header
    msg_none = emailer.build_followup_mime_message(
        lead=lead,
        original_msg_id=None,
        original_content="Subject: Hello\n\nContent"
    )
    assert msg_none.get("In-Reply-To") is None
    assert msg_none.get("References") is None

    # 2. When original_msg_id is a bogus fake ID (e.g. initial@mail.com or thread.ref), must reject it
    msg_fake = emailer.build_followup_mime_message(
        lead=lead,
        original_msg_id="<agent@realty.com.initial@mail.com>",
        original_content="Subject: Hello\n\nContent"
    )
    assert msg_fake.get("In-Reply-To") is None
    assert msg_fake.get("References") is None


def test_pipeline_followup_does_not_pass_bogus_fallback_message_id(tmp_path):
    db_file = tmp_path / "leads_no_msgid.db"
    csv_file = tmp_path / "locations.csv"
    csv_file.write_text("city,state\nColumbus,OH\n", encoding="utf-8")
    
    db = LeadTrackerDB(str(db_file))
    lead = Lead(name="John Doe", city="Columbus", email="johndoe@realtor.com")
    db.record_lead_contacted(lead, email_content="Subject: Hi\n\nBody", message_id=None)
    
    pipeline = LeadAcquisitionPipeline(
        csv_path=str(csv_file),
        db_path=str(db_file),
        dry_run=True,
        sender_email="test@gmail.com",
        sender_name="Sajjad Wali"
    )
    
    with patch.object(pipeline.emailer, "send_followup", wraps=pipeline.emailer.send_followup) as mock_send:
        pipeline.run_followups(days_threshold=0, enforce_business_hours=False)
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        passed_msg_id = kwargs.get("original_msg_id")
        # Must NEVER be the fake fallback like <johndoe@realtor.com.initial@mail.com>
        assert passed_msg_id != "<johndoe@realtor.com.initial@mail.com>"
        assert passed_msg_id is None or not (
            "initial@mail.com" in str(passed_msg_id) or "thread.ref" in str(passed_msg_id)
        )


def test_db_get_message_id_filters_fake_ids(tmp_path):
    db_file = tmp_path / "test_filter_ids.db"
    db = LeadTrackerDB(str(db_file))
    
    # 1. Real ID
    lead1 = Lead(name="Agent One", city="Columbus", email="agent1@realty.com")
    db.record_lead_contacted(lead1, email_content="Content", message_id="<real-id-12345@gmail.com>")
    assert db.get_message_id_for_email("agent1@realty.com") == "<real-id-12345@gmail.com>"
    
    # 2. Fake .initial@mail.com ID
    lead2 = Lead(name="Agent Two", city="Columbus", email="agent2@realty.com")
    db.record_lead_contacted(lead2, email_content="Content", message_id="<agent2@realty.com.initial@mail.com>")
    assert db.get_message_id_for_email("agent2@realty.com") is None

    # 3. Non-existent lead
    assert db.get_message_id_for_email("unknown@realty.com") is None


def test_db_sync_message_id_from_imap_mock(tmp_path):
    db_file = tmp_path / "test_imap_sync.db"
    db = LeadTrackerDB(str(db_file))
    lead = Lead(name="Agent IMAP", city="Columbus", email="imap_agent@realty.com")
    db.record_lead_contacted(lead, email_content="Content", message_id=None)

    fake_header = b"Message-ID: <imap.real.msg.999@gmail.com>\r\nSubject: Test\r\n\r\n"

    with patch("imaplib.IMAP4_SSL") as mock_imap:
        instance = MagicMock()
        mock_imap.return_value = instance
        instance.login.return_value = ("OK", [b"Logged in"])
        instance.select.return_value = ("OK", [b"1"])
        instance.search.return_value = ("OK", [b"101 102"])
        instance.fetch.return_value = ("OK", [(b"101", fake_header)])

        retrieved_id = db.sync_message_id_from_imap(
            email="imap_agent@realty.com",
            sender_email="sajjad@gmail.com",
            sender_password="secret_pass"
        )

        assert retrieved_id == "<imap.real.msg.999@gmail.com>"
        # Should now be saved in the database
        assert db.get_message_id_for_email("imap_agent@realty.com") == "<imap.real.msg.999@gmail.com>"


def test_pipeline_dry_run_attribute_and_imap_lookup_with_credentials(tmp_path):
    db_file = tmp_path / "leads_dryrun_test.db"
    csv_file = tmp_path / "locations.csv"
    csv_file.write_text("city,state\nColumbus,OH\n", encoding="utf-8")
    
    db = LeadTrackerDB(str(db_file))
    lead = Lead(name="Jane Doe", city="Columbus", email="janedoe@realtor.com")
    db.record_lead_contacted(lead, email_content="Subject: Hi\n\nBody", message_id=None)
    
    pipeline = LeadAcquisitionPipeline(
        csv_path=str(csv_file),
        db_path=str(db_file),
        dry_run=False,
        sender_email="sajjad@gmail.com",
        sender_password="secret_password",
        sender_name="Sajjad Wali"
    )
    
    # 1. Pipeline instance must have dry_run attribute
    assert hasattr(pipeline, "dry_run")
    assert pipeline.dry_run is False

    # 2. When run_followups runs with sender credentials and dry_run=False,
    # it must not throw AttributeError: 'LeadAcquisitionPipeline' object has no attribute 'dry_run'
    with patch.object(pipeline.db, "sync_message_id_from_imap", return_value="<retrieved@gmail.com>") as mock_sync, \
         patch.object(pipeline.emailer, "send_followup", return_value=(True, "Success", "Content")):
        count = pipeline.run_followups(days_threshold=0, enforce_business_hours=False)
        assert count == 1
        mock_sync.assert_called_once_with("janedoe@realtor.com", "sajjad@gmail.com", "secret_password")




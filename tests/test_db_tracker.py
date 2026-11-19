import pytest
import os
from src.models import Lead
from src.db import LeadTrackerDB

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_tracker.db"
    tracker = LeadTrackerDB(db_path=str(db_file))
    yield tracker
    tracker.close()

def test_db_stores_and_retrieves_source_url(temp_db):
    lead = Lead(
        name="Briahna Ross",
        city="Tampa",
        email="briahna@realty.com",
        source="Instagram",
        profile_url="https://instagram.com/briahnarossrealtor"
    )
    temp_db.record_lead_contacted(lead, "Test Pitch", "SENT")
    records = temp_db.get_records_for_report()
    assert len(records) == 1
    assert records[0]["profile_url"] == "https://instagram.com/briahnarossrealtor"

def test_db_record_contact_and_deduplication(temp_db):
    lead = Lead(
        name="Alex Mercer",
        city="Detroit",
        email="alex@detroitliving.com",
        source="Google Maps"
    )
    temp_db.record_lead_contacted(
        lead=lead,
        email_content="Hi Alex, here is my portfolio...",
        status="SENT"
    )
    assert temp_db.is_already_contacted("alex@detroitliving.com") is True
    assert temp_db.is_already_contacted("ALEX@detroitliving.com") is True  # Case insensitive check

def test_db_get_daily_summary(temp_db):
    lead1 = Lead(name="Agent 1", city="Detroit", email="a1@test.com", source="Google Maps")
    lead2 = Lead(name="Agent 2", city="Texas", email="a2@test.com", source="Instagram")

    temp_db.record_lead_contacted(lead1, "Pitch 1", "SENT")
    temp_db.record_lead_contacted(lead2, "Pitch 2", "SENT")

    records = temp_db.get_records_for_report()
    assert len(records) == 2
    emails = {r["email"] for r in records}
    assert emails == {"a1@test.com", "a2@test.com"}

def test_db_followup_workflow(temp_db):
    lead = Lead(name="Agent Followup", city="Detroit", email="follow@test.com")
    temp_db.record_lead_contacted(lead, "Initial Pitch", "SENT")
    
    # Mark as due
    due_leads = temp_db.get_leads_due_for_followup(days_threshold=0)
    assert len(due_leads) == 1
    assert due_leads[0]["email"] == "follow@test.com"

    # Mark followup sent
    temp_db.mark_followup_sent("follow@test.com")
    due_after = temp_db.get_leads_due_for_followup(days_threshold=0)
    assert len(due_after) == 0

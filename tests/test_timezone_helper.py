import pytest
import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock
from src.timezone_helper import TimezoneHelper
from src.models import Lead

def test_timezone_helper_maps_indian_cities_to_kolkata():
    assert TimezoneHelper.get_timezone_for_location("patna") == "Asia/Kolkata"
    assert TimezoneHelper.get_timezone_for_location("Ranchi") == "Asia/Kolkata"
    assert TimezoneHelper.get_timezone_for_location("boriwali") == "Asia/Kolkata"
    assert TimezoneHelper.get_timezone_for_location("Pune") == "Asia/Kolkata"
    assert TimezoneHelper.get_timezone_for_location("Mumbai, India") == "Asia/Kolkata"

def test_timezone_helper_maps_us_eastern_cities():
    assert TimezoneHelper.get_timezone_for_location("Miami") == "America/New_York"
    assert TimezoneHelper.get_timezone_for_location("Detroit") == "America/New_York"
    assert TimezoneHelper.get_timezone_for_location("New York City") == "America/New_York"
    assert TimezoneHelper.get_timezone_for_location("Montreal") in ("America/Toronto", "America/New_York")
    assert TimezoneHelper.get_timezone_for_location("Durham") == "America/New_York"
    assert TimezoneHelper.get_timezone_for_location("Atlanta") == "America/New_York"
    assert TimezoneHelper.get_timezone_for_location("Philadelphia") == "America/New_York"

def test_timezone_helper_maps_us_central_cities():
    assert TimezoneHelper.get_timezone_for_location("Chicago") == "America/Chicago"
    assert TimezoneHelper.get_timezone_for_location("Dallas") == "America/Chicago"
    assert TimezoneHelper.get_timezone_for_location("Houston") == "America/Chicago"
    assert TimezoneHelper.get_timezone_for_location("Texas") == "America/Chicago"

def test_timezone_helper_maps_us_pacific_cities():
    assert TimezoneHelper.get_timezone_for_location("Los Angeles") == "America/Los_Angeles"
    assert TimezoneHelper.get_timezone_for_location("Irvine") == "America/Los_Angeles"
    assert TimezoneHelper.get_timezone_for_location("San Francisco") == "America/Los_Angeles"
    assert TimezoneHelper.get_timezone_for_location("Seattle") == "America/Los_Angeles"
    assert TimezoneHelper.get_timezone_for_location("california") == "America/Los_Angeles"

def test_timezone_helper_maps_uk_and_europe():
    assert TimezoneHelper.get_timezone_for_location("London, UK") == "Europe/London"
    assert TimezoneHelper.get_timezone_for_location("Manchester") == "Europe/London"
    assert TimezoneHelper.get_timezone_for_location("Paris, France") == "Europe/Paris"
    assert TimezoneHelper.get_timezone_for_location("Berlin, Germany") == "Europe/Berlin"
    assert TimezoneHelper.get_timezone_for_location("Madrid, Spain") == "Europe/Madrid"
    assert TimezoneHelper.get_timezone_for_location("Rome, Italy") == "Europe/Rome"

def test_timezone_helper_maps_australia_and_middle_east_and_asia():
    assert TimezoneHelper.get_timezone_for_location("Sydney, Australia") == "Australia/Sydney"
    assert TimezoneHelper.get_timezone_for_location("Melbourne") == "Australia/Melbourne"
    assert TimezoneHelper.get_timezone_for_location("Perth") == "Australia/Perth"
    assert TimezoneHelper.get_timezone_for_location("Dubai, UAE") == "Asia/Dubai"
    assert TimezoneHelper.get_timezone_for_location("Singapore") == "Asia/Singapore"
    assert TimezoneHelper.get_timezone_for_location("Toronto, Canada") == "America/Toronto"
    assert TimezoneHelper.get_timezone_for_location("Vancouver") == "America/Vancouver"

def test_timezone_helper_global_10_30_am_dispatch_windows():
    # 1. London Morning at 10:30 AM (UTC 10:30)
    utc_london = datetime.datetime(2026, 11, 20, 10, 30, 0, tzinfo=datetime.timezone.utc)
    in_win, msg = TimezoneHelper.is_in_followup_window("London", now_utc=utc_london)
    assert in_win is True
    assert "10:30 AM" in msg

    # 2. Dubai Morning at 10:30 AM (UTC 06:30)
    utc_dubai = datetime.datetime(2026, 11, 20, 6, 30, 0, tzinfo=datetime.timezone.utc)
    in_win, msg = TimezoneHelper.is_in_followup_window("Dubai", now_utc=utc_dubai)
    assert in_win is True
    assert "10:30 AM" in msg

    # 3. Sydney Morning at 10:30 AM (UTC 23:30 previous day)
    utc_sydney = datetime.datetime(2026, 11, 20, 23, 30, 0, tzinfo=datetime.timezone.utc)
    in_win, msg = TimezoneHelper.is_in_followup_window("Sydney", now_utc=utc_sydney)
    assert in_win is True
    assert "10:30 AM" in msg

def test_timezone_helper_followup_window_detection():
    # Simulated UTC time: 05:00 UTC (10:30 AM IST / 12:00 AM Midnight EST)
    test_utc = datetime.datetime(2026, 11, 20, 5, 0, 0, tzinfo=datetime.timezone.utc)
    
    # In India (Patna): 10:30 AM -> Must be in business morning window
    in_win_india, msg_india = TimezoneHelper.is_in_followup_window("Patna", now_utc=test_utc)
    assert in_win_india is True
    assert "10:30 AM" in msg_india

    # In US East (Miami): 00:00 AM (Midnight) -> Must be blocked as night time
    in_win_us, msg_us = TimezoneHelper.is_in_followup_window("Miami", now_utc=test_utc)
    assert in_win_us is False
    assert "night" in msg_us.lower() or "outside" in msg_us.lower()

    # In US Pacific (Los Angeles): 21:00 PM (Night) -> Must be blocked as night time
    in_win_la, msg_la = TimezoneHelper.is_in_followup_window("Los Angeles", now_utc=test_utc)
    assert in_win_la is False

def test_timezone_helper_allows_us_morning_at_us_time():
    # Simulated UTC time: 15:30 UTC (10:30 AM EST in Miami / 09:30 AM CST in Chicago / 9:00 PM IST in India)
    test_utc = datetime.datetime(2026, 11, 20, 15, 30, 0, tzinfo=datetime.timezone.utc)

    # In Miami: 10:30 AM -> Must be in business morning window
    in_win_miami, msg_miami = TimezoneHelper.is_in_followup_window("Miami", now_utc=test_utc)
    assert in_win_miami is True

    # In India (Patna): 9:00 PM -> Must be blocked (too late in India)
    in_win_patna, msg_patna = TimezoneHelper.is_in_followup_window("Patna", now_utc=test_utc)
    assert in_win_patna is False

@patch("src.pipeline.ColdEmailer.send_followup")
def test_pipeline_followup_enforces_agent_local_timezone(mock_send, tmp_path):
    from src.pipeline import LeadAcquisitionPipeline
    from src.db import LeadTrackerDB

    db_path = str(tmp_path / "test_tz.db")
    db = LeadTrackerDB(db_path=db_path)
    
    # 1. Indian lead contacted 4 days ago
    lead_india = Lead(name="Patna Realty", city="patna", email="patna@test.com")
    # 2. US lead contacted 4 days ago
    lead_us = Lead(name="Miami Homes", city="Miami", email="miami@test.com")

    # Record both leads with contacted_at 4 days ago
    old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=4)
    db.record_lead_contacted(lead_india, "Hello", status="SENT")
    db.record_lead_contacted(lead_us, "Hello", status="SENT")
    
    # Manually backdate contacted_at
    with db._get_connection() as conn:
        conn.execute("UPDATE contacted_leads SET contacted_at = ?", (old_time.isoformat(),))
        conn.commit()

    pipeline = LeadAcquisitionPipeline(
        db_path=db_path,
        csv_path=str(tmp_path / "locations.csv"),
        pdf_path=str(tmp_path / "report.pdf"),
        dry_run=True
    )
    mock_send.return_value = (True, "Simulated", "Content")

    # Set current time to 05:00 UTC (10:30 AM IST in India, 12:00 AM Midnight in Miami)
    test_utc = datetime.datetime(2026, 11, 20, 5, 0, 0, tzinfo=datetime.timezone.utc)
    
    with patch("src.timezone_helper.TimezoneHelper.get_current_utc", return_value=test_utc):
        sent_count = pipeline.run_followups(days_threshold=3, enforce_business_hours=True)

    # Only India lead must be sent! US lead must be safely postponed because it is night in Miami!
    assert sent_count == 1
    assert mock_send.call_count == 1
    assert mock_send.call_args[0][0].email == "patna@test.com"

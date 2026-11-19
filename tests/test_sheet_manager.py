import pytest
import csv
import os
from src.sheet_manager import SheetManager

@pytest.fixture
def sample_csv(tmp_path):
    csv_file = tmp_path / "target_locations.csv"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Location", "Status", "Leads_Found", "Emails_Sent", "Last_Processed"])
        writer.writerow(["Detroit, MI", "PENDING", "0", "0", ""])
        writer.writerow(["Texas", "PENDING", "0", "0", ""])
        writer.writerow(["Miami, FL", "COMPLETED", "12", "10", "2026-11-09"])
    return str(csv_file)

def test_read_pending_locations(sample_csv):
    manager = SheetManager(csv_path=sample_csv)
    pending = manager.get_pending_locations()
    assert len(pending) == 2
    assert pending[0].raw_location == "Detroit, MI"
    assert pending[0].city == "Detroit"
    assert pending[1].raw_location == "Texas"

def test_update_location_status(sample_csv):
    manager = SheetManager(csv_path=sample_csv)
    manager.update_status(
        location="Detroit, MI",
        status="COMPLETED",
        leads_found=8,
        emails_sent=5
    )
    pending = manager.get_pending_locations()
    assert len(pending) == 1
    assert pending[0].raw_location == "Texas"

def test_add_new_location(sample_csv):
    manager = SheetManager(csv_path=sample_csv)
    manager.add_location("Florida")
    pending = manager.get_pending_locations()
    locations = [p.raw_location for p in pending]
    assert "Florida" in locations

def test_add_new_location_sanitizes_quotes_and_flags(sample_csv):
    manager = SheetManager(csv_path=sample_csv)
    manager.add_location('"Chicago"" --live')
    pending = manager.get_pending_locations()
    locations = [p.raw_location for p in pending]
    assert "Chicago" in locations
    assert '"Chicago"" --live' not in locations

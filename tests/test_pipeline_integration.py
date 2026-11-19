import pytest
import os
import csv
from src.pipeline import LeadAcquisitionPipeline
from src.db import LeadTrackerDB
from src.sheet_manager import SheetManager
from src.mailer import ColdEmailer

@pytest.fixture
def integration_env(tmp_path):
    csv_file = tmp_path / "locations.csv"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Location", "Status", "Leads_Found", "Emails_Sent", "Last_Processed"])
        writer.writerow(["Detroit, MI", "PENDING", "0", "0", ""])
        writer.writerow(["Texas", "PENDING", "0", "0", ""])

    db_file = tmp_path / "test_leads.db"
    pdf_report_file = tmp_path / "test_report.pdf"

    return {
        "csv_path": str(csv_file),
        "db_path": str(db_file),
        "pdf_path": str(pdf_report_file)
    }

def test_full_pipeline_end_to_end_execution(integration_env):
    pipeline = LeadAcquisitionPipeline(
        csv_path=integration_env["csv_path"],
        db_path=integration_env["db_path"],
        pdf_path=integration_env["pdf_path"],
        dry_run=True,
        max_daily_emails=20,
        sender_name="Hamzha",
        portfolio_url="https://hamzha.dev"
    )

    # 1. Run pipeline for pending locations
    metrics = pipeline.run()

    # 2. Verify metrics
    assert metrics.total_locations == 2
    assert metrics.total_scraped > 0
    assert metrics.total_filtered_no_website > 0
    assert metrics.total_emails_sent > 0
    assert metrics.total_duplicates_skipped == 0

    # 3. Verify Sheet was updated
    sheet_manager = SheetManager(csv_path=integration_env["csv_path"])
    pending = sheet_manager.get_pending_locations()
    assert len(pending) == 0  # Both locations processed and marked COMPLETED

    # 4. Verify DB has records and email content contains standard preview pitch and portfolio
    db = LeadTrackerDB(db_path=integration_env["db_path"])
    records = db.get_records_for_report()
    assert len(records) == metrics.total_emails_sent
    assert any(r.get("source") == "Facebook" for r in records)
    assert any(r.get("source") == "Reddit Intent" for r in records)
    assert any("Would you be open if I send over a quick sample website preview first?" in (r.get("email_content") or "") for r in records)
    assert any("https://hamzha.dev" in (r.get("email_content") or "") for r in records)

    # 5. Verify PDF Report was generated
    assert os.path.exists(integration_env["pdf_path"])
    assert os.path.getsize(integration_env["pdf_path"]) > 1000

    # 6. Test Deduplication on Second Run:
    # If the user adds the same location again:
    sheet_manager.add_location("Detroit, MI")
    second_metrics = pipeline.run()

    # Detroit leads were already contacted in run 1, so they must be detected as duplicates
    assert second_metrics.total_duplicates_skipped > 0

    # 7. Test Automated Follow-up Trigger
    followups_sent = pipeline.run_followups(days_threshold=0)
    assert followups_sent > 0

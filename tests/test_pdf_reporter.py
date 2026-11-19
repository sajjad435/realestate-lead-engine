import pytest
import os
from src.reporter import PDFReporter
from src.models import RunMetrics

def test_pdf_report_generation(tmp_path):
    output_pdf = tmp_path / "daily_lead_report.pdf"
    reporter = PDFReporter(output_path=str(output_pdf))

    metrics = RunMetrics(
        total_locations=2,
        total_scraped=20,
        total_filtered_no_website=10,
        total_emails_found=8,
        total_emails_sent=5,
        total_duplicates_skipped=3
    )

    sample_leads = [
        {
            "name": "Sarah Jenkins",
            "city": "Detroit",
            "state": "MI",
            "source": "Google Maps",
            "email": "sarah@realty.com",
            "status": "SENT",
            "email_content": "Subject: Quick question about Detroit listings\nHi Sarah, noticed your business doesn't have a website...",
            "contacted_at": "2026-11-10 10:00:00",
            "followup_due_date": "2026-11-13 10:00:00",
            "followup_status": "PENDING"
        },
        {
            "name": "David Miller",
            "city": "Dallas",
            "state": "TX",
            "source": "Instagram",
            "email": "david@dallashomes.com",
            "status": "SENT",
            "email_content": "Subject: Web portfolio for Dallas Realtor\nHi David, saw your great Instagram listings...",
            "contacted_at": "2026-11-10 10:05:00",
            "followup_due_date": "2026-11-13 10:05:00",
            "followup_status": "PENDING"
        }
    ]

    generated_path = reporter.generate(
        metrics=metrics,
        leads=sample_leads,
        cities=["Detroit, MI", "Texas"]
    )

    assert os.path.exists(generated_path)
    assert os.path.getsize(generated_path) > 1000  # PDF is populated

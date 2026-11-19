import os
import csv
import pytest
from unittest.mock import patch, MagicMock
from src.models import Lead
from src.social_dm_manager import SocialDMManager
from src.scrapers.instagram_finder import InstagramFinder
from src.scrapers.facebook_finder import FacebookFinder

def test_social_dm_manager_saves_lead_to_csv(tmp_path):
    csv_file = str(tmp_path / "test_social_dm_leads.csv")
    manager = SocialDMManager(csv_path=csv_file)

    lead = Lead(
        name="Cindy Charles Montreal Realtor",
        city="Montreal",
        website=None,
        email=None,
        source="Instagram",
        profile_url="https://instagram.com/cindycharlesrealtor",
        snippet="Passionate about Montreal homes. DM for info."
    )

    added = manager.record_social_lead(lead)
    assert added is True
    assert os.path.exists(csv_file)

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["Name"] == "Cindy Charles Montreal Realtor"
        assert reader[0]["Platform"] == "Instagram"
        assert reader[0]["City"] == "Montreal"
        assert reader[0]["Profile_URL"] == "https://instagram.com/cindycharlesrealtor"
        assert reader[0]["Status"] == "PENDING_MANUAL_DM"

def test_social_dm_manager_prevents_duplicate_profiles(tmp_path):
    csv_file = str(tmp_path / "test_social_dm_leads.csv")
    manager = SocialDMManager(csv_path=csv_file)

    lead = Lead(
        name="Olivier Couture",
        city="Montreal",
        website=None,
        email=None,
        source="Facebook",
        profile_url="https://www.facebook.com/oliviercouturecourtier/",
        snippet="Courtier chez Royal LePage Montreal"
    )

    first_add = manager.record_social_lead(lead)
    second_add = manager.record_social_lead(lead)
    assert first_add is True
    assert second_add is False

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1

def test_social_dm_manager_builds_digest_email_content():
    manager = SocialDMManager()
    leads = [
        Lead(
            name="Cindy Charles",
            city="Montreal",
            website=None,
            email=None,
            source="Instagram",
            profile_url="https://instagram.com/cindycharlesrealtor"
        ),
        Lead(
            name="Olivier Couture",
            city="Montreal",
            website=None,
            email=None,
            source="Facebook",
            profile_url="https://www.facebook.com/oliviercouturecourtier/"
        )
    ]
    subject, body = manager.build_digest_email_content(
        leads=leads,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )

    assert "Social DM Alert" in subject
    assert "Cindy Charles" in body
    assert "https://instagram.com/cindycharlesrealtor" in body
    assert "Olivier Couture" in body
    assert "https://www.facebook.com/oliviercouturecourtier/" in body
    assert "https://sajjad-wali-portfolio.vercel.app/" in body

def test_social_dm_manager_sends_digest_email_in_dry_run():
    manager = SocialDMManager()
    leads = [
        Lead(
            name="Cindy Charles",
            city="Montreal",
            website=None,
            email=None,
            source="Instagram",
            profile_url="https://instagram.com/cindycharlesrealtor"
        )
    ]
    success, msg = manager.send_digest_email(
        leads=leads,
        recipient_email="sajjadwali257@gmail.com",
        sender_email="sajjadwali257@gmail.com",
        sender_password="dummy_password",
        dry_run=True
    )
    assert success is True
    assert "[DRY-RUN]" in msg

@patch("src.social_dm_manager.smtplib.SMTP")
def test_social_dm_manager_sends_digest_email_via_smtp(mock_smtp):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    manager = SocialDMManager()
    leads = [
        Lead(
            name="Cindy Charles",
            city="Montreal",
            website=None,
            email=None,
            source="Instagram",
            profile_url="https://instagram.com/cindycharlesrealtor"
        )
    ]
    success, msg = manager.send_digest_email(
        leads=leads,
        recipient_email="sajjadwali257@gmail.com",
        sender_email="sajjadwali257@gmail.com",
        sender_password="app_password",
        dry_run=False
    )
    assert success is True
    assert mock_server.starttls.called
    assert mock_server.login.called
    assert mock_server.sendmail.called

@patch("src.scrapers.email_enricher.EmailEnricher.enrich_email")
def test_scrapers_collect_social_dm_leads_when_no_email_found(mock_enrich):
    mock_enrich.return_value = None  # Enrichment failed to find public email

    # Test Instagram
    insta_finder = InstagramFinder()
    insta_items = [
        {
            "title": "Cindy Charles Montreal Realtor (@cindycharlesrealtor) • Instagram",
            "href": "https://www.instagram.com/cindycharlesrealtor/",
            "snippet": "Passionate about Montreal homes. DM for info."
        }
    ]
    insta_leads = insta_finder.parse_search_items(insta_items, city="Montreal")
    assert len(insta_leads) == 0  # No email -> skipped for cold email pipeline
    assert len(insta_finder.social_dm_leads) == 1  # But collected for Social DM
    assert insta_finder.social_dm_leads[0].profile_url == "https://instagram.com/cindycharlesrealtor"

    # Test Facebook
    fb_finder = FacebookFinder()
    fb_items = [
        {
            "title": "Olivier Couture - Courtier immobilier Royal LePage | Facebook",
            "href": "https://www.facebook.com/oliviercouturecourtier/",
            "snippet": "Courtier immobilier chez Royal LePage Montreal. Call 514-555-0199."
        }
    ]
    fb_leads = fb_finder.parse_search_items(fb_items, city="Montreal")
    assert len(fb_leads) == 0
    assert len(fb_finder.social_dm_leads) == 1
    assert fb_finder.social_dm_leads[0].profile_url == "https://www.facebook.com/oliviercouturecourtier"

@patch("src.pipeline.ColdEmailer.send_report_email")
@patch("src.social_dm_manager.SocialDMManager.send_digest_email")
def test_pipeline_records_and_alerts_social_dm_leads(mock_send_digest, mock_report, tmp_path):
    from src.pipeline import LeadAcquisitionPipeline
    import csv

    csv_path = str(tmp_path / "locations.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Location", "Status", "Leads_Found", "Emails_Sent", "Last_Processed"])
        writer.writerow(["Montreal", "PENDING", 0, 0, ""])

    db_path = str(tmp_path / "test.db")
    pdf_path = str(tmp_path / "test.pdf")
    dm_csv = str(tmp_path / "social_dm_leads.csv")

    mock_send_digest.return_value = (True, "Digest sent")
    mock_report.return_value = (True, "Report sent")

    pipeline = LeadAcquisitionPipeline(
        csv_path=csv_path,
        db_path=db_path,
        pdf_path=pdf_path,
        dry_run=True,
        sender_email="sajjadwali257@gmail.com"
    )
    pipeline.social_dm_manager.csv_path = dm_csv

    # Simulate scrapers finding a social DM lead
    def mock_insta_search(loc):
        pipeline.insta_finder.social_dm_leads = [
            Lead(
                name="Cindy Charles",
                city="Montreal",
                website=None,
                email=None,
                source="Instagram",
                profile_url="https://instagram.com/cindycharlesrealtor"
            )
        ]
        return []
    pipeline.insta_finder.search_city = mock_insta_search

    pipeline.run(scan_inbound_intent=False)

    assert os.path.exists(dm_csv)
    with open(dm_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["Name"] == "Cindy Charles"
        assert rows[0]["Profile_URL"] == "https://instagram.com/cindycharlesrealtor"

    assert mock_send_digest.called


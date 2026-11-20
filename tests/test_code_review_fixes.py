import os
import pytest
from src.models import Lead, RunMetrics
from src.mailer import EmailTemplate
from src.reporter import PDFReporter
from src.config import AppConfig

def test_extract_salutation_name_preserves_international_accented_names():
    # Accented characters like ë, é, ç, etc. should NOT be butchered or truncated
    lead_michael = Lead(name="Michaël Marcotte", city="Montreal", email="m.marcotte@remax.com")
    assert EmailTemplate.extract_salutation_name(lead_michael) == "Michaël"

    lead_eric = Lead(name="Éric Bouchard", city="Montreal", email="eric.bouchard@remax.com")
    assert EmailTemplate.extract_salutation_name(lead_eric) == "Éric"

    lead_francois = Lead(name="François Dubois", city="Quebec", email="francois.dubois@remax.com")
    assert EmailTemplate.extract_salutation_name(lead_francois) == "François"

    lead_jose = Lead(name="José Martinez", city="Miami", email="jose.martinez@compass.com")
    assert EmailTemplate.extract_salutation_name(lead_jose) == "José"

def test_pdf_reporter_handles_emojis_and_unusual_unicode_without_crashing(tmp_path):
    pdf_file = tmp_path / "test_report_unicode.pdf"
    reporter = PDFReporter(output_path=str(pdf_file))
    
    metrics = RunMetrics(total_scraped=5, total_filtered_no_website=2, total_emails_sent=1, total_duplicates_skipped=0)
    # Exotic names with emojis, smart quotes, symbols, em-dashes
    leads = [
        {
            "name": "Steph | REALTOR® 🌴 🏡",
            "city": "Montréal 🇨🇦",
            "source": "Instagram 📸",
            "profile_url": "https://instagram.com/steph",
            "email": "steph@gmail.com",
            "status": "SENT",
            "followup_due_date": "2026-11-23",
            "email_content": "Subject: Hi Steph — let’s connect! 🚀\n\nFull body with emoji 🏡 and smart quotes ‘test’."
        }
    ]
    cities = ["Montréal 🇨🇦", "Miami ☀️"]
    
    # Must NOT throw FPDFUnicodeEncodingException
    generated_path = reporter.generate(metrics=metrics, leads=leads, cities=cities)
    assert os.path.exists(generated_path)
    assert os.path.getsize(generated_path) > 500

def test_city_sanitization_strips_cli_flags_in_outreach():
    lead = Lead(name="Eunique Realtor", city='Chicago" --live', email="eunique@gmail.com")
    clean_city = EmailTemplate.clean_city_name(lead.city)
    assert clean_city == "Chicago"
    
    subject, body = EmailTemplate.render(lead, sender_name="Sajjad Wali")
    assert '--live' not in subject
    assert '"' not in subject
    assert '--live' not in body

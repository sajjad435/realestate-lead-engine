import pytest
from unittest.mock import patch, MagicMock
from src.scrapers.email_enricher import EmailEnricher
from src.scrapers.instagram_finder import InstagramFinder
from src.scrapers.facebook_finder import FacebookFinder
from src.models import Lead

def test_email_enricher_extracts_email_matching_agent_name():
    enricher = EmailEnricher()
    mock_search_body = """
    Philippe Daunais - Courtier Immobilier Résidentiel Montreal
    Bureau: Royal LePage Heritage. Courriel: philippe.daunais@gmail.com
    Téléphone: 514-555-0199
    """
    found_email = enricher.extract_matching_email(
        text=mock_search_body,
        agent_name="Philippe Daunais"
    )
    assert found_email == "philippe.daunais@gmail.com"

def test_email_enricher_rejects_platform_and_system_emails():
    enricher = EmailEnricher()
    bad_text = "Follow us on Instagram: support@instagram.com or help@google.com or test.png"
    found_email = enricher.extract_matching_email(
        text=bad_text,
        agent_name="Philippe Daunais"
    )
    assert found_email is None

@patch("src.scrapers.email_enricher.requests.get")
def test_email_enricher_queries_web_and_returns_email(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <html>
      <body>
        <div class="result__snippet">
          Contact Liza Gédéon Lévêque, Montreal REALTOR at liza.gedeon@gmail.com
        </div>
      </body>
    </html>
    """
    mock_get.return_value = mock_resp

    enricher = EmailEnricher()
    email = enricher.enrich_email(
        name="Liza Gédéon Lévêque",
        city="Montreal"
    )
    assert email == "liza.gedeon@gmail.com"

@patch("src.scrapers.email_enricher.EmailEnricher.enrich_email")
def test_instagram_finder_enriches_lead_when_no_email_in_bio(mock_enrich):
    mock_enrich.return_value = "cindy.charles@gmail.com"

    finder = InstagramFinder()
    items = [
        {
            "title": "Cindy Charles Montreal Realtor (@cindycharlesrealtor) • Instagram",
            "href": "https://www.instagram.com/cindycharlesrealtor/",
            "snippet": "Passionate about Montreal homes. DM for info." # No email, no website in bio
        }
    ]
    leads = finder.parse_search_items(items, city="Montreal")
    assert len(leads) == 1
    assert leads[0].email == "cindy.charles@gmail.com"
    assert leads[0].website is None

@patch("src.scrapers.email_enricher.EmailEnricher.enrich_email")
def test_facebook_finder_enriches_lead_when_no_email_in_page(mock_enrich):
    mock_enrich.return_value = "olivier.couture@royallepage.ca"

    finder = FacebookFinder()
    items = [
        {
            "title": "Olivier Couture - Courtier immobilier Royal LePage | Facebook",
            "href": "https://www.facebook.com/oliviercouturecourtier/",
            "snippet": "Courtier immobilier chez Royal LePage Montreal. Call 514-555-0199." # No email in snippet
        }
    ]
    leads = finder.parse_search_items(items, city="Montreal")
    assert len(leads) == 1
    assert leads[0].email == "olivier.couture@royallepage.ca"
    assert leads[0].website is None

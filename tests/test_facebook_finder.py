import pytest
from src.scrapers.facebook_finder import FacebookFinder
from src.models import LocationInput
from src.ai_verifier import AIAnalysisResult

def test_facebook_finder_builds_search_queries():
    finder = FacebookFinder()
    queries = finder.build_search_queries("Raleigh")
    assert any("site:facebook.com" in q for q in queries)
    assert any("realtor" in q for q in queries)
    assert any("real estate" in q for q in queries)
    assert len(queries) >= 3

def test_facebook_finder_builds_search_queries_for_indian_cities():
    finder = FacebookFinder()
    queries = finder.build_search_queries("Patna")
    assert any("property dealer" in q for q in queries)

def test_facebook_finder_validates_page_slugs():
    finder = FacebookFinder()
    assert finder.is_valid_facebook_page_slug("login") is False
    assert finder.is_valid_facebook_page_slug("events") is False
    assert finder.is_valid_facebook_page_slug("groups") is False
    assert finder.is_valid_facebook_page_slug("help") is False
    assert finder.is_valid_facebook_page_slug("watch") is False
    assert finder.is_valid_facebook_page_slug("marketplace") is False
    assert finder.is_valid_facebook_page_slug("apexrealtypatna") is True
    assert finder.is_valid_facebook_page_slug("raleighcustomhomes") is True

def test_facebook_finder_extracts_realtors_without_website():
    finder = FacebookFinder()
    raw_items = [
        {
            "title": "Carolina Blue Realty - Home | Facebook",
            "href": "https://www.facebook.com/carolinabluerealty/",
            "snippet": "Carolina Blue Realty. Real Estate Service in Raleigh, NC. Contact: carolinablue.realty@gmail.com"
        }
    ]
    leads = finder.parse_search_items(raw_items, city="Raleigh", state="NC")
    assert len(leads) == 1
    assert leads[0].name == "Carolina Blue Realty"
    assert leads[0].email == "carolinablue.realty@gmail.com"
    assert leads[0].website is None
    assert leads[0].source == "Facebook"

def test_facebook_finder_skips_pages_with_existing_website():
    finder = FacebookFinder()
    raw_items = [
        {
            "title": "Oak City Estates - Real Estate Agency | Facebook",
            "href": "https://www.facebook.com/oakcityestates/",
            "snippet": "Premier Raleigh agents. Visit our listings at https://oakcityestates.com. Email: contact@oakcityestates.com"
        }
    ]
    leads = finder.parse_search_items(raw_items, city="Raleigh", state="NC")
    assert len(leads) == 1
    assert leads[0].website == "https://oakcityestates.com"

def test_facebook_finder_detects_website_from_email_custom_domain(monkeypatch):
    from src.filter import LeadFilter
    finder = FacebookFinder()
    monkeypatch.setattr(
        LeadFilter,
        "check_custom_domain_website",
        lambda email: "https://raleighcustomrealty.com" if "raleighcustomrealty.com" in email else None
    )
    raw_items = [
        {
            "title": "Triangle Property Advisors | Facebook",
            "href": "https://www.facebook.com/triangleprops/",
            "snippet": "Reach out to us: sales@raleighcustomrealty.com"
        }
    ]
    leads = finder.parse_search_items(raw_items, city="Raleigh", state="NC")
    assert len(leads) == 1
    assert leads[0].website == "https://raleighcustomrealty.com"

def test_facebook_finder_integrates_with_gemini_verifier():
    finder = FacebookFinder(gemini_api_key="test-key")
    finder.ai_verifier.analyze_lead = lambda **kwargs: AIAnalysisResult(
        has_website=False,
        official_website_url=None,
        verified_email="verified.realtor@gmail.com",
        reasoning="Solo realtor with no dedicated agency website."
    )
    raw_items = [
        {
            "title": "Patna Property Guru | Facebook",
            "href": "https://www.facebook.com/patnapropertyguru/",
            "snippet": "Trusted property advisory in Kadamkuan, Patna."
        }
    ]
    leads = finder.parse_search_items(raw_items, city="Patna", state="BR")
    assert len(leads) == 1
    assert leads[0].email == "verified.realtor@gmail.com"
    assert leads[0].website is None

def test_facebook_finder_test_mode_returns_mock_leads():
    finder = FacebookFinder(test_mode=True)
    loc = LocationInput(raw_location="Raleigh, NC")
    leads = finder.search_city(loc)
    assert len(leads) > 0
    assert any(lead.source == "Facebook" for lead in leads)

def test_facebook_finder_builds_paginated_google_search_urls():
    finder = FacebookFinder()
    urls = finder.build_paginated_google_urls('site:facebook.com "Raleigh" realtor', max_pages=3)
    assert len(urls) == 3
    assert "start=0" in urls[0] or "q=" in urls[0]
    assert "start=10" in urls[1]
    assert "start=20" in urls[2]

def test_facebook_finder_resolves_linktree_with_official_website(monkeypatch):
    from src.scrapers.bio_link_resolver import BioLinkResolver
    monkeypatch.setattr(
        BioLinkResolver,
        "resolve",
        lambda self, url: {
            "has_website": True,
            "website_url": "https://www.carolinabluerealty.com",
            "email": None,
            "destination_links": ["https://www.carolinabluerealty.com"]
        }
    )
    finder = FacebookFinder()
    raw_items = [
        {
            "title": "Carolina Blue Realty | Facebook",
            "href": "https://www.facebook.com/carolinablue/",
            "snippet": "Contact: info@gmail.com | View our links: linktr.ee/carolinablue"
        }
    ]
    leads = finder.parse_search_items(raw_items, city="Raleigh", state="NC")
    assert len(leads) == 1
    assert leads[0].website == "https://www.carolinabluerealty.com"


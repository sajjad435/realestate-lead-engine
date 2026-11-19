import pytest
from src.scrapers.intent_finder import IntentFinder
from src.models import LocationInput, Lead
from src.ai_verifier import AIAnalysisResult

def test_intent_finder_builds_search_queries():
    finder = IntentFinder()
    queries = finder.build_search_queries()
    assert any("site:reddit.com/r/realtors" in q for q in queries)
    assert any("need a website" in q or "looking for" in q for q in queries)
    assert len(queries) >= 3

def test_intent_finder_filters_service_providers_vs_actual_clients():
    finder = IntentFinder()
    # 1. Provider pitch (should be rejected)
    provider_post = {
        "title": "We build luxury websites for top producing real estate agents",
        "href": "https://reddit.com/r/realtors/comments/111",
        "snippet": "Contact our agency at info@webagency.com to get your IDX site."
    }
    assert finder.is_realtor_buyer_intent(provider_post["title"], provider_post["snippet"]) is False

    # 2. Genuine realtor asking for a website (should be accepted)
    client_post = {
        "title": "New solo agent in Dallas looking for someone to build a clean portfolio website",
        "href": "https://reddit.com/r/realtors/comments/222",
        "snippet": "I recently passed my exam and need a website for my buyer leads. Email me at dallas.agent@gmail.com"
    }
    assert finder.is_realtor_buyer_intent(client_post["title"], client_post["snippet"]) is True

def test_intent_finder_parses_search_items_with_email():
    finder = IntentFinder()
    items = [
        {
            "title": "Looking for web designer for my new realty business : r/realtors",
            "href": "https://reddit.com/r/realtors/comments/abc123/looking_for_web_designer/",
            "snippet": "Hey everyone, I need a modern website built for my listings in Raleigh. Contact: raleigh.realtor.alex@gmail.com"
        }
    ]
    leads = finder.parse_search_items(items)
    assert len(leads) == 1
    assert leads[0].email == "raleigh.realtor.alex@gmail.com"
    assert leads[0].source == "Reddit Intent"
    assert "reddit.com" in leads[0].profile_url
    assert leads[0].website is None

def test_intent_finder_integrates_with_gemini_verifier():
    finder = IntentFinder(gemini_api_key="test-key")
    finder.ai_verifier.analyze_lead = lambda **kwargs: AIAnalysisResult(
        has_website=False,
        official_website_url=None,
        verified_email="chicago.broker@gmail.com",
        reasoning="Realtor explicitly posted asking for a website builder."
    )
    items = [
        {
            "title": "Need a simple clean website for my real estate clients",
            "href": "https://reddit.com/r/realtors/comments/xyz789/",
            "snippet": "Looking for recommendations or someone to hire."
        }
    ]
    leads = finder.parse_search_items(items)
    assert len(leads) == 1
    assert leads[0].email == "chicago.broker@gmail.com"
    assert leads[0].source == "Reddit Intent"

def test_intent_finder_test_mode_returns_mock_leads():
    finder = IntentFinder(test_mode=True)
    leads = finder.search_intent()
    assert len(leads) > 0
    assert any(lead.source == "Reddit Intent" for lead in leads)

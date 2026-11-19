import pytest
from src.models import Lead
from src.filter import LeadFilter

def test_filter_accepts_lead_without_website_and_valid_email():
    lead = Lead(
        name="Sarah Connor",
        city="Detroit",
        email="sarah@realty.com",
        website=None,
        source="Google Maps"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is True
    assert reason == "QUALIFIED"

def test_filter_accepts_mx_only_business_email_without_website():
    # Achyuta Realtor has email info@achyutaenterprises.in which has valid MX records but no A record
    lead = Lead(
        name="Achyuta Realtor",
        city="Lucknow",
        email="info@achyutaenterprises.in",
        website=None,
        source="Instagram"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is True
    assert reason == "QUALIFIED"


def test_filter_rejects_lead_with_website():
    lead = Lead(
        name="Bruce Wayne",
        city="Detroit",
        email="bruce@wayneestates.com",
        website="https://wayneestates.com",
        source="Google Maps"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is False
    assert reason == "HAS_WEBSITE"

def test_filter_rejects_lead_with_social_linktree_as_website_check():
    # If website field is empty string or None, it should qualify
    lead = Lead(
        name="Empty Web Agent",
        city="Miami",
        email="agent@miami.com",
        website="",
        source="Instagram"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is True

def test_filter_rejects_lead_without_valid_email():
    lead = Lead(
        name="No Email Agent",
        city="Texas",
        email=None,
        website=None,
        source="Google Maps"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is False
    assert reason == "NO_VALID_EMAIL"

def test_filter_treats_social_and_portal_directories_as_no_website():
    # If lead links to their TikTok, Realtor.com directory, or Centris, they DO NOT have a private agency website!
    lead_tiktok = Lead(
        name="Gautam Walia",
        city="Montreal",
        email="gautam@gmail.com",
        website="https://www.tiktok.com/@gautamwalia",
        source="Instagram"
    )
    is_valid_tt, _ = LeadFilter.evaluate(lead_tiktok)
    assert is_valid_tt is True

    lead_realtor_portal = Lead(
        name="Monty Bhagirath",
        city="Montreal",
        email="monty.bhagirath@gmail.com",
        website="https://realtor.com/realestateagents/monty",
        source="Instagram"
    )
    is_valid_portal, _ = LeadFilter.evaluate(lead_realtor_portal)
    assert is_valid_portal is True


def test_filter_rejects_invalid_email_format():
    lead = Lead(
        name="Bad Email Agent",
        city="Texas",
        email="notanemail",
        website=None,
        source="Google Maps"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is False
    assert reason == "NO_VALID_EMAIL"

def test_filter_rejects_non_existent_domain_email():
    lead = Lead(
        name="Non Existent Domain Agent",
        city="LA",
        email="realtor@losangelisprime.com",
        website=None,
        source="Google Maps"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is False
    assert reason == "DOMAIN_NOT_RESOLVABLE"

def test_filter_checks_custom_email_domain_for_live_website():
    # If agent has a business email like hello@renaudhomegroup.com, their domain hosts a website!
    lead = Lead(
        name="Renaud Home Group",
        city="Irvine",
        email="hello@renaudhomegroup.com",
        website=None, # Scraper didn't catch it initially, but filter should catch custom domain website
        source="Instagram"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is False
    assert reason == "HAS_WEBSITE"
    assert lead.website is not None
    assert "renaudhomegroup.com" in lead.website

def test_filter_allows_free_email_providers_without_website():
    # Free email like gmail.com has no personal agency website
    lead = Lead(
        name="John Real Estate",
        city="Irvine",
        email="john.realestate.agent123@gmail.com",
        website=None,
        source="Instagram"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is True
    assert reason == "QUALIFIED"

def test_filter_accepts_mx_only_business_email_without_website():
    # Achyuta Realtor has email info@achyutaenterprises.in which has valid MX records but no A record
    lead = Lead(
        name="Achyuta Realtor",
        city="Lucknow",
        email="info@achyutaenterprises.in",
        website=None,
        source="Instagram"
    )
    is_valid, reason = LeadFilter.evaluate(lead)
    assert is_valid is True
    assert reason == "QUALIFIED"


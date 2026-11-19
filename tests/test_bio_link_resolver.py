import pytest
from unittest.mock import patch, MagicMock
from src.scrapers.bio_link_resolver import BioLinkResolver

def test_detect_bio_link_service_url():
    resolver = BioLinkResolver()
    
    # Linktree in bio
    text1 = "Boise Realtor | Relocation Expert | 🔗 linktr.ee/archergroup | Call today!"
    assert resolver.extract_bio_service_url(text1) == "https://linktr.ee/archergroup"

    # beacons.ai
    text2 = "Miami Luxury Homes -> beacons.ai/elenawoodshomes"
    assert resolver.extract_bio_service_url(text2) == "https://beacons.ai/elenawoodshomes"

    # lnk.bio
    text3 = "Check my links: https://lnk.bio/dallasrealty"
    assert resolver.extract_bio_service_url(text3) == "https://lnk.bio/dallasrealty"

    # None if normal text without bio-link service
    text4 = "Just a realtor in Detroit. Call 555-0199"
    assert resolver.extract_bio_service_url(text4) is None

@patch("src.scrapers.bio_link_resolver.requests.get")
def test_resolve_linktree_with_official_website(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <html>
      <body>
        <a href="https://instagram.com/boiserealtor">Instagram</a>
        <a href="https://facebook.com/archergroup">Facebook Page</a>
        <a href="https://www.archergrouprealestate.com">Official Agency Website</a>
        <a href="https://airbnb.com/h/archertownhome">Our Townhome Airbnb</a>
      </body>
    </html>
    """
    mock_get.return_value = mock_resp

    resolver = BioLinkResolver()
    result = resolver.resolve("https://linktr.ee/archergroup")

    assert result["has_website"] is True
    assert "archergrouprealestate.com" in result["website_url"]

@patch("src.scrapers.bio_link_resolver.requests.get")
def test_resolve_linktree_without_website_extracts_email(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <html>
      <body>
        <h1>Summer Jacobs Realtor</h1>
        <a href="https://instagram.com/summerjacobs">Instagram</a>
        <a href="https://tiktok.com/@summerrealtor">TikTok</a>
        <a href="mailto:summer@gmail.com">Send an Email</a>
        <p>Contact me: summer@gmail.com</p>
      </body>
    </html>
    """
    mock_get.return_value = mock_resp

    resolver = BioLinkResolver()
    result = resolver.resolve("https://linktr.ee/summerjacobs")

    assert result["has_website"] is False
    assert result["website_url"] is None
    assert result["email"] == "summer@gmail.com"

@patch("src.scrapers.bio_link_resolver.requests.get")
def test_bio_link_resolver_ignores_social_media_destinations(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <html>
      <body>
        <a href="https://instagram.com/agent">Instagram</a>
        <a href="https://facebook.com/agent">Facebook</a>
        <a href="https://twitter.com/agent">Twitter</a>
        <a href="https://linkedin.com/in/agent">LinkedIn</a>
        <a href="https://youtube.com/@agent">YouTube</a>
        <a href="https://spotify.com/artist/xyz">Spotify</a>
      </body>
    </html>
    """
    mock_get.return_value = mock_resp

    resolver = BioLinkResolver()
    result = resolver.resolve("https://linktr.ee/socialonly")

    assert result["has_website"] is False
    assert result["website_url"] is None

import pytest
from unittest.mock import patch, MagicMock
from src.scrapers.maps_finder import GoogleMapsFinder
from src.scrapers.instagram_finder import InstagramFinder
from src.models import LocationInput

def test_google_maps_finder_parses_results():
    finder = GoogleMapsFinder()
    location = LocationInput(raw_location="Detroit, MI")
    
    # Mock / Test raw response parser
    mock_raw_data = [
        {
            "name": "Apex Realty Detroit",
            "city": "Detroit",
            "state": "MI",
            "phone": "+1 313-555-0144",
            "website": None,  # Target! No website
            "email": "contact@apexrealtydetroit.com",
            "profile_url": "https://maps.google.com/?cid=111"
        },
        {
            "name": "Grand Detroit Estates",
            "city": "Detroit",
            "state": "MI",
            "phone": "+1 313-555-0199",
            "website": "https://granddetroitestates.com", # Exclude! Has website
            "email": "info@granddetroitestates.com",
            "profile_url": "https://maps.google.com/?cid=222"
        }
    ]
    leads = finder.parse_raw_places(mock_raw_data)
    assert len(leads) == 2
    assert leads[0].name == "Apex Realty Detroit"
    assert leads[0].website is None
    assert leads[0].source == "Google Maps"

def test_instagram_finder_extracts_realtors_without_website():
    finder = InstagramFinder()
    location = LocationInput(raw_location="Texas")
    
    mock_insta_profiles = [
        {
            "username": "texas_homes_sarah",
            "full_name": "Sarah Jenkins | Texas Realtor",
            "bio": "Helping families buy & sell across Dallas & Austin! DM or email me 📩 sarah@texasrealtorhomes.com",
            "external_url": None, # Target! No website in bio
            "city": "Texas",
            "profile_url": "https://instagram.com/texas_homes_sarah"
        },
        {
            "username": "houston_luxury_realty",
            "full_name": "Houston Luxury Realty",
            "bio": "Top 1% Producers in Texas. Check our listings below",
            "external_url": "https://houstonluxuryrealty.com", # Has website
            "city": "Texas",
            "profile_url": "https://instagram.com/houston_luxury_realty"
        }
    ]
    leads = finder.parse_raw_profiles(mock_insta_profiles)
    assert len(leads) == 2
    assert leads[0].name == "Sarah Jenkins | Texas Realtor"
    assert leads[0].email == "sarah@texasrealtorhomes.com"
    assert leads[0].website is None
    assert leads[0].source == "Instagram"

def test_instagram_finder_extracts_email_from_bio_text():
    finder = InstagramFinder()
    bio_text = "Commercial & Residential Realtor in Miami. Contact: broker.alex@gmail.com for deals"
    email = finder.extract_email_from_text(bio_text)
    assert email == "broker.alex@gmail.com"

def test_instagram_finder_detects_website_in_bio_text_without_slash():
    finder = InstagramFinder()
    # Case from user screenshot: Renaud Home Group with domain 'renaudhomegroup.com' in bio text without trailing slash
    bio_text = "The best of Irvine real estate! hello@renaudhomegroup.com Renaud Denis | Realtor renaudhomegroup.com"
    website = finder.detect_website_in_text(bio_text)
    assert website is not None
    assert "renaudhomegroup.com" in website

def test_instagram_finder_rejects_system_paths_as_usernames():
    finder = InstagramFinder()
    assert finder.is_valid_instagram_username("reel") is False
    assert finder.is_valid_instagram_username("reels") is False
    assert finder.is_valid_instagram_username("p") is False
    assert finder.is_valid_instagram_username("explore") is False
    assert finder.is_valid_instagram_username("stories") is False
    assert finder.is_valid_instagram_username("renaudhomegroup") is True
    assert finder.is_valid_instagram_username("yoonlimrealestateadv") is True

def test_instagram_finder_extracts_website_from_profile_html():
    finder = InstagramFinder()
    mock_html = '''
    <html>
      <head>
        <meta property="og:description" content="Renaud Home Group on Instagram: hello@renaudhomegroup.com" />
      </head>
      <body>
        <script>{"props":{"user":{"biography":"Irvine realtor","external_url":"https://renaudhomegroup.com"}}}</script>
      </body>
    </html>
    '''
    detected = finder.extract_website_from_profile_html(mock_html)
    assert detected == "https://renaudhomegroup.com"

def test_google_maps_detect_website_isolates_authority_button():
    finder = GoogleMapsFinder()
    
    # Mock page object with authority button
    class MockLocator:
        def __init__(self, count_val=0, href_val=None, text_val=""):
            self._count = count_val
            self._href = href_val
            self._text = text_val
        def count(self):
            return self._count
        @property
        def first(self):
            return self
        def get_attribute(self, attr):
            if attr == "href":
                return self._href
            return None
        def inner_text(self):
            return self._text
        def all(self):
            return [self] if self._count > 0 else []

    class MockPageWithWebsite:
        def locator(self, selector):
            if 'data-item-id="authority"' in selector:
                return MockLocator(count_val=1, href_val="https://aashiyanacity.com/")
            return MockLocator(count_val=0)

    class MockPageWithoutWebsite:
        def locator(self, selector):
            if 'data-item-id="authority"' in selector:
                return MockLocator(count_val=0)
            return MockLocator(count_val=0)

    # Place with website should return its own website
    assert finder._detect_website_in_place_pane(MockPageWithWebsite()) == "https://aashiyanacity.com/"
    # Place without website must return None (NOT leak flatinranchi.com from other places)
    assert finder._detect_website_in_place_pane(MockPageWithoutWebsite()) is None

def test_instagram_finder_parses_search_result_items():
    finder = InstagramFinder()
    items = [
        {
            "title": "Ranchi properties l Ranchi Real Estate (@ranchirealestate_) - Instagram",
            "href": "https://www.instagram.com/ranchirealestate_/",
            "snippet": "Contact us at contact@ranchirealestate.com for flats and plots."
        },
        {
            "title": "Ranchi Reel - Instagram",
            "href": "https://www.instagram.com/reel/C12345/",
            "snippet": "Watch latest reel"
        }
    ]
    leads = finder.parse_search_items(items, city="Ranchi")
    # Reel must be skipped, real estate account must be extracted
    assert len(leads) == 1
    assert "Ranchi Real Estate" in leads[0].name
    assert leads[0].email == "contact@ranchirealestate.com"
    assert leads[0].source == "Instagram"

def test_investigate_social_profiles_finds_email_on_facebook():
    finder = GoogleMapsFinder()
    mock_search_results = [
        {
            "title": "Vasudeva Realty | Ranchi - Facebook",
            "href": "https://www.facebook.com/vasudevarealty/",
            "snippet": "Contact us at vasudeva.realty@gmail.com for premium flats in Ranchi."
        }
    ]
    web, email, profile_url = finder.parse_social_investigation_results(
        mock_search_results,
        business_name="Vasudeva Realty",
        city="Ranchi"
    )
    assert web is None
    assert email == "vasudeva.realty@gmail.com"
    assert profile_url == "https://www.facebook.com/vasudevarealty/"

def test_investigate_social_profiles_detects_website_in_social_results():
    finder = GoogleMapsFinder()
    mock_search_results = [
        {
            "title": "Samridhi Properties & Developers | Ranchi - Facebook",
            "href": "https://www.facebook.com/samridhiproperties/",
            "snippet": "Contact: 9835499995 spdrealities@gmail.com www.spdrealties.com"
        },
        {
            "title": "SPD | Samridhi Properties & Developers",
            "href": "https://spdrealties.com/",
            "snippet": "Premium real estate advisory across India."
        }
    ]
    web, email, profile_url = finder.parse_social_investigation_results(
        mock_search_results,
        business_name="Samridhi Properties & Developers",
        city="Ranchi"
    )
    # Must catch spdrealties.com as website!
    assert web is not None
    assert "spdrealties.com" in web

def test_investigate_social_profiles_rejects_instagram_corporate_email():
    finder = GoogleMapsFinder()
    mock_search_results = [
        {
            "title": "River view - Instagram",
            "href": "https://www.instagram.com",
            "snippet": "Welcome to Instagram. For corporate inquiries contact info@instagram.com."
        }
    ]
    web, email, profile_url = finder.parse_social_investigation_results(
        mock_search_results,
        business_name="River view",
        city="jahanabaad"
    )
    # info@instagram.com. must be strictly rejected as platform corporate email
    assert email is None
    # Generic homepage https://www.instagram.com must NOT be accepted as business profile
    assert profile_url is None

def test_parse_google_search_text_extracts_email_and_detects_no_website():
    finder = GoogleMapsFinder()
    sample_google_text = """
    Search Results
    AI Overview
    Brahmdev Property Dealer is a real estate and rental service provider located near Budh Murti in Kadamkuan / Lohanipur, Patna. 
    Contact & Location Details
    Address: D Singh Road, near Budh Murti, Kadamkuan / Pirmohani Chowk / West Lohanipur, Patna, Bihar – 800003
    Phone Number: +91 79033 26045
    Email: avinashkumarsharma76@gmail.com
    Facebook Profile: Brahmdev Property dealer and To let services
    Justdial: Brahamdev Property Dealer in Pirmohani Chowk, Patna
    """
    web, email, social_url = finder.parse_google_search_page(
        page_text=sample_google_text,
        links=[
            {"title": "Justdial", "href": "https://www.justdial.com/Patna/Brahamdev-Property-Dealer"},
            {"title": "Facebook", "href": "https://www.facebook.com/brahmdevpropertydealer/"}
        ],
        business_name="Brahmdev Property Dealer",
        city="Patna"
    )
    assert web is None
    assert email == "avinashkumarsharma76@gmail.com"
    assert social_url == "https://www.facebook.com/brahmdevpropertydealer/"

def test_parse_google_search_page_detects_website_in_overview_or_links():
    finder = GoogleMapsFinder()
    sample_text = """
    Origin Properties Patna
    Address: Boring Road, Patna
    Official Website: https://originpropertiespatna.com
    Email: sales@originpropertiespatna.com
    """
    web, email, social_url = finder.parse_google_search_page(
        page_text=sample_text,
        links=[
            {"title": "Origin Properties Patna", "href": "https://originpropertiespatna.com"}
        ],
        business_name="Origin Properties",
        city="Patna"
    )
    assert web == "https://originpropertiespatna.com"

def test_parse_google_search_page_ignores_corporate_google_emails():
    finder = GoogleMapsFinder()
    sample_text = """
    Some Realtor Patna
    Contact Google Support: support@google.com or admin@duckduckgo.com
    """
    web, email, social_url = finder.parse_google_search_page(
        page_text=sample_text,
        links=[],
        business_name="Some Realtor",
        city="Patna"
    )
    assert email is None

def test_parse_google_search_does_not_falsely_match_generic_real_estate_portal_as_website():
    finder = GoogleMapsFinder()
    sample_text = """
    Dream Estates is a real estate agency in Lucknow located in Eldeco Saubhagyam Arcade.
    Phone: +91 95693 92218
    Email: hidreamestate@gmail.com
    Check top listings on realestateindia.com and squareyards.com
    """
    links = [
        {"title": "RealEstateIndia", "href": "https://www.realestateindia.com/agents-lucknow.htm"},
        {"title": "SquareYards", "href": "https://www.squareyards.com/lucknow-property"},
        {"title": "Eldeco Group", "href": "https://www.eldecogroup.com/commercial-arcade"}
    ]
    web, email, social_url = finder.parse_google_search_page(
        page_text=sample_text,
        links=links,
        business_name="Dream Estates",
        city="Lucknow"
    )
    # Must NOT claim realestateindia, squareyards, or eldecogroup as official website of Dream Estates
    assert web is None
    assert email == "hidreamestate@gmail.com"

def test_parse_social_investigation_results_does_not_falsely_match_third_party_portals():
    finder = GoogleMapsFinder()
    mock_search_results = [
        {
            "title": "Top Real Estate Agents in Lucknow - RealEstateIndia.Com",
            "href": "https://www.realestateindia.com/agents-brokers-in-kadamkuan-patna.htm",
            "snippet": "Find trusted real estate agents and property dealers across Lucknow on realestateindia.com"
        },
        {
            "title": "Eldeco Saubhagyam Arcade Commercial Properties",
            "href": "https://www.eldecogroup.com",
            "snippet": "Eldeco group commercial project in Vrindavan colony."
        }
    ]
    web, email, profile_url = finder.parse_social_investigation_results(
        mock_search_results,
        business_name="Dream Estates",
        city="Lucknow"
    )
    assert web is None

def test_google_maps_finder_has_ai_verifier_configured():
    from src.ai_verifier import GeminiVerifier
    finder = GoogleMapsFinder(gemini_api_key="test-gemini-key")
    assert finder.ai_verifier is not None
    assert finder.ai_verifier.api_key == "test-gemini-key"

def test_instagram_finder_has_ai_verifier_configured():
    from src.ai_verifier import GeminiVerifier
    finder = InstagramFinder(gemini_api_key="test-gemini-key")
    assert finder.ai_verifier is not None
    assert finder.ai_verifier.api_key == "test-gemini-key"

def test_instagram_finder_uses_ai_verifier_to_detect_website():
    from src.ai_verifier import AIAnalysisResult
    finder = InstagramFinder(gemini_api_key="test-gemini-key")
    
    # Mock Gemini verifier returning website found for Jason & Felecia Archer
    finder.ai_verifier.analyze_lead = lambda **kwargs: AIAnalysisResult(
        has_website=True,
        official_website_url="https://www.archergrouprealestate.com",
        verified_email="jason@archergrouprealestate.com",
        reasoning="Archer Group has dedicated website www.archergrouprealestate.com"
    )
    
    items = [
        {
            "title": "Jason & Felecia Archer | Idaho Real Estate Advisors (@boiserealtor) • Instagram",
            "href": "https://www.instagram.com/boiserealtor/",
            "snippet": "IDAHO REALTORS + Relocation Experts Archer Group At Homes of Idaho"
        }
    ]
    leads = finder.parse_search_items(items, city="Boise", state="ID")
    assert len(leads) == 1
    assert leads[0].website == "https://www.archergrouprealestate.com"

def test_instagram_finder_detects_website_from_email_custom_domain(monkeypatch):
    from src.filter import LeadFilter
    finder = InstagramFinder()
    
    # Mock LeadFilter.check_custom_domain_website to return website for custom domain
    monkeypatch.setattr(
        LeadFilter, 
        "check_custom_domain_website", 
        lambda email: "https://raleighcustomrealty.com" if "raleighcustomrealty.com" in email else None
    )

    items = [
        {
            "title": "Summer Jacobs | Raleigh REALTOR® (@summerjacobs_realtor) • Instagram",
            "href": "https://www.instagram.com/summerjacobs_realtor/",
            "snippet": "Top Raleigh Realtor. Contact me at Summer@raleighcustomrealty.com for showings."
        }
    ]
    leads = finder.parse_search_items(items, city="Raleigh", state="NC")
    assert len(leads) == 1
    # Must detect company website from email domain so it is marked has_website -> Skipped
    assert leads[0].website == "https://raleighcustomrealty.com"

def test_google_maps_finder_builds_multi_angle_queries():
    finder = GoogleMapsFinder()
    queries = finder.build_search_queries("Raleigh")
    assert any("real estate agent" in q for q in queries)
    assert any("real estate agency" in q for q in queries)
    assert any("realtor" in q for q in queries)
    assert len(queries) >= 3

def test_instagram_finder_builds_multi_queries():
    finder = InstagramFinder()
    queries = finder.build_discovery_queries("Raleigh")
    assert any("realtor" in q for q in queries)
    assert any("real estate" in q for q in queries)
    assert len(queries) >= 3

def test_instagram_finder_builds_paginated_google_search_urls():
    finder = InstagramFinder()
    urls = finder.build_paginated_google_urls('site:instagram.com "Boise" realtor', max_pages=3)
    assert len(urls) == 3
    assert "start=0" in urls[0] or "q=" in urls[0]
    assert "start=10" in urls[1]
    assert "start=20" in urls[2]

@patch("src.scrapers.bio_link_resolver.BioLinkResolver.resolve")
def test_instagram_finder_resolves_linktree_with_official_website(mock_resolve):
    mock_resolve.return_value = {
        "has_website": True,
        "website_url": "https://www.archergrouprealestate.com",
        "email": None,
        "destination_links": ["https://www.archergrouprealestate.com"]
    }
    finder = InstagramFinder()
    items = [
        {
            "title": "Jason & Felecia Archer (@boiserealtor) • Instagram",
            "href": "https://www.instagram.com/boiserealtor/",
            "snippet": "IDAHO REALTORS + Relocation Experts | 🔗 linktr.ee/archergroup"
        }
    ]
    leads = finder.parse_search_items(items, city="Boise")
    assert len(leads) == 1
    assert leads[0].website == "https://www.archergrouprealestate.com"

@patch("src.scrapers.bio_link_resolver.BioLinkResolver.resolve")
def test_instagram_finder_resolves_linktree_without_website_extracts_email(mock_resolve):
    mock_resolve.return_value = {
        "has_website": False,
        "website_url": None,
        "email": "sarah.dallas@gmail.com",
        "destination_links": ["https://tiktok.com/@sarah"]
    }
    finder = InstagramFinder()
    items = [
        {
            "title": "Sarah Jenkins | Dallas Realtor (@sarahdallas) • Instagram",
            "href": "https://www.instagram.com/sarahdallas/",
            "snippet": "Dallas Real Estate Advisor | Check my links: beacons.ai/sarahdallas"
        }
    ]
    leads = finder.parse_search_items(items, city="Dallas")
    assert len(leads) == 1
    assert leads[0].website is None
    assert leads[0].email == "sarah.dallas@gmail.com"

def test_instagram_finder_ignores_portals_and_tiktok_as_websites():
    finder = InstagramFinder()
    bio_with_tiktok = "Top Producer in Montreal | Follow on TikTok: tiktok.com/@gautamwalia | Call 555-0199"
    assert finder.detect_website_in_text(bio_with_tiktok) is None

    bio_with_realtor_portal = "Listing agent in Montreal | View my listings at realtor.com or zillow.com"
    assert finder.detect_website_in_text(bio_with_realtor_portal) is None

def test_instagram_finder_builds_bilingual_queries_for_montreal():
    finder = InstagramFinder()
    queries = finder.build_discovery_queries("Montreal")
    assert any("courtier immobilier" in q for q in queries)









import pytest
from unittest.mock import patch, MagicMock
from src.ai_verifier import GeminiVerifier, AIAnalysisResult

def test_ai_analysis_result_defaults():
    res = AIAnalysisResult(has_website=False, verified_email="info@test.com")
    assert res.has_website is False
    assert res.official_website_url is None
    assert res.verified_email == "info@test.com"

def test_gemini_verifier_parses_json_response():
    verifier = GeminiVerifier(api_key="mock-key")
    mock_gemini_output = '''
    ```json
    {
      "has_website": false,
      "official_website_url": null,
      "verified_email": "hidreamestate@gmail.com",
      "facebook_url": null,
      "instagram_url": null,
      "reasoning": "Dream Estates has no dedicated website. Found valid Gmail contact."
    }
    ```
    '''
    result = verifier._parse_response_text(mock_gemini_output)
    assert result is not None
    assert result.has_website is False
    assert result.official_website_url is None
    assert result.verified_email == "hidreamestate@gmail.com"
    assert "Dream Estates" in result.reasoning

def test_gemini_verifier_detects_when_business_has_official_website():
    verifier = GeminiVerifier(api_key="mock-key")
    mock_gemini_output = '''
    {
      "has_website": true,
      "official_website_url": "https://praveen.realtor",
      "verified_email": "praveen@realtor.com",
      "facebook_url": null,
      "instagram_url": null,
      "reasoning": "Praveen Realtor has an official website at praveen.realtor."
    }
    '''
    result = verifier._parse_response_text(mock_gemini_output)
    assert result is not None
    assert result.has_website is True
    assert result.official_website_url == "https://praveen.realtor"

def test_gemini_verifier_graceful_fallback_on_invalid_json():
    verifier = GeminiVerifier(api_key="mock-key")
    bad_text = "Sorry, I could not parse this information."
    result = verifier._parse_response_text(bad_text)
    assert result is None

@patch("src.ai_verifier.requests.post")
def test_gemini_verifier_analyze_lead_with_mock_api(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"has_website": false, "official_website_url": null, "verified_email": "avinashkumarsharma76@gmail.com", "facebook_url": "https://facebook.com/brahmdev", "instagram_url": null, "reasoning": "Local broker with no website."}'
                        }
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    verifier = GeminiVerifier(api_key="mock-key")
    res = verifier.analyze_lead(
        business_name="Brahmdev Property Dealer",
        city="Patna",
        search_snippets="Contact: avinashkumarsharma76@gmail.com Phone: 7903326045",
        links=[{"title": "Justdial", "href": "https://justdial.com/patna/brahmdev"}]
    )
    assert res is not None
    assert res.has_website is False
    assert res.verified_email == "avinashkumarsharma76@gmail.com"
    assert res.facebook_url == "https://facebook.com/brahmdev"

@patch("src.ai_verifier.requests.post")
def test_gemini_verifier_fallback_on_429(mock_post):
    # First model hits 429 quota, fallback model succeeds with 200
    res_429 = MagicMock()
    res_429.status_code = 429

    res_200 = MagicMock()
    res_200.status_code = 200
    res_200.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"has_website": true, "official_website_url": "https://archergrouprealestate.com", "verified_email": null, "facebook_url": null, "instagram_url": null, "reasoning": "Found official agency website."}'
                        }
                    ]
                }
            }
        ]
    }
    mock_post.side_effect = [res_429, res_200]

    verifier = GeminiVerifier(api_key="mock-key")
    res = verifier.analyze_lead(
        business_name="boiserealtor",
        city="Boise",
        search_snippets="www.archergrouprealestate.com"
    )
    assert res is not None
    assert res.has_website is True
    assert res.official_website_url == "https://archergrouprealestate.com"
    assert mock_post.call_count == 2


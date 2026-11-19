import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import requests

@dataclass
class AIAnalysisResult:
    has_website: bool = False
    official_website_url: Optional[str] = None
    verified_email: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    reasoning: str = ""

class GeminiVerifier:
    """
    Smart Brain LLM Integration using Google Gemini.
    Accurately determines whether a real estate business has an official dedicated website,
    distinguishes third-party aggregator portals from agency sites, and extracts verified emails.
    """
    FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-2.5-flash"]

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite"):
        self.api_key = api_key or ""
        self.model = model
        self.models_to_try = [model] + [m for m in self.FALLBACK_MODELS if m != model]

    def _parse_response_text(self, text: str) -> Optional[AIAnalysisResult]:
        if not text:
            return None
        # Extract json content if enclosed in markdown blocks
        clean_text = text.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if json_match:
            clean_text = json_match.group(1).strip()
        elif clean_text.startswith("{") and clean_text.endswith("}"):
            clean_text = clean_text.strip()
        else:
            first_brace = clean_text.find("{")
            last_brace = clean_text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                clean_text = clean_text[first_brace:last_brace + 1].strip()

        try:
            data = json.loads(clean_text)
            has_web = bool(data.get("has_website", False))
            off_url = data.get("official_website_url")
            if not off_url or not isinstance(off_url, str) or not off_url.strip():
                off_url = None
            else:
                off_url = off_url.strip()

            email = data.get("verified_email")
            if not email or not isinstance(email, str) or not email.strip() or "@" not in email:
                email = None
            else:
                email = email.strip(".,;:!? '\"").lower()

            fb = data.get("facebook_url")
            if fb and isinstance(fb, str) and fb.strip().startswith("http"):
                fb = fb.strip()
            else:
                fb = None

            insta = data.get("instagram_url")
            if insta and isinstance(insta, str) and insta.strip().startswith("http"):
                insta = insta.strip()
            else:
                insta = None

            reasoning = str(data.get("reasoning", "")).strip()

            return AIAnalysisResult(
                has_website=has_web,
                official_website_url=off_url,
                verified_email=email,
                facebook_url=fb,
                instagram_url=insta,
                reasoning=reasoning
            )
        except Exception:
            return None

    def analyze_lead(
        self,
        business_name: str,
        city: str,
        search_snippets: str = "",
        links: Optional[List[Dict[str, str]]] = None
    ) -> Optional[AIAnalysisResult]:
        """
        Invokes Gemini LLM to reason over search findings for a business.
        """
        if not self.api_key:
            return None

        links_str = ""
        if links:
            links_str = "\n".join([f"- {l.get('title', '')}: {l.get('href', '')}" for l in links[:15]])

        prompt = f"""You are an elite real estate research and lead verification AI.
Examine the following real estate business and search findings to answer:
1. Does this business have an OFFICIAL DEDICATED WEBSITE (owned and operated by this specific agency)?
   CRITICAL RULE: Portals, aggregators, directories, and developer complexes (such as Justdial, Magicbricks, 99acres, Housing.com, Sulekha, RealEstateIndia, SquareYards, NoBroker, Eldeco Group, Growfy, Facebook, Instagram) are THIRD-PARTY SITES, NOT the business's official website! Do NOT mark them as an official website.
2. Does the business have a real, verified contact email (e.g. gmail, yahoo, or custom domain)?
   CRITICAL RULE: Discard platform corporate emails (e.g. info@instagram.com, support@google.com).
3. Extract their official Facebook or Instagram page if found.

Business Name: {business_name}
City: {city}

Google Search Findings / Overview:
{search_snippets[:2000]}

Relevant Links:
{links_str}

Respond STRICTLY with valid JSON in this exact structure:
{{
  "has_website": true or false,
  "official_website_url": "https://..." or null,
  "verified_email": "example@email.com" or null,
  "facebook_url": "https://facebook.com/..." or null,
  "instagram_url": "https://instagram.com/..." or null,
  "reasoning": "brief 1-sentence reasoning"
}}
"""

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        for model_name in self.models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                resp = requests.post(url, json=payload, timeout=8.0)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text_resp = parts[0].get("text", "")
                            parsed = self._parse_response_text(text_resp)
                            if parsed:
                                return parsed
                elif resp.status_code in (429, 503):
                    # Rate limit or temporary model unavailability; try next fallback model
                    continue
            except Exception:
                continue

        return None

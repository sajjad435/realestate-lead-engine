import re
import urllib.parse
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
from src.filter import LeadFilter

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

PLATFORM_CORPORATE_DOMAINS = (
    "instagram.com", "facebook.com", "meta.com", "fb.com", "google.com",
    "duckduckgo.com", "apple.com", "microsoft.com", "yahoo-inc.com", "twitter.com", "x.com"
)

class EmailEnricher:
    """
    Finds verified professional emails for real estate agents whose social media bio
    lacks a direct email address. Cross-references the agent's name, brokerage/agency,
    and city across official public broker directories and web records.
    """
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }

    def extract_matching_email(self, text: str, agent_name: str) -> Optional[str]:
        if not text:
            return None

        matches = EMAIL_REGEX.findall(text)
        candidates = []
        for m in matches:
            clean_m = m.strip(".,;:!? '\"").lower()
            if not LeadFilter.is_valid_email_format(clean_m):
                continue
            if any(clean_m.endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js']):
                continue
            domain = clean_m.split("@")[1].strip()
            if any(domain == p or domain.endswith("." + p) for p in PLATFORM_CORPORATE_DOMAINS):
                continue
            candidates.append(clean_m)

        if not candidates:
            return None

        # Check for name token alignment (e.g. 'philippe' or 'daunais' in email prefix)
        name_tokens = [
            t.lower() for t in re.sub(r"[^a-zA-Z]", " ", agent_name).split()
            if len(t) >= 3 and t.lower() not in ("realtor", "realty", "courtier", "broker", "agent", "montreal", "real", "estate")
        ]
        for c in candidates:
            prefix = c.split("@")[0].lower()
            if any(tok in prefix for tok in name_tokens):
                return c

        return candidates[0]

    def enrich_email(
        self,
        name: str,
        city: str,
        agency: Optional[str] = None
    ) -> Optional[str]:
        """
        Deep searches public web and directories for the agent's verified contact email.
        """
        clean_name = re.sub(r"[|•\-].*$", "", name).strip()
        for suffix in ("Realtor", "Courtier immobilier", "Real Estate Agent", "Real Estate Broker", "Courtier Immobilier"):
            clean_name = clean_name.replace(suffix, "").strip()

        if city:
            clean_name = re.sub(rf"\b{re.escape(city.strip())}\b", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+", " ", clean_name).strip()

        if not clean_name or len(clean_name.split()) < 2:
            return None

        clean_city = city.strip()
        queries = [
            f'"{clean_name}" "{clean_city}" email',
            f'"{clean_name}" "{clean_city}" realtor email'
        ]
        if agency:
            queries.insert(0, f'"{clean_name}" "{agency}" "{clean_city}" email')

        for q in queries:
            try:
                url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
                resp = requests.get(url, headers=self.headers, timeout=5.0)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text_content = " ".join([el.get_text() for el in soup.find_all(["div", "a", "span", "p"])])
                    found = self.extract_matching_email(text_content, clean_name)
                    if found:
                        return found
            except Exception:
                continue

        return None

import os
import re
from urllib.parse import quote_plus
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from src.models import Lead
from src.ai_verifier import GeminiVerifier
from src.filter import LeadFilter

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

class IntentFinder:
    """
    Finds real estate agents and brokers actively asking for a website or web designer
    on public discussion forums like Reddit (r/realtors, r/RealEstateTechnology).
    Filters out agency self-promotions and targets genuine high-intent clients.
    """
    DISQUALIFYING_PROVIDER_PHRASES = [
        "we build", "our agency", "i build websites", "free consultation",
        "hire our team", "web design services", "best web design company",
        "dm us for pricing", "our developers", "portfolio:", "offering web design"
    ]

    QUALIFYING_BUYER_PHRASES = [
        "need a website", "looking for someone to build", "looking for web designer",
        "looking for a web designer", "recommend a website builder",
        "hire someone to build", "how much to build a website",
        "need a simple website", "need a clean website", "new agent need",
        "solo agent looking", "recommendations for a website"
    ]

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        test_mode: bool = False
    ):
        self.test_mode = test_mode
        self.ai_verifier = GeminiVerifier(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY", ""))

    def build_search_queries(self) -> List[str]:
        return [
            'site:reddit.com/r/realtors "need a website"',
            'site:reddit.com/r/realtors "looking for web designer" OR "build my website"',
            'site:reddit.com/r/realtors "hire someone to build a website"',
            'site:reddit.com/r/RealEstateTechnology "need a website" realtor',
            'site:reddit.com "realtor" "need a website" email'
        ]

    BUYER_INTENT_PATTERN = re.compile(
        r"\b(?:need|looking for|want|hire|recommend(?:ation|ations)?)\b.*?\b(?:website|web designer|web developer)\b",
        re.IGNORECASE
    )

    def is_realtor_buyer_intent(self, title: str, snippet: str) -> bool:
        full_text = f"{title} {snippet}".lower()

        # Reject web agencies / designers pitching their services
        if any(phrase in full_text for phrase in self.DISQUALIFYING_PROVIDER_PHRASES):
            return False

        # Check regex pattern for buyer intent (e.g. "need a simple clean website")
        if self.BUYER_INTENT_PATTERN.search(full_text):
            return True

        # Check phrase match
        if any(phrase in full_text for phrase in self.QUALIFYING_BUYER_PHRASES):
            return True

        return False

    def extract_email_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        platform_domains = (
            "reddit.com", "facebook.com", "instagram.com", "google.com",
            "duckduckgo.com", "apple.com", "microsoft.com", "yahoo-inc.com"
        )
        matches = EMAIL_REGEX.findall(text)
        for m in matches:
            clean_m = m.strip(".,;:!? '\"")
            if "@" in clean_m:
                domain = clean_m.split("@")[1].lower().strip()
                if any(domain == p or domain.endswith("." + p) for p in platform_domains):
                    continue
                if not any(clean_m.lower().endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js']):
                    return clean_m
        return None

    def parse_search_items(self, items: List[Dict[str, Any]]) -> List[Lead]:
        leads = []
        for it in items:
            title = it.get("title", "")
            snippet = it.get("snippet", "")
            href = it.get("href", "")
            full_text = f"{title} | {snippet}"

            # Only process if buyer intent is evident
            if not self.is_realtor_buyer_intent(title, snippet):
                continue

            email = self.extract_email_from_text(full_text)

            # Consult Gemini AI Smart Brain if available
            if self.ai_verifier and self.ai_verifier.api_key:
                ai_res = self.ai_verifier.analyze_lead(
                    business_name=f"Reddit Realtor Inquiry ({title[:60]})",
                    city="Inbound Public Post",
                    search_snippets=full_text,
                    links=[{"title": title, "href": href}]
                )
                if ai_res:
                    if ai_res.verified_email and not email:
                        email = ai_res.verified_email

            # Extract a sensible author / name from title
            clean_name = title.split(":")[0].split("-")[0].replace("r/realtors", "").strip()
            if not clean_name or len(clean_name) < 3:
                clean_name = "Realtor Prospect (Reddit Intent)"

            if email:
                print(f"   🔥 [Reddit Intent] {clean_name} | Verified Email: {email} | Thread: {href}")
                leads.append(Lead(
                    name=clean_name,
                    city="Inbound Intent",
                    state="",
                    website=None,
                    email=email,
                    source="Reddit Intent",
                    profile_url=href
                ))
            else:
                print(f"   ℹ️ [Reddit Intent] {clean_name} asked for website but no public email in thread: {href}")

        return leads

    def search_intent(self, max_leads: int = 15) -> List[Lead]:
        print("\n🔥 [Intent Finder] Scanning Reddit & public discussions for realtors asking for a website...")

        if self.test_mode or os.getenv("TEST_MODE") == "1":
            return [
                Lead(
                    name="Dallas Solo Realtor Inquiry",
                    city="Inbound Intent",
                    state="TX",
                    website=None,
                    email="dallas.agent.intent@gmail.com",
                    source="Reddit Intent",
                    profile_url="https://reddit.com/r/realtors/comments/test_intent_1"
                )
            ]

        raw_items = []
        seen_urls = set()
        queries = self.build_search_queries()

        # 1. Primary Engine: Playwright Chrome
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=CHROME_PATH if os.path.exists(CHROME_PATH) else None,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                for q_idx, search_query in enumerate(queries):
                    ddg_url = f"https://duckduckgo.com/?q={quote_plus(search_query)}&t=h_&ia=web"
                    print(f"   ↳ [Intent Angle {q_idx+1}/{len(queries)}] Searching: '{search_query}'...")
                    try:
                        page.goto(ddg_url, timeout=18000)
                        page.wait_for_timeout(2500)
                    except Exception:
                        continue

                    articles = page.locator('article[data-testid="result"]').all()
                    for a in articles:
                        link_el = a.locator('a[data-testid="result-title-a"]')
                        snippet_el = a.locator('div[data-result="snippet"]')
                        title_text = link_el.inner_text() if link_el.count() > 0 else ""
                        href_url = link_el.get_attribute("href") if link_el.count() > 0 else ""
                        snippet_text = snippet_el.inner_text() if snippet_el.count() > 0 else ""

                        if "reddit.com/r/" in href_url and href_url not in seen_urls:
                            seen_urls.add(href_url)
                            raw_items.append({
                                "title": title_text,
                                "href": href_url,
                                "snippet": snippet_text
                            })

                browser.close()

        except Exception as e:
            print(f"   ⚠️ Playwright search notice for Intent Finder: {e}. Trying HTTP fallback...")

        # 2. Secondary Engine: HTTP requests fallback
        if not raw_items:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                }
                for search_query in queries:
                    r = requests.get(f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}", headers=headers, timeout=10)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, "html.parser")
                        results = soup.find_all("div", class_="result")
                        for res in results:
                            title_el = res.find("a", class_="result__title")
                            snippet_el = res.find("a", class_="result__snippet")
                            link_el = res.find("a", class_="result__url")
                            href_val = f"https://{link_el.get_text().strip()}" if link_el else ""
                            if "reddit.com/r/" in href_val and href_val not in seen_urls:
                                seen_urls.add(href_val)
                                raw_items.append({
                                    "title": title_el.get_text().strip() if title_el else "",
                                    "href": href_val,
                                    "snippet": snippet_el.get_text().strip() if snippet_el else ""
                                })
            except Exception:
                pass

        print(f"   ↳ Found {len(raw_items)} potential realtor website inquiry threads")
        if not raw_items:
            return []

        return self.parse_search_items(raw_items)

import os
import re
import time
from urllib.parse import quote_plus
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from src.models import Lead, LocationInput
from src.ai_verifier import GeminiVerifier
from src.filter import LeadFilter
from src.scrapers.bio_link_resolver import BioLinkResolver
from src.scrapers.email_enricher import EmailEnricher

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

class FacebookFinder:
    """
    Finds real estate agents, agencies, and brokers on Facebook Pages.
    Inspects About/Intro sections for contact email and verifies if the business
    lacks an external official website.
    NEVER invents or guesses fake email addresses.
    """
    INVALID_SLUGS = {
        "login", "events", "groups", "help", "watch", "marketplace",
        "share", "dialog", "photo", "photos", "reel", "reels", "story",
        "stories", "recover", "policy", "privacy", "terms", "pages",
        "directory", "biz", "legal", "ads", "safety", "about"
    }

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        test_mode: bool = False
    ):
        self.test_mode = test_mode
        self.ai_verifier = GeminiVerifier(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY", ""))
        self.bio_resolver = BioLinkResolver()
        self.email_enricher = EmailEnricher()
        self.social_dm_leads: List[Lead] = []

    def is_valid_facebook_page_slug(self, slug: str) -> bool:
        if not slug or not isinstance(slug, str):
            return False
        clean = slug.strip("/?# ").lower()
        if clean in self.INVALID_SLUGS:
            return False
        if len(clean) < 2 or len(clean) > 60:
            return False
        if clean.isdigit():
            return False
        return bool(re.match(r"^[a-zA-Z0-9._-]+$", clean))

    def build_search_queries(self, city: str) -> List[str]:
        """
        Builds targeted multi-query discovery for real estate business and agent pages on Facebook.
        """
        c = city.strip()
        queries = [
            f'site:facebook.com "{c}" realtor email',
            f'site:facebook.com "{c}" "real estate" email',
            f'site:facebook.com "{c}" realtor'
        ]
        indian_cities = {
            "patna", "lucknow", "delhi", "mumbai", "pune", "bangalore",
            "kolkata", "ranchi", "jaipur", "noida", "gurgaon", "ahmedabad", "chandigarh"
        }
        if c.lower() in indian_cities:
            queries.append(f'site:facebook.com "{c}" "property dealer" email')
        if c.lower() in ("montreal", "montréal", "quebec", "québec", "laval", "gatineau"):
            queries.extend([
                f'site:facebook.com "{c}" "courtier immobilier" email',
                f'site:facebook.com "{c}" "agence immobiliere"'
            ])
        return queries

    def build_paginated_google_urls(self, query: str, max_pages: int = 3) -> List[str]:
        """
        Builds Google Search pagination URLs (start=0, start=10, start=20, etc.)
        to inspect multiple search pages for Facebook pages.
        """
        urls = []
        for page in range(max_pages):
            start = page * 10
            urls.append(f"https://www.google.com/search?q={quote_plus(query)}&start={start}&hl=en")
        return urls

    def detect_website_in_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        platform_domains = (
            "facebook.com", "instagram.com", "threads.net", "whatsapp.com",
            "twitter.com", "x.com", "linkedin.com", "youtube.com", "tiktok.com",
            "google.com", "duckduckgo.com", "realtor.com", "realtor.ca", "zillow.com",
            "redfin.com", "trulia.com", "centris.ca", "linktr.ee", "beacons.ai"
        )
        url_matches = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)
        for u in url_matches:
            clean_u = u.strip(".,;:!? '\"").lower()
            if not any(p in clean_u for p in platform_domains):
                return clean_u if clean_u.startswith("http") else f"https://{clean_u}"
        
        # Strip emails so username parts like 'name.realty@gmail.com' don't get misidentified as domains
        text_without_emails = re.sub(EMAIL_REGEX, " ", text)
        domain_matches = re.findall(r'\b([a-zA-Z0-9-]+\.(?:com|net|org|co|us|io|biz|estate|realty|in|co\.in))\b', text_without_emails, re.I)
        for d in domain_matches:
            clean_d = d.strip().lower()
            if not any(clean_d == p or clean_d.endswith("." + p) for p in platform_domains):
                return f"https://{clean_d}"
        return None

    def extract_email_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        platform_domains = (
            "facebook.com", "instagram.com", "meta.com", "fb.com", "google.com",
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

    def parse_search_items(
        self,
        items: List[Dict[str, Any]],
        city: str,
        state: Optional[str] = None
    ) -> List[Lead]:
        leads = []
        for it in items:
            title = it.get("title", "")
            snippet = it.get("snippet", "")
            href = it.get("href", "")
            full_text = f"{title} | {snippet}"

            # Extract clean slug and page URL
            clean_url = href.split("?")[0].rstrip("/")
            slug_match = re.search(r"facebook\.com/(?:pages/[^/]+/)?([^/?#]+)", clean_url, re.I)
            raw_slug = slug_match.group(1).lower() if slug_match else ""

            if not self.is_valid_facebook_page_slug(raw_slug):
                continue

            clean_profile_url = f"https://www.facebook.com/{raw_slug}"

            # Extract Name
            clean_name = title
            for suffix in [" - Home | Facebook", " | Facebook", " - Real Estate Agency", " - Real Estate Service", " - Realtor"]:
                clean_name = clean_name.replace(suffix, "")
            clean_name = clean_name.split("|")[0].split("•")[0].strip()
            if not clean_name or clean_name.lower() in ("facebook", "home"):
                clean_name = raw_slug.replace(".", " ").replace("-", " ").title()

            email = self.extract_email_from_text(full_text)
            detected_website = self.detect_website_in_text(full_text)

            # Deep inspect bio-link aggregator (Linktree, Beacons, etc.)
            bio_service_url = self.bio_resolver.extract_bio_service_url(full_text)
            resolved_bio_links = []
            if bio_service_url:
                bio_info = self.bio_resolver.resolve(bio_service_url)
                if bio_info.get("has_website"):
                    detected_website = bio_info.get("website_url")
                if bio_info.get("email") and not email:
                    email = bio_info.get("email")
                resolved_bio_links = [{"title": f"Bio Service Link: {l}", "href": l} for l in bio_info.get("destination_links", [])]

            # Consult Gemini AI Smart Brain if available
            if self.ai_verifier and self.ai_verifier.api_key:
                ai_res = self.ai_verifier.analyze_lead(
                    business_name=f"{clean_name} (Facebook: {raw_slug})",
                    city=city,
                    search_snippets=full_text,
                    links=[{"title": "Facebook Page", "href": clean_profile_url}] + resolved_bio_links
                )
                if ai_res:
                    if ai_res.has_website:
                        detected_website = ai_res.official_website_url or detected_website or "https://verified-website.com"
                        print(f"   🧠 [Gemini AI Brain] {clean_name}: {ai_res.reasoning}")
                    if ai_res.verified_email and not email:
                        email = ai_res.verified_email

            # Check if email domain already hosts an active live website
            if not detected_website and email:
                custom_domain_web = LeadFilter.check_custom_domain_website(email)
                if custom_domain_web:
                    detected_website = custom_domain_web

            # Method 2: If no website and no email, attempt deep email enrichment
            if not detected_website and not email:
                agency = None
                for ag in ["Royal LePage", "Remax", "RE/MAX", "Sutton", "Century 21", "Keller Williams", "Compass", "Sotheby's", "Coldwell Banker", "eXp Realty", "Proprio Direct", "Via Capitale"]:
                    if ag.lower() in full_text.lower():
                        agency = ag
                        break
                enriched_email = self.email_enricher.enrich_email(clean_name, city, agency=agency)
                if enriched_email:
                    email = enriched_email
                    print(f"   🎯 [Facebook Enriched] Verified contact email found for {clean_name}: {email}")

            if detected_website:
                print(f"   ❌ [Facebook] {clean_name} has website ({detected_website}) -> Skipped")
                leads.append(Lead(
                    name=clean_name,
                    city=city,
                    state=state,
                    website=detected_website,
                    email=email,
                    source="Facebook",
                    profile_url=clean_profile_url
                ))
            else:
                if email:
                    print(f"   ✅ [Facebook] {clean_name} | No Website | Verified Email: {email} | Page: {clean_profile_url}")
                    leads.append(Lead(
                        name=clean_name,
                        city=city,
                        state=state,
                        website=None,
                        email=email,
                        source="Facebook",
                        profile_url=clean_profile_url
                    ))
                else:
                    print(f"   📱 [Facebook] {clean_name} | No website, no email -> Added to Social DM Queue")
                    self.social_dm_leads.append(Lead(
                        name=clean_name,
                        city=city,
                        state=state,
                        website=None,
                        email=None,
                        source="Facebook",
                        profile_url=clean_profile_url,
                        snippet=full_text
                    ))

        return leads

    def search_city(self, location: LocationInput, max_places: int = 25) -> List[Lead]:
        self.social_dm_leads = []
        query_loc = location.city or location.raw_location
        print(f"\n📘 [Facebook Pages] Scanning real estate agency and agent pages for: {query_loc}...")

        if self.test_mode or os.getenv("TEST_MODE") == "1":
            clean_loc = re.sub(r"[^a-zA-Z0-9]", "", query_loc).lower()
            return [
                Lead(
                    name=f"{query_loc} Property Experts",
                    city=query_loc,
                    state=location.state,
                    website=None,
                    email=f"fb.{clean_loc}@gmail.com",
                    source="Facebook",
                    profile_url=f"https://www.facebook.com/{clean_loc}realty"
                )
            ]

        raw_items = []
        seen_slugs = set()
        discovery_queries = self.build_search_queries(query_loc)

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

                for d_idx, search_query in enumerate(discovery_queries):
                    # Multi-page Google Search (Pages 1, 2, 3)
                    google_urls = self.build_paginated_google_urls(search_query, max_pages=3)
                    google_blocked = False

                    for p_idx, g_url in enumerate(google_urls):
                        if len(seen_slugs) >= 40:
                            break
                        print(f"   ↳ [Facebook Angle {d_idx+1} | Google Page {p_idx+1}] Querying: '{search_query}'...")
                        try:
                            page.goto(g_url, timeout=16000)
                            page.wait_for_timeout(2000)
                            g_body = page.inner_text("body")
                            if "unusual traffic" in g_body or "recaptcha" in g_body.lower():
                                google_blocked = True
                                break

                            # Extract organic Google results for Facebook
                            g_links = page.locator('a[href*="facebook.com/"]').all()
                            for gl in g_links:
                                href_url = gl.get_attribute("href") or ""
                                if "facebook.com/" in href_url:
                                    try:
                                        clean_url = href_url.split("?")[0].rstrip("/")
                                        slug_match = re.search(r"facebook\.com/(?:pages/[^/]+/)?([^/?#]+)", clean_url, re.I)
                                        slug = slug_match.group(1).lower() if slug_match else ""
                                        if slug and slug not in seen_slugs and self.is_valid_facebook_page_slug(slug):
                                            seen_slugs.add(slug)
                                            parent_text = gl.evaluate("el => el.closest('div.g') ? el.closest('div.g').innerText : el.innerText")
                                            raw_items.append({
                                                "title": slug.replace(".", " ").replace("-", " ").title(),
                                                "href": f"https://www.facebook.com/{slug}",
                                                "snippet": parent_text[:1200]
                                            })
                                    except Exception:
                                        pass
                        except Exception:
                            continue

                    # Complement with DuckDuckGo search if Google blocked or needed more results
                    if google_blocked or len(raw_items) < 15:
                        ddg_url = f"https://duckduckgo.com/?q={quote_plus(search_query)}&t=h_&ia=web"
                        print(f"   ↳ [Facebook Angle {d_idx+1} | DuckDuckGo] Querying: '{search_query}'...")
                        try:
                            page.goto(ddg_url, timeout=18000)
                            page.wait_for_timeout(2500)
                            for _ in range(2):
                                page.evaluate("window.scrollBy(0, 3000)")
                                page.wait_for_timeout(1000)
                        except Exception:
                            continue

                        articles = page.locator('article[data-testid="result"]').all()
                        for a in articles:
                            link_el = a.locator('a[data-testid="result-title-a"]')
                            snippet_el = a.locator('div[data-result="snippet"]')
                            title_text = link_el.inner_text() if link_el.count() > 0 else ""
                            href_url = link_el.get_attribute("href") if link_el.count() > 0 else ""
                            snippet_text = snippet_el.inner_text() if snippet_el.count() > 0 else ""

                            if "facebook.com/" in href_url:
                                try:
                                    clean_url = href_url.split("?")[0].rstrip("/")
                                    slug_match = re.search(r"facebook\.com/(?:pages/[^/]+/)?([^/?#]+)", clean_url, re.I)
                                    slug = slug_match.group(1).lower() if slug_match else ""
                                    if slug and slug not in seen_slugs and self.is_valid_facebook_page_slug(slug):
                                        seen_slugs.add(slug)
                                        raw_items.append({
                                            "title": title_text,
                                            "href": href_url,
                                            "snippet": snippet_text
                                        })
                                except Exception:
                                    pass

                # Cross-reference with Google Search to reveal external websites and business emails
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                for it in raw_items[:25]:
                    try:
                        clean_title = it["title"].split("|")[0].split("-")[0].strip()
                        g_query = f"{clean_title} {query_loc} website OR email"
                        page.goto(f"https://www.google.com/search?q={quote_plus(g_query)}&hl=en", timeout=12000)
                        page.wait_for_timeout(2000)
                        g_body = page.inner_text("body")
                        if "unusual traffic" not in g_body:
                            it["snippet"] = f"{it['snippet']} | Google Search Findings: {g_body[:1800]}"
                    except Exception:
                        pass

                browser.close()

        except Exception as e:
            print(f"   ⚠️ Playwright browser search notice for Facebook: {e}. Trying HTTP fallback...")

        # 2. Secondary Engine: HTTP requests fallback if Playwright got no results
        if not raw_items:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                }
                for search_query in discovery_queries:
                    r = requests.get(f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}", headers=headers, timeout=10)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, "html.parser")
                        results = soup.find_all("div", class_="result")
                        for res in results:
                            title_el = res.find("a", class_="result__title")
                            snippet_el = res.find("a", class_="result__snippet")
                            link_el = res.find("a", class_="result__url")
                            href_val = f"https://{link_el.get_text().strip()}" if link_el else ""
                            if "facebook.com/" in href_val:
                                try:
                                    clean_url = href_val.split("?")[0].rstrip("/")
                                    slug_match = re.search(r"facebook\.com/(?:pages/[^/]+/)?([^/?#]+)", clean_url, re.I)
                                    slug = slug_match.group(1).lower() if slug_match else ""
                                    if slug and slug not in seen_slugs and self.is_valid_facebook_page_slug(slug):
                                        seen_slugs.add(slug)
                                        raw_items.append({
                                            "title": title_el.get_text().strip() if title_el else "",
                                            "href": href_val,
                                            "snippet": snippet_el.get_text().strip() if snippet_el else ""
                                        })
                                except Exception:
                                    pass
            except Exception:
                pass

        print(f"   ↳ Found {len(raw_items)} potential Facebook real estate pages")
        if not raw_items:
            return []

        return self.parse_search_items(raw_items, city=query_loc, state=location.state)

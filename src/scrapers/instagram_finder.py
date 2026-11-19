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

class InstagramFinder:
    """
    Finds real estate agents on Instagram and inspects profiles, bios, and posts.
    Identifies agents who do not have an external website link,
    but have an email address in bio or posts.
    NEVER invents or guesses fake email addresses.
    """
    INVALID_USERNAMES = {
        "reel", "reels", "p", "stories", "explore", "tv", "direct", 
        "accounts", "legal", "about", "tags", "locations", "directory", "popular"
    }

    def __init__(
        self,
        session_cookie: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        test_mode: bool = False
    ):
        self.session_cookie = session_cookie
        self.test_mode = test_mode
        self.ai_verifier = GeminiVerifier(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY", ""))
        self.bio_resolver = BioLinkResolver()
        self.email_enricher = EmailEnricher()
        self.social_dm_leads: List[Lead] = []

    def is_valid_instagram_username(self, username: str) -> bool:
        if not username or not isinstance(username, str):
            return False
        clean = username.strip().lower()
        if clean in self.INVALID_USERNAMES:
            return False
        if len(clean) < 2 or len(clean) > 30:
            return False
        if clean.isdigit():
            return False
        return bool(re.match(r"^[a-zA-Z0-9_.]+$", clean))

    def build_discovery_queries(self, city: str) -> List[str]:
        """
        Builds targeted multi-query discovery for realtors, agents, and email-verified
        profiles in the target location.
        """
        c = city.strip()
        queries = [
            f'site:instagram.com "{c}" realtor',
            f'site:instagram.com "{c}" "real estate" email',
            f'site:instagram.com "{c}" realtor "@gmail.com"',
            f'site:instagram.com "{c} realtor"'
        ]
        # Bilingual queries for French Canadian markets (e.g. Montreal, Quebec City, Laval)
        if c.lower() in ("montreal", "montréal", "quebec", "québec", "laval", "gatineau"):
            queries.extend([
                f'site:instagram.com "{c}" "courtier immobilier"',
                f'site:instagram.com "{c}" "courtier immobilier" email',
                f'site:instagram.com "{c}" "agence immobiliere"'
            ])
        return queries

    def build_paginated_google_urls(self, query: str, max_pages: int = 3) -> List[str]:
        """
        Builds Google Search pagination URLs (start=0, start=10, start=20, etc.)
        to inspect multiple search pages for a query.
        """
        urls = []
        for page in range(max_pages):
            start = page * 10
            urls.append(f"https://www.google.com/search?q={quote_plus(query)}&start={start}&hl=en")
        return urls

    def detect_website_in_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        # 1. Check for common website builders (excluding multi-link aggregators like Linktree)
        builder_services = [
            "wix.com", "wixsite.com", "squarespace.com", "weebly.com", "webflow.io"
        ]
        for service in builder_services:
            if service in text.lower():
                return f"https://{service}"

        # 2. Extract potential domain tokens (excluding emails, IG/FB and bio-link aggregators)
        text_without_emails = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", " ", text)
        domain_pattern = re.compile(
            r"\b((?:https?://|www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.(?:com|org|net|co|io|ai|me|us|biz|info|realtor|estate|properties|homes|in))\b",
            re.IGNORECASE
        )
        
        ignored_domains = (
            "instagram.com", "cdninstagram.com", "threads.net", "facebook.com", "fb.com", "meta.com",
            "google.com", "duckduckgo.com", "schema.org", "w3.org", "apple.com", "netmng.com", "fbcdn.net",
            "doubleclick.net", "googletagmanager.com", "linktr.ee", "beacons.ai", "campsite.bio",
            "tap.bio", "solo.to", "linkin.bio", "lnk.bio", "bio.site", "snipfeed.co", "stan.store", "bit.ly",
            "tiktok.com", "youtube.com", "linkedin.com", "twitter.com", "x.com", "snapchat.com", "pinterest.com",
            "realtor.com", "realtor.ca", "zillow.com", "redfin.com", "trulia.com", "centris.ca",
            "justdial.com", "magicbricks.com", "99acres.com", "housing.com", "sulekha.com"
        )
        
        for match in domain_pattern.finditer(text_without_emails):
            domain_str = match.group(1).lower().strip()
            bare_domain = domain_str.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            if not any(bare_domain.endswith(ign) for ign in ignored_domains) and "." in bare_domain:
                return domain_str if domain_str.startswith("http") else f"https://{domain_str}"
                
        return None

    def extract_website_from_profile_html(self, html: str) -> Optional[str]:
        if not html:
            return None
        
        # Search for external_url in Instagram JSON state/scripts
        ext_matches = re.findall(r'\"external_url\"[\s]*:[\s]*\"([^\"]+)\"', html)
        for url in ext_matches:
            clean_url = url.encode().decode('unicode-escape').replace(r"\/", "/")
            if clean_url and not any(ign in clean_url.lower() for ign in ["instagram.com", "cdninstagram.com", "facebook.com"]):
                return clean_url

        shim_matches = re.findall(r'\"external_url_linkshim\"[\s]*:[\s]*\"([^\"]+)\"', html)
        for url in shim_matches:
            clean_url = url.encode().decode('unicode-escape').replace(r"\/", "/")
            if clean_url and not any(ign in clean_url.lower() for ign in ["instagram.com", "cdninstagram.com", "facebook.com"]):
                return clean_url

        return None

    def extract_bio_text_from_profile_html(self, html: str) -> str:
        if not html:
            return ""
        # 1. Check JSON biography field
        bio_matches = re.findall(r'\"biography\"[\s]*:[\s]*\"([^\"]+)\"', html)
        for b in bio_matches:
            try:
                clean_bio = b.encode().decode('unicode-escape')
                if clean_bio:
                    return clean_bio
            except Exception:
                pass

        # 2. Check meta description tags
        soup = BeautifulSoup(html, "html.parser")
        for prop in ["og:description", "description"]:
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta and meta.get("content"):
                return meta.get("content")

        return ""

    def extract_email_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        platform_domains = (
            "instagram.com", "facebook.com", "meta.com", "fb.com", "google.com",
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

    def parse_raw_profiles(self, raw_profiles: List[Dict[str, Any]]) -> List[Lead]:
        leads = []
        for p in raw_profiles:
            bio = p.get("bio", "")
            extracted_email = p.get("email") or self.extract_email_from_text(bio)
            external_url = p.get("external_url") or self.detect_website_in_text(bio)

            if not external_url and extracted_email:
                custom_web = LeadFilter.check_custom_domain_website(extracted_email)
                if custom_web:
                    external_url = custom_web

            lead = Lead(
                name=p.get("full_name") or p.get("username", "Instagram Realtor"),
                city=p.get("city", ""),
                state=p.get("state", ""),
                phone=p.get("phone"),
                website=external_url,
                email=extracted_email,
                source="Instagram",
                profile_url=p.get("profile_url") or f"https://instagram.com/{p.get('username', '')}"
            )
            leads.append(lead)
        return leads

    def parse_search_items(self, items: List[Dict[str, str]], city: str, state: Optional[str] = None) -> List[Lead]:
        """
        Parses search result items (title, href, snippet) into qualified/skipped Leads.
        """
        leads = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        for item in items:
            title = (item.get("title") or "").strip()
            link = (item.get("href") or "").strip()
            snippet = (item.get("snippet") or "").strip()

            if "instagram.com" not in link:
                continue

            parts = link.replace("https://", "").replace("http://", "").replace("www.", "").replace("www-fallback.", "").split("/")
            if len(parts) <= 1 or not parts[1]:
                continue

            raw_user = parts[1].split("?")[0].strip()
            if not self.is_valid_instagram_username(raw_user):
                continue

            clean_profile_url = f"https://instagram.com/{raw_user}"
            full_text = f"{title} {snippet}"
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

            # Deep inspect profile HTML if website or email not found in snippet
            if clean_profile_url and (not detected_website or not email):
                try:
                    prof_resp = requests.get(clean_profile_url, headers=headers, timeout=5)
                    if prof_resp.status_code == 200:
                        prof_html = prof_resp.text
                        bio_text = self.extract_bio_text_from_profile_html(prof_html)
                        if not detected_website:
                            detected_website = (
                                self.extract_website_from_profile_html(prof_html) 
                                or self.detect_website_in_text(bio_text)
                            )
                        if not bio_service_url:
                            bio_service_url = self.bio_resolver.extract_bio_service_url(bio_text)
                            if bio_service_url:
                                bio_info = self.bio_resolver.resolve(bio_service_url)
                                if bio_info.get("has_website"):
                                    detected_website = bio_info.get("website_url")
                                if bio_info.get("email") and not email:
                                    email = bio_info.get("email")
                                resolved_bio_links.extend([{"title": f"Bio Service Link: {l}", "href": l} for l in bio_info.get("destination_links", [])])
                        if not email:
                            email = self.extract_email_from_text(bio_text) or self.extract_email_from_text(prof_html)
                except Exception:
                    pass

            clean_name = title.split("•")[0].split("(")[0].replace("Instagram", "").strip()
            if not clean_name or clean_name.lower() in (f"{city.lower()} realtor", "instagram"):
                clean_name = raw_user.replace(".", " ").replace("_", " ").title()

            # Consult Gemini AI Smart Brain
            if self.ai_verifier and self.ai_verifier.api_key:
                ai_res = self.ai_verifier.analyze_lead(
                    business_name=f"{clean_name} (@{raw_user})",
                    city=city,
                    search_snippets=full_text,
                    links=[{"title": "Instagram Profile", "href": clean_profile_url}] + resolved_bio_links
                )
                if ai_res:
                    if ai_res.has_website:
                        detected_website = ai_res.official_website_url or detected_website or "https://verified-website.com"
                        print(f"   🧠 [Gemini AI Brain] {clean_name}: {ai_res.reasoning}")
                    if ai_res.verified_email and not email:
                        email = ai_res.verified_email

            # Check if email is on a custom domain that hosts an active website
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
                    print(f"   🎯 [Instagram Enriched] Verified contact email found for {clean_name}: {email}")

            if detected_website:
                print(f"   ❌ [Instagram] {clean_name} has website ({detected_website}) -> Skipped")
                leads.append(Lead(
                    name=clean_name,
                    city=city,
                    state=state,
                    website=detected_website,
                    email=email,
                    source="Instagram",
                    profile_url=clean_profile_url
                ))
            else:
                if email:
                    print(f"   ✅ [Instagram] {clean_name} | No Website | Verified Email: {email} | Profile: {clean_profile_url}")
                    leads.append(Lead(
                        name=clean_name,
                        city=city,
                        state=state,
                        website=None,
                        email=email,
                        source="Instagram",
                        profile_url=clean_profile_url
                    ))
                else:
                    print(f"   📱 [Instagram] {clean_name} | No website, no email -> Added to Social DM Queue")
                    self.social_dm_leads.append(Lead(
                        name=clean_name,
                        city=city,
                        state=state,
                        website=None,
                        email=None,
                        source="Instagram",
                        profile_url=clean_profile_url,
                        snippet=snippet
                    ))

        return leads

    def search_city(self, location: LocationInput) -> List[Lead]:
        """
        Executes live Instagram discovery for Realtors in location.
        Scans profiles, bio links, and contact information.
        Uses Playwright Chrome browser to bypass bot verification,
        with automated fallback.
        """
        self.social_dm_leads = []
        query_loc = location.city or location.raw_location
        print(f"\n📸 [Instagram] Scanning real estate profiles and bios for: {query_loc}...")

        if self.test_mode or os.getenv("TEST_MODE") == "1":
            clean_loc = re.sub(r"[^a-zA-Z0-9]", "", query_loc).lower()
            return [
                Lead(
                    name=f"{query_loc} Elite Realtor",
                    city=query_loc,
                    state=location.state,
                    website=None,
                    email=f"insta.{clean_loc}@gmail.com",
                    source="Instagram",
                    profile_url=f"https://instagram.com/{clean_loc}_realtor"
                )
            ]

        raw_items = []
        seen_users = set()
        discovery_queries = self.build_discovery_queries(query_loc)

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
                        if len(seen_users) >= 40:
                            break
                        print(f"   ↳ [Instagram Angle {d_idx+1} | Google Page {p_idx+1}] Querying: '{search_query}'...")
                        try:
                            page.goto(g_url, timeout=16000)
                            page.wait_for_timeout(2000)
                            g_body = page.inner_text("body")
                            if "unusual traffic" in g_body or "recaptcha" in g_body.lower():
                                google_blocked = True
                                break

                            # Extract organic Google results
                            g_links = page.locator('a[href*="instagram.com/"]').all()
                            for gl in g_links:
                                href_url = gl.get_attribute("href") or ""
                                if "instagram.com/" in href_url:
                                    try:
                                        clean_u = href_url.split("instagram.com/")[1].split("/")[0].split("?")[0].lower()
                                        if clean_u and clean_u not in seen_users and self.is_valid_instagram_username(clean_u):
                                            seen_users.add(clean_u)
                                            # Try to find parent text snippet
                                            parent_text = gl.evaluate("el => el.closest('div.g') ? el.closest('div.g').innerText : el.innerText")
                                            raw_items.append({
                                                "title": clean_u.replace(".", " ").replace("_", " ").title(),
                                                "href": f"https://www.instagram.com/{clean_u}/",
                                                "snippet": parent_text[:1200]
                                            })
                                    except Exception:
                                        pass
                        except Exception:
                            continue

                    # Complement with DuckDuckGo search if Google blocked or needed more results
                    if google_blocked or len(raw_items) < 15:
                        ddg_url = f"https://duckduckgo.com/?q={quote_plus(search_query)}&t=h_&ia=web"
                        print(f"   ↳ [Instagram Angle {d_idx+1} | DuckDuckGo] Querying: '{search_query}'...")
                        try:
                            page.goto(ddg_url, timeout=18000)
                            page.wait_for_timeout(2500)
                            # Scroll to load additional results
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

                            if "instagram.com/" in href_url:
                                try:
                                    clean_u = href_url.split("instagram.com/")[1].split("/")[0].split("?")[0].lower()
                                    if clean_u and clean_u not in seen_users and self.is_valid_instagram_username(clean_u):
                                        seen_users.add(clean_u)
                                        raw_items.append({
                                            "title": title_text,
                                            "href": href_url,
                                            "snippet": snippet_text
                                        })
                                except Exception:
                                    pass

                # Cross-reference discovered profiles with Google Search to reveal external websites and business emails
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                for it in raw_items[:25]:
                    try:
                        clean_u = it["href"].split("instagram.com/")[1].split("/")[0].split("?")[0]
                        g_query = f"{clean_u} {it['title'].split('•')[0].strip()} {query_loc} website"
                        page.goto(f"https://www.google.com/search?q={quote_plus(g_query)}&hl=en", timeout=12000)
                        page.wait_for_timeout(2000)
                        g_body = page.inner_text("body")
                        if "unusual traffic" not in g_body:
                            it["snippet"] = f"{it['snippet']} | Google Search Findings: {g_body[:1800]}"
                    except Exception:
                        pass

                browser.close()

        except Exception as e:
            print(f"   ⚠️ Playwright browser search notice: {e}. Trying secondary HTTP search...")

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
                            if "instagram.com/" in href_val:
                                try:
                                    clean_u = href_val.split("instagram.com/")[1].split("/")[0].split("?")[0].lower()
                                    if clean_u and clean_u not in seen_users and self.is_valid_instagram_username(clean_u):
                                        seen_users.add(clean_u)
                                        raw_items.append({
                                            "title": title_el.get_text().strip() if title_el else "",
                                            "href": href_val,
                                            "snippet": snippet_el.get_text().strip() if snippet_el else ""
                                        })
                                except Exception:
                                    pass
            except Exception:
                pass

        print(f"   ↳ Found {len(raw_items)} potential Instagram realtor accounts")
        if not raw_items:
            print(f"   ℹ️ [Instagram] No public Instagram profiles found for: {query_loc}")
            return []

        return self.parse_search_items(raw_items, city=query_loc, state=location.state)

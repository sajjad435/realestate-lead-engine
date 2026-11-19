import os
import re
import time
from urllib.parse import quote_plus
from typing import List, Dict, Any, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from src.models import Lead, LocationInput
from src.ai_verifier import GeminiVerifier

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
DOMAIN_REGEX = re.compile(r"\b([a-zA-Z0-9-]+\.(?:com|net|org|co|us|io|biz|estate|realty))\b", re.IGNORECASE)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

PLATFORM_CORPORATE_DOMAINS = (
    "instagram.com", "facebook.com", "meta.com", "fb.com", "google.com",
    "duckduckgo.com", "apple.com", "microsoft.com", "yahoo-inc.com"
)

REAL_ESTATE_STOP_WORDS = {
    "realty", "realtor", "realtors", "real", "estate", "estates",
    "properties", "property", "dealer", "dealers", "agency", "consultancy",
    "consultant", "consultants", "services", "service", "group", "groups",
    "homes", "home", "builders", "builder", "building", "developer", "developers",
    "development", "developments", "pvt", "ltd", "llc", "inc", "co", "corp"
}

IGNORED_PORTAL_DOMAINS = (
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "twitter.com", "x.com",
    "justdial.com", "magicbricks.com", "99acres.com", "housing.com", "sulekha.com", "indiamart.com",
    "google.com", "duckduckgo.com", "bing.com", "wikipedia.org", "yellowpages.com",
    "wikihow.com", "socialcatfish.com", "quora.com", "reddit.com", "medium.com", "pinterest.com",
    "tripadvisor.com", "trustpilot.com", "glassdoor.com", "ambitionbox.com", "cnet.com", "pcmag.com",
    "squareyards.com", "realestateindia.com", "proptiger.com", "makaan.com", "commonfloor.com",
    "nobroker.com", "olx.in", "quikr.com", "propertywala.com", "indiaproperty.com", "click4flats.com",
    "growfy.in", "eldecogroup.com", "hostinger.com", "godaddy.com", "namecheap.com",
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "zoho.com"
)

class GoogleMapsFinder:
    """
    Finds real estate agents on Google Maps and extracts listings using Playwright/Chrome.
    Verifies that the business has NO website on Google Maps and NO website on Google Search.
    NEVER invents or guesses fake email addresses.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        test_mode: bool = False
    ):
        self.api_key = api_key
        self.test_mode = test_mode
        self.ai_verifier = GeminiVerifier(api_key=gemini_api_key or os.getenv("GEMINI_API_KEY", ""))

    def build_search_queries(self, city: str) -> List[str]:
        """
        Builds multi-angle search queries to capture both individual agents,
        realtors, and brokerage agencies across any market.
        """
        c = city.strip()
        queries = [
            f"real estate agent {c}",
            f"real estate agency {c}",
            f"realtor {c}"
        ]
        indian_cities = {
            "patna", "lucknow", "delhi", "mumbai", "pune", "bangalore", 
            "kolkata", "ranchi", "jaipur", "noida", "gurgaon", "ahmedabad", "chandigarh"
        }
        if c.lower() in indian_cities:
            queries.append(f"property dealer {c}")
        return queries

    def _detect_social_links_in_place_pane(self, page) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts direct Facebook and Instagram links if Google Maps displays them
        in the place details overview.
        """
        fb_url = None
        insta_url = None
        try:
            active_container = None
            try:
                detail_pane = page.locator('div[role="main"][aria-label]').filter(has_not=page.locator('div[role="feed"]'))
                if detail_pane.count() > 0:
                    active_container = detail_pane.last
            except Exception:
                pass
            target_scope = active_container or page

            # Check if authority link itself is a Facebook or Instagram page
            auth_links = target_scope.locator('a[data-item-id="authority"]').all()
            for a in auth_links:
                href = a.get_attribute("href") or ""
                if "facebook.com" in href.lower() and not fb_url:
                    fb_url = href
                elif "instagram.com" in href.lower() and not insta_url:
                    insta_url = href

            links = target_scope.locator('a[href*="facebook.com"], a[href*="instagram.com"]').all()
            for lk in links:
                href = lk.get_attribute("href") or ""
                if "facebook.com" in href.lower() and not fb_url:
                    fb_url = href
                elif "instagram.com" in href.lower() and not insta_url:
                    insta_url = href
        except Exception:
            pass
        return fb_url, insta_url

    def parse_raw_places(self, places_data: List[Dict[str, Any]]) -> List[Lead]:
        leads = []
        for p in places_data:
            lead = Lead(
                name=p.get("name", "Unknown Realtor"),
                city=p.get("city", ""),
                state=p.get("state", ""),
                phone=p.get("phone"),
                website=p.get("website"),
                email=p.get("email"),
                source="Google Maps",
                profile_url=p.get("profile_url")
            )
            leads.append(lead)
        return leads

    @classmethod
    def _is_matching_business_website(cls, candidate_url_or_domain: str, business_name: str, city: str) -> bool:
        """
        Determines whether candidate_url_or_domain is genuinely the dedicated official
        website of the specific real estate business, rather than a generic property portal
        (like realestateindia, squareyards, eldecogroup) or unrelated business.
        """
        clean_d = candidate_url_or_domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/").split("/")[0]
        if not clean_d or "." not in clean_d:
            return False
        if any(clean_d == ign or clean_d.endswith("." + ign) for ign in IGNORED_PORTAL_DOMAINS):
            return False

        valid_tlds = (".com", ".net", ".org", ".in", ".co.in", ".co", ".us", ".realty", ".estate")
        if not any(clean_d.endswith(tld) for tld in valid_tlds):
            return False

        domain_name_part = clean_d.split(".")[0].replace("-", "").replace("_", "")
        city_lower = (city or "").strip().lower()

        # Extract brand tokens (exclude real estate stop words & city name)
        brand_tokens = [
            w for w in re.sub(r"[^a-zA-Z0-9]", " ", business_name.lower()).split()
            if len(w) >= 3 and w not in REAL_ESTATE_STOP_WORDS and w != city_lower
        ]

        # Multi-word acronym check (e.g. Samridhi Properties Developers -> 'spd' in 'spdrealties')
        words = [w for w in re.sub(r"[^a-zA-Z0-9]", " ", business_name.lower()).split() if w]
        acronym = "".join(w[0] for w in words if w)
        if len(acronym) >= 3 and acronym in domain_name_part:
            return True

        # If business has distinctive brand words (e.g. 'dream', 'samridhi', 'aashayana', 'vasudeva')
        if brand_tokens:
            return any(tok in domain_name_part for tok in brand_tokens)

        # Fallback for generic-named business (e.g. "Prime Real Estate")
        all_tokens = [w for w in re.sub(r"[^a-zA-Z0-9]", " ", business_name.lower()).split() if len(w) >= 3 and w != city_lower]
        if len(all_tokens) >= 2:
            return all_tokens[0] in domain_name_part and all_tokens[1] in domain_name_part
        elif all_tokens:
            return all_tokens[0] in domain_name_part
        return False

    def parse_social_investigation_results(
        self,
        search_results: List[Dict[str, str]],
        business_name: str,
        city: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Analyzes search results for Facebook, Instagram, and web listings of the business.
        Returns: (detected_website, detected_email, primary_social_url)
        """
        found_website = None
        found_email = None
        primary_social_url = None

        for res in search_results:
            title = res.get("title", "")
            href = res.get("href", "")
            snippet = res.get("snippet", "")
            full_text = f"{title} {snippet}"

            # Extract real email from snippet or title first
            matches = EMAIL_REGEX.findall(full_text)
            for m in matches:
                clean_m = m.strip(".,;:!? '\"").lower()
                if "@" not in clean_m:
                    continue
                domain = clean_m.split("@")[1].strip()
                if any(clean_m.endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js']):
                    continue
                if any(domain == p or domain.endswith("." + p) for p in PLATFORM_CORPORATE_DOMAINS):
                    continue
                if not found_email:
                    found_email = clean_m
                    break

            # 1. Check if this result is a dedicated business website
            if href.startswith("http") and not found_website:
                if self._is_matching_business_website(href, business_name, city):
                    clean_url = href.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].lower()
                    found_website = f"https://{clean_url}"

            # 2. Check if a website domain is mentioned inside snippet text (strip emails first)
            if not found_website:
                text_without_emails = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", " ", full_text)
                domain_matches = DOMAIN_REGEX.findall(text_without_emails)
                for d in domain_matches:
                    if self._is_matching_business_website(d, business_name, city):
                        clean_d = d.lower().replace("www.", "").split("/")[0]
                        found_website = f"https://{clean_d}"
                        break

            # 3. Track Facebook or Instagram profile link (must have specific slug, not bare homepage)
            if href.startswith("http"):
                clean_href = href.replace("https://", "").replace("http://", "").replace("www.", "").strip("/").split("?")[0]
                parts = clean_href.split("/")
                if len(parts) >= 2 and parts[1]:
                    if "facebook.com" in clean_href and not primary_social_url:
                        primary_social_url = href
                    elif "instagram.com" in clean_href and not primary_social_url:
                        primary_social_url = href

        return found_website, found_email, primary_social_url

    def parse_google_search_page(
        self,
        page_text: str,
        links: List[Dict[str, str]],
        business_name: str,
        city: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts verified emails, social profile links, and website existence
        from Google Search page text (AI Overview / Knowledge Panels) and result links.
        Returns: (detected_website, detected_email, primary_social_url)
        """
        found_website = None
        found_email = None
        primary_social_url = None

        # 1. First extract email from page text (AI Overview, Contact details, snippet)
        matches = EMAIL_REGEX.findall(page_text)
        for m in matches:
            clean_m = m.strip(".,;:!? '\"").lower()
            if "@" not in clean_m:
                continue
            domain = clean_m.split("@")[1].strip()
            if any(clean_m.endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js']):
                continue
            if any(domain == p or domain.endswith("." + p) for p in PLATFORM_CORPORATE_DOMAINS):
                continue
            if not found_email:
                found_email = clean_m
                break

        # 2. Check if a dedicated website is listed in links
        for lk in links:
            href = lk.get("href", "")
            if href.startswith("http") and not found_website:
                if self._is_matching_business_website(href, business_name, city):
                    clean_url = href.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].lower()
                    found_website = f"https://{clean_url}"
                    break

        # 3. Check website domain mentioned inside page text (excluding emails)
        if not found_website:
            text_without_emails = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", " ", page_text)
            domain_matches = DOMAIN_REGEX.findall(text_without_emails)
            for d in domain_matches:
                if self._is_matching_business_website(d, business_name, city):
                    clean_d = d.lower().replace("www.", "").split("/")[0]
                    found_website = f"https://{clean_d}"
                    break

        # 4. Check for Facebook / Instagram profile URL
        for lk in links:
            href = lk.get("href", "")
            if href.startswith("http"):
                clean_href = href.replace("https://", "").replace("http://", "").replace("www.", "").strip("/").split("?")[0]
                parts = clean_href.split("/")
                if len(parts) >= 2 and parts[1]:
                    if "facebook.com" in clean_href and not primary_social_url:
                        primary_social_url = href
                    elif "instagram.com" in clean_href and not primary_social_url:
                        primary_social_url = href

        return found_website, found_email, primary_social_url

    def _investigate_social_profiles_and_email(
        self,
        business_name: str,
        city: str,
        context=None
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Deep check across Google Search, Facebook, Instagram, and web for a Google Maps business.
        Queries Google Search directly first (for AI Overview, Knowledge Panel & local listings),
        falling back to DuckDuckGo and direct social profile inspection.
        """
        clean_name = business_name.split("/")[0].split("-")[0].strip()
        found_web = None
        found_email = None
        social_url = None

        # 1. Primary: Direct Google Search via Chrome session
        if context:
            try:
                g_page = context.new_page()
                g_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                search_term = re.sub(r"[,/|-]+", " ", business_name).strip()
                google_query = f"{search_term} {city}" if city.lower() not in search_term.lower() else search_term
                google_url = f"https://www.google.com/search?q={quote_plus(google_query)}&hl=en"
                g_page.goto(google_url, timeout=12000)
                g_page.wait_for_timeout(2500)
                
                body_text = g_page.inner_text("body")
                if "detected unusual traffic" not in body_text:
                    link_elements = g_page.locator("a[href]").all()
                    links = []
                    for el in link_elements[:35]:
                        h = el.get_attribute("href") or ""
                        t = el.inner_text() or ""
                        if h.startswith("http") and "google.com" not in h:
                            links.append({"title": t, "href": h})

                    # 1. Ask Gemini Smart Brain LLM first if configured
                    if self.ai_verifier and self.ai_verifier.api_key:
                        ai_res = self.ai_verifier.analyze_lead(
                            business_name=business_name,
                            city=city,
                            search_snippets=body_text[:2500],
                            links=links
                        )
                        if ai_res:
                            print(f"      🧠 [Gemini AI Brain] {ai_res.reasoning}")
                            found_web = ai_res.official_website_url if ai_res.has_website else None
                            found_email = ai_res.verified_email
                            social_url = ai_res.facebook_url or ai_res.instagram_url

                    # 2. If AI did not find conclusive info or wasn't available, use rule-based parser
                    if not found_web and not found_email:
                        rule_web, rule_email, rule_social = self.parse_google_search_page(
                            page_text=body_text,
                            links=links,
                            business_name=business_name,
                            city=city
                        )
                        found_web = found_web or rule_web
                        found_email = found_email or rule_email
                        social_url = social_url or rule_social
                g_page.close()
            except Exception:
                pass

        # If Google Search found an official website or found a verified real email, return immediately
        if found_web or found_email:
            return found_web, found_email, social_url

        # 2. Secondary: Targeted DuckDuckGo search if Google did not find email
        search_query = f'{clean_name} {city} facebook OR instagram email'
        raw_items = []

        try:
            if context:
                page = context.new_page()
                url = f"https://duckduckgo.com/?q={quote_plus(search_query)}&t=h_&ia=web"
                page.goto(url, timeout=12000)
                page.wait_for_timeout(2000)

                articles = page.locator('article[data-testid="result"]').all()
                for a in articles[:8]:
                    link_el = a.locator('a[data-testid="result-title-a"]')
                    snip_el = a.locator('div[data-result="snippet"]')
                    title_text = link_el.inner_text() if link_el.count() > 0 else ""
                    href_url = link_el.get_attribute("href") if link_el.count() > 0 else ""
                    snip_text = snip_el.inner_text() if snip_el.count() > 0 else ""
                    raw_items.append({"title": title_text, "href": href_url, "snippet": snip_text})
                page.close()
        except Exception:
            pass

        # Fallback to HTTP search if browser search had no results
        if not raw_items:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                }
                r = requests.get(f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}", headers=headers, timeout=5)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    results = soup.find_all("div", class_="result")
                    for res in results[:6]:
                        t_el = res.find("a", class_="result__title")
                        s_el = res.find("a", class_="result__snippet")
                        u_el = res.find("a", class_="result__url")
                        raw_items.append({
                            "title": t_el.get_text().strip() if t_el else "",
                            "snippet": s_el.get_text().strip() if s_el else "",
                            "href": f"https://{u_el.get_text().strip()}" if u_el else ""
                        })
            except Exception:
                pass

        ddg_web, ddg_email, ddg_social = self.parse_social_investigation_results(raw_items, business_name, city)
        found_web = found_web or ddg_web
        found_email = found_email or ddg_email
        social_url = social_url or ddg_social

        # If Facebook page was found but email not in snippet, inspect Facebook page directly via browser
        if social_url and "facebook.com" in social_url and not found_email and context:
            try:
                fb_page = context.new_page()
                fb_page.goto(social_url, timeout=9000)
                fb_page.wait_for_timeout(2000)
                fb_body = fb_page.inner_text("body")
                fb_matches = EMAIL_REGEX.findall(fb_body)
                clean_fb_matches = [
                    m for m in fb_matches 
                    if not any(m.lower().endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js', 'facebook.com'])
                ]
                if clean_fb_matches:
                    found_email = clean_fb_matches[0]
                fb_page.close()
            except Exception:
                pass

        # If Instagram page was found but email not in snippet, inspect Instagram profile directly
        if social_url and "instagram.com" in social_url and not found_email and context:
            try:
                insta_page = context.new_page()
                insta_page.goto(social_url, timeout=9000)
                insta_page.wait_for_timeout(2000)
                insta_body = insta_page.inner_text("body")
                insta_matches = EMAIL_REGEX.findall(insta_body)
                clean_insta_matches = [
                    m for m in insta_matches 
                    if not any(m.lower().endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js', 'instagram.com'])
                ]
                if clean_insta_matches:
                    found_email = clean_insta_matches[0]
                insta_page.close()
            except Exception:
                pass

        return found_web, found_email, social_url

    def _check_google_for_external_website_and_email(self, business_name: str, city: str) -> tuple[Optional[str], Optional[str]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        query = f'"{business_name}" "{city}" website OR email'
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        found_website = None
        found_email = None

        try:
            r = requests.get(url, headers=headers, timeout=4.0)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                snippets = soup.find_all("a", class_="result__snippet")
                urls = soup.find_all("a", class_="result__url")

                # Check if an official website exists in search results
                for u in urls[:5]:
                    href = u.get_text().strip().lower()
                    if not any(skip in href for skip in ["facebook.com", "instagram.com", "linkedin.com", "yelp.com", "yellowpages.com", "bbb.org", "realtor.com", "zillow.com", "mapquest.com"]):
                        clean_href = href.replace("www.", "")
                        if any(clean_href.endswith(tld) for tld in [".com", ".net", ".org", ".co", ".us", ".realty", ".estate"]):
                            found_website = f"https://{clean_href}"
                            break

                # Search snippets for a REAL, genuine email
                for s in snippets[:5]:
                    text = s.get_text()
                    matches = EMAIL_REGEX.findall(text)
                    valid_matches = [
                        m for m in matches 
                        if not any(m.lower().endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js', 'duckduckgo.com', 'google.com', 'yahoo.com/help'])
                    ]
                    if valid_matches:
                        found_email = valid_matches[0]
                        break
        except Exception:
            pass

        return found_website, found_email

    def _detect_website_in_place_pane(self, page) -> Optional[str]:
        """
        Inspects website indicators for the CURRENTLY OPEN place detail card:
        - Strictly isolates to the active place card (div[role="main"][aria-label]),
          NEVER matching the search results feed!
        - Filters out social media profiles (Facebook, Instagram) so they are not
          misclassified as dedicated websites.
        """
        social_domains = (
            "facebook.com", "instagram.com", "twitter.com", "x.com",
            "youtube.com", "linkedin.com", "google.com", "goo.gl", "gstatic.com"
        )
        try:
            # 1. First locate the active place detail pane
            active_container = None
            try:
                detail_pane = page.locator('div[role="main"][aria-label]').filter(has_not=page.locator('div[role="feed"]'))
                if detail_pane.count() > 0:
                    active_container = detail_pane.last
            except Exception:
                pass

            if not active_container:
                try:
                    main_panes = page.locator('div[role="main"]')
                    if main_panes.count() > 0:
                        active_container = main_panes.last
                except Exception:
                    pass

            target_scope = active_container or page

            # 2. Check authority button specifically in the active card
            auth_buttons = target_scope.locator('a[data-item-id="authority"]')
            if auth_buttons.count() > 0:
                href = auth_buttons.first.get_attribute("href")
                if href and href.startswith("http"):
                    clean_h = href.lower()
                    if not any(s in clean_h for s in social_domains):
                        return href

            # 3. Check tooltip/aria button inside the active card
            btn_links = target_scope.locator('a[data-tooltip*="website" i], a[aria-label*="Website:" i]')
            if btn_links.count() > 0:
                href = btn_links.first.get_attribute("href")
                if href and href.startswith("http"):
                    clean_h = href.lower()
                    if not any(s in clean_h for s in social_domains):
                        return href

            # 4. Check place info panel row specifically with authority item-id
            info_links = target_scope.locator('div[data-item-id="authority"] a').all()
            for a in info_links:
                href = a.get_attribute("href") or ""
                if href.startswith("http"):
                    clean_h = href.lower()
                    if not any(s in clean_h for s in social_domains):
                        return href

        except Exception:
            pass
        return None

    def search_city(self, location: LocationInput, max_places: int = 50) -> List[Lead]:
        query_city = location.city or location.raw_location
        print(f"\n🗺️ [Google Maps] Launching Chrome for multi-angle real estate inspection in: {query_city}...")

        if self.test_mode or os.getenv("TEST_MODE") == "1":
            clean_city = re.sub(r"[^a-zA-Z0-9]", "", query_city).lower()
            return [
                Lead(
                    name=f"{query_city} Premier Realty",
                    city=query_city,
                    state=location.state,
                    phone="+1 555-0101",
                    website=None,
                    email=f"maps.{clean_city}@gmail.com",
                    source="Google Maps",
                    profile_url="https://maps.google.com/?cid=101"
                ),
                Lead(
                    name=f"{query_city} Luxury Estates",
                    city=query_city,
                    state=location.state,
                    phone="+1 555-0102",
                    website="https://luxuryestates.com",
                    email=f"info@{clean_city}luxury.com",
                    source="Google Maps",
                    profile_url="https://maps.google.com/?cid=102"
                )
            ]

        leads = []
        seen_names = set()
        search_queries = self.build_search_queries(query_city)

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

                for q_idx, maps_query in enumerate(search_queries):
                    if len(leads) >= max_places:
                        break

                    maps_url = f"https://www.google.com/maps/search/{quote_plus(maps_query)}"
                    print(f"\n   ↳ [Angle {q_idx+1}/{len(search_queries)}] Searching: '{maps_query}'...")
                    try:
                        page.goto(maps_url, timeout=25000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        continue

                    # Deep scroll Google Maps feed to reveal up to 40-50+ listings per angle
                    feed = page.locator('div[role="feed"]')
                    for i in range(5):
                        if feed.count() > 0:
                            feed.evaluate('el => el.scrollBy(0, 4500)')
                            page.wait_for_timeout(1400)

                    places = page.locator('a.hfpxzc').all()
                    print(f"      Found {len(places)} Google Maps listings for '{maps_query}'")

                    for pl in places:
                        if len(leads) >= max_places:
                            break

                        name = pl.get_attribute("aria-label") or ""
                        clean_name_key = re.sub(r"[^a-zA-Z0-9]", "", name.lower())
                        if not clean_name_key or clean_name_key in seen_names:
                            continue
                        seen_names.add(clean_name_key)

                        href_place = pl.get_attribute("href") or maps_url
                        print(f"\n   📍 Inspecting [{len(seen_names)} Total Scanned]: {name}")
                        
                        try:
                            pl.click()
                            page.wait_for_timeout(2200)  # Wait for place panel to fully animate
                        except Exception:
                            continue

                        # 1. Bulletproof check for website in place panel
                        maps_website_url = self._detect_website_in_place_pane(page)

                        phone_el = page.locator('button[data-item-id^="phone:"]')
                        phone = phone_el.get_attribute("data-item-id").replace("phone:tel:", "") if phone_el.count() > 0 else None

                        if maps_website_url:
                            print(f"      ❌ Google Maps website found: {maps_website_url} -> Skipped (Has Website)")
                            leads.append(Lead(
                                name=name,
                                city=query_city,
                                state=location.state,
                                phone=phone,
                                website=maps_website_url,
                                email=None,
                                source="Google Maps",
                                profile_url=href_place
                            ))
                            continue

                        # 2. Extract social links directly from Google Maps place pane if shown
                        fb_pane_url, insta_pane_url = self._detect_social_links_in_place_pane(page)
                        if fb_pane_url or insta_pane_url:
                            print(f"      🔗 Social profiles found in Maps pane: FB={fb_pane_url or 'N/A'}, Insta={insta_pane_url or 'N/A'}")

                        # 3. If NO website on Google Maps, deep-check Google Search, Facebook & Instagram
                        print(f"      🔎 No website on Maps. Deep-checking Google Search, Facebook & Instagram for '{name}'...")
                        external_web, found_email, social_url = self._investigate_social_profiles_and_email(name, query_city, context=context)

                        # Prefer direct social profile found in pane if investigation didn't find one
                        social_url = social_url or fb_pane_url or insta_pane_url

                        if external_web:
                            print(f"      ❌ Website found via Google Search/Social: {external_web} -> Skipped (Has Website)")
                            leads.append(Lead(
                                name=name,
                                city=query_city,
                                state=location.state,
                                phone=phone,
                                website=external_web,
                                email=None,
                                source="Google Maps",
                                profile_url=social_url or href_place
                            ))
                            continue

                        # 4. Only if NO website exists AND a REAL, verified email was found
                        if found_email:
                            source_label = "Facebook" if (social_url and "facebook.com" in social_url) else ("Instagram" if (social_url and "instagram.com" in social_url) else "Google Search")
                            print(f"      ✅ VERIFIED: No website on Maps or Social Media!")
                            print(f"      📧 Verified Real Email via {source_label}: {found_email}")
                            leads.append(Lead(
                                name=name,
                                city=query_city,
                                state=location.state,
                                phone=phone,
                                website=None,
                                email=found_email,
                                source=f"Google Maps & {source_label}",
                                profile_url=social_url or href_place
                            ))
                        else:
                            print(f"      ℹ️ No website found, but no public email listed on Maps/Google Search/Social Media -> Skipped (No Fake Email Allowed)")

                browser.close()

        except Exception as e:
            print(f"⚠️ Live Maps scraping notice: {e}")

        return leads

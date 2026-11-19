import re
from typing import Optional, Dict, Any, List
import requests
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

class BioLinkResolver:
    """
    Detects and inspects multi-link bio services (Linktree, Beacons, Lnk.bio, etc.)
    used by real estate agents. Traverses all destination links inside to verify
    whether the agent actually has an official dedicated website or only social profiles.
    """
    BIO_SERVICES = [
        "linktr.ee", "beacons.ai", "campsite.bio", "tap.bio", "solo.to",
        "linkin.bio", "lnk.bio", "bio.site", "snipfeed.co", "stan.store"
    ]

    IGNORED_DESTINATIONS = (
        "linktr.ee", "beacons.ai", "campsite.bio", "tap.bio", "solo.to",
        "linkin.bio", "lnk.bio", "bio.site", "snipfeed.co", "stan.store",
        "instagram.com", "facebook.com", "fb.com", "threads.net", "twitter.com",
        "x.com", "tiktok.com", "youtube.com", "linkedin.com", "spotify.com",
        "apple.com", "pinterest.com", "snapchat.com", "whatsapp.com", "wa.me",
        "calendly.com", "google.com", "maps.google.com", "goo.gl", "bit.ly"
    )

    def extract_bio_service_url(self, text: str) -> Optional[str]:
        if not text:
            return None

        # Check for URLs with or without http(s)
        for service in self.BIO_SERVICES:
            pattern = rf"(?:https?://)?(?:www\.)?({re.escape(service)}/[a-zA-Z0-9_.-]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                full_slug = match.group(1).strip()
                return f"https://{full_slug}"
        return None

    def resolve(self, bio_url: str) -> Dict[str, Any]:
        """
        Visits the Linktree / bio-link page and inspects all destination links and email addresses.
        """
        result: Dict[str, Any] = {
            "has_website": False,
            "website_url": None,
            "email": None,
            "destination_links": []
        }

        if not bio_url:
            return result

        clean_url = bio_url if bio_url.startswith("http") else f"https://{bio_url}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:
            resp = requests.get(clean_url, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                html = resp.text
                soup = BeautifulSoup(html, "html.parser")

                # 1. Search for mailto: or email in text
                mailto_links = soup.find_all("a", href=re.compile(r"^mailto:", re.I))
                for m in mailto_links:
                    href = m.get("href", "")
                    clean_email = href.replace("mailto:", "").split("?")[0].strip()
                    if "@" in clean_email:
                        result["email"] = clean_email
                        break

                if not result["email"]:
                    text_emails = EMAIL_REGEX.findall(html)
                    valid_emails = [
                        e.strip(".,;:!? '\"") for e in text_emails 
                        if not any(e.lower().endswith(bad) for bad in ['.png', '.jpg', '.webp', '.js', 'linktr.ee', 'beacons.ai'])
                    ]
                    if valid_emails:
                        result["email"] = valid_emails[0]

                # 2. Inspect outbound destination links
                anchors = soup.find_all("a", href=True)
                for a in anchors:
                    href = a["href"].strip()
                    if not href.startswith("http"):
                        continue

                    lower_href = href.lower()
                    if any(ign in lower_href for ign in self.IGNORED_DESTINATIONS):
                        continue

                    # Potential official agency website found
                    result["destination_links"].append(href)
                    if not result["website_url"]:
                        clean_dest = href.split("?")[0].rstrip("/")
                        result["website_url"] = clean_dest
                        result["has_website"] = True

        except Exception:
            pass

        return result

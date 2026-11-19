import re
import socket
import subprocess
import requests
from typing import Tuple
from src.models import Lead

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "ymail.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "me.com", "aol.com", "msn.com", "comcast.net",
    "sbcglobal.net", "att.net", "verizon.net", "mail.com", "zoho.com",
    "protonmail.com", "proton.me"
}

PLATFORM_CORPORATE_DOMAINS = {
    "instagram.com", "facebook.com", "meta.com", "fb.com", "google.com",
    "duckduckgo.com", "apple.com", "microsoft.com", "yahoo-inc.com"
}

THIRD_PARTY_PORTALS_AND_SOCIALS = (
    "tiktok.com", "youtube.com", "linkedin.com", "twitter.com", "x.com",
    "snapchat.com", "pinterest.com", "facebook.com", "instagram.com", "threads.net",
    "realtor.com", "realtor.ca", "zillow.com", "redfin.com", "trulia.com",
    "centris.ca", "justdial.com", "magicbricks.com", "99acres.com", "housing.com",
    "sulekha.com", "linktr.ee", "beacons.ai", "tap.bio", "campsite.bio"
)

class LeadFilter:
    @staticmethod
    def is_valid_email_format(email: str | None) -> bool:
        if not email or not isinstance(email, str):
            return False
        clean_email = email.strip(".,;:!? '\"")
        if not clean_email or len(clean_email) > 100:
            return False
        return bool(EMAIL_REGEX.match(clean_email))

    @staticmethod
    def is_domain_resolvable(email: str) -> bool:
        try:
            clean_email = email.strip(".,;:!? '\"")
            domain = clean_email.split("@")[1].strip().lower()
            if domain in FREE_EMAIL_DOMAINS:
                return True
            # 1. Check A / AAAA record
            try:
                socket.getaddrinfo(domain, None)
                return True
            except Exception:
                pass
            # 2. Check MX record for email-only business domains without web servers
            try:
                res = subprocess.run(
                    ["nslookup", "-type=mx", domain],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                output = res.stdout.lower()
                if "mail exchanger" in output or "mx preference" in output:
                    return True
            except Exception:
                pass
            return False
        except Exception:
            return False

    @staticmethod
    def check_custom_domain_website(email: str) -> str | None:
        """
        If email has a custom business domain (e.g. hello@renaudhomegroup.com),
        checks if the domain has a live website running.
        If yes, returns the website URL so it can be filtered out.
        """
        try:
            clean_email = email.strip(".,;:!? '\"")
            domain = clean_email.split("@")[1].strip().lower()
            if domain in FREE_EMAIL_DOMAINS or domain in PLATFORM_CORPORATE_DOMAINS:
                return None
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            # Fast probe for active website on custom domain
            for protocol in ("https://", "http://"):
                try:
                    resp = requests.get(f"{protocol}{domain}", headers=headers, timeout=3, allow_redirects=True)
                    if resp.status_code < 400 or resp.status_code in (200, 201, 202, 203, 204, 301, 302, 307, 308):
                        return f"{protocol}{domain}"
                except Exception:
                    continue
        except Exception:
            pass
        return None

    @staticmethod
    def has_no_website(website: str | None) -> bool:
        if not website:
            return True
        clean_web = website.strip().lower()
        if clean_web in ("", "none", "null", "n/a", "no website"):
            return True
        # If the URL points to a social network or 3rd-party directory portal, it is NOT an official agency site
        for portal in THIRD_PARTY_PORTALS_AND_SOCIALS:
            if portal in clean_web:
                return True
        return False

    @classmethod
    def evaluate(cls, lead: Lead) -> Tuple[bool, str]:
        # Clean trailing punctuation from email if present
        if lead.email:
            lead.email = lead.email.strip(".,;:!? '\"")

        # 1. Must NOT have a website
        if not cls.has_no_website(lead.website):
            return False, "HAS_WEBSITE"

        # 2. Must have a valid email format
        if not cls.is_valid_email_format(lead.email):
            return False, "NO_VALID_EMAIL"

        # 3. Reject platform corporate emails (e.g. info@instagram.com)
        email_domain = lead.email.split("@")[1].strip().lower()
        if any(email_domain == p or email_domain.endswith("." + p) for p in PLATFORM_CORPORATE_DOMAINS):
            return False, "PLATFORM_EMAIL_DISALLOWED"

        # 4. Email domain MUST actually exist and resolve via DNS (prevents bounces!)
        if not cls.is_domain_resolvable(lead.email):
            return False, "DOMAIN_NOT_RESOLVABLE"

        # 5. If email is from a custom business domain, verify it does NOT already host a website!
        custom_domain_web = cls.check_custom_domain_website(lead.email)
        if custom_domain_web:
            lead.website = custom_domain_web
            return False, "HAS_WEBSITE"

        return True, "QUALIFIED"

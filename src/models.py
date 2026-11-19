from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass
class Lead:
    name: str
    city: str
    email: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    source: str = "Google Maps"  # "Google Maps" or "Instagram"
    profile_url: Optional[str] = None
    status: str = "PENDING"
    email_content: Optional[str] = None
    contacted_at: Optional[str] = None
    website_preview_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    snippet: Optional[str] = None
    custom_hook: Optional[str] = None

CITY_TYPO_MAP = {
    "montrial": "Montreal",
    "montréal": "Montreal",
    "los angelis": "Los Angeles",
    "los angeles": "Los Angeles",
    "newyork": "New York",
    "philidelphia": "Philadelphia",
    "philly": "Philadelphia",
    "san fransisco": "San Francisco",
    "san francisco": "San Francisco",
    "jahanabaad": "Jehanabad",
    "jahanabad": "Jehanabad"
}

class LocationInput(BaseModel):
    raw_location: str
    city: str = ""
    state: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        parts = [p.strip() for p in self.raw_location.split(",") if p.strip()]
        if len(parts) >= 2:
            raw_c = parts[0]
            self.city = CITY_TYPO_MAP.get(raw_c.lower(), raw_c)
            self.state = parts[1]
        elif len(parts) == 1:
            val = parts[0]
            # If it's a known state or single token, determine whether state or city
            common_states = {"texas", "florida", "california", "new york", "michigan", "ohio", "georgia"}
            if val.lower() in common_states:
                self.city = ""
                self.state = val.title()
            else:
                self.city = CITY_TYPO_MAP.get(val.lower(), val)
                self.state = ""

@dataclass
class RunMetrics:
    total_locations: int = 0
    total_scraped: int = 0
    total_filtered_no_website: int = 0
    total_emails_found: int = 0
    total_emails_sent: int = 0
    total_duplicates_skipped: int = 0

import re
import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

class TimezoneHelper:
    """
    Handles global location-aware business hours and timezones for real estate agents
    in ANY country across the world.
    Ensures that follow-ups and outreach are dispatched strictly during the agent's
    local morning hours (10:00 AM to 11:30 AM, centered at 10:30 AM local time).
    """

    # 1. India
    INDIA_LOCATIONS = {
        "patna", "ranchi", "boriwali", "andheri", "bandra", "pune", "jahanabad",
        "jahanabaad", "lucknow", "mumbai", "delhi", "new delhi", "kolkata", "bengaluru",
        "bangalore", "hyderabad", "chennai", "ahmedabad", "noida", "gurugram", "gurgaon",
        "bihar", "jharkhand", "maharashtra", "uttar pradesh", "india"
    }

    # 2. United Kingdom & Ireland
    UK_LOCATIONS = {
        "london", "manchester", "birmingham", "leeds", "glasgow", "edinburgh",
        "liverpool", "bristol", "sheffield", "uk", "united kingdom", "great britain",
        "england", "scotland", "wales", "northern ireland", "dublin", "ireland"
    }

    # 3. Europe
    EUROPE_LOCATIONS = {
        "paris": "Europe/Paris",
        "france": "Europe/Paris",
        "lyon": "Europe/Paris",
        "marseille": "Europe/Paris",
        "berlin": "Europe/Berlin",
        "germany": "Europe/Berlin",
        "munich": "Europe/Berlin",
        "frankfurt": "Europe/Berlin",
        "hamburg": "Europe/Berlin",
        "madrid": "Europe/Madrid",
        "spain": "Europe/Madrid",
        "barcelona": "Europe/Madrid",
        "valencia": "Europe/Madrid",
        "rome": "Europe/Rome",
        "italy": "Europe/Rome",
        "milan": "Europe/Rome",
        "amsterdam": "Europe/Amsterdam",
        "netherlands": "Europe/Amsterdam",
        "rotterdam": "Europe/Amsterdam",
        "brussels": "Europe/Brussels",
        "belgium": "Europe/Brussels",
        "zurich": "Europe/Zurich",
        "switzerland": "Europe/Zurich",
        "geneva": "Europe/Zurich",
        "vienna": "Europe/Vienna",
        "austria": "Europe/Vienna",
        "stockholm": "Europe/Stockholm",
        "sweden": "Europe/Stockholm",
        "oslo": "Europe/Oslo",
        "norway": "Europe/Oslo",
        "copenhagen": "Europe/Copenhagen",
        "denmark": "Europe/Copenhagen",
        "lisbon": "Europe/Lisbon",
        "portugal": "Europe/Lisbon",
        "warsaw": "Europe/Warsaw",
        "poland": "Europe/Warsaw"
    }

    # 4. Australia & New Zealand
    AUSTRALIA_LOCATIONS = {
        "sydney": "Australia/Sydney",
        "melbourne": "Australia/Melbourne",
        "brisbane": "Australia/Brisbane",
        "perth": "Australia/Perth",
        "adelaide": "Australia/Adelaide",
        "gold coast": "Australia/Brisbane",
        "canberra": "Australia/Sydney",
        "australia": "Australia/Sydney",
        "auckland": "Pacific/Auckland",
        "wellington": "Pacific/Auckland",
        "new zealand": "Pacific/Auckland"
    }

    # 5. Canada
    CANADA_LOCATIONS = {
        "toronto": "America/Toronto",
        "montreal": "America/Toronto",
        "ottawa": "America/Toronto",
        "vancouver": "America/Vancouver",
        "calgary": "America/Edmonton",
        "edmonton": "America/Edmonton",
        "halifax": "America/Halifax",
        "canada": "America/Toronto"
    }

    # 6. Middle East
    MIDDLE_EAST_LOCATIONS = {
        "dubai": "Asia/Dubai",
        "abu dhabi": "Asia/Dubai",
        "uae": "Asia/Dubai",
        "united arab emirates": "Asia/Dubai",
        "riyadh": "Asia/Riyadh",
        "jeddah": "Asia/Riyadh",
        "saudi arabia": "Asia/Riyadh",
        "doha": "Asia/Qatar",
        "qatar": "Asia/Qatar",
        "kuwait": "Asia/Kuwait",
        "bahrain": "Asia/Bahrain",
        "muscat": "Asia/Muscat",
        "oman": "Asia/Muscat"
    }

    # 7. Asia Pacific
    ASIA_PACIFIC_LOCATIONS = {
        "singapore": "Asia/Singapore",
        "tokyo": "Asia/Tokyo",
        "japan": "Asia/Tokyo",
        "osaka": "Asia/Tokyo",
        "hong kong": "Asia/Hong_Kong",
        "kuala lumpur": "Asia/Kuala_Lumpur",
        "malaysia": "Asia/Kuala_Lumpur",
        "bangkok": "Asia/Bangkok",
        "thailand": "Asia/Bangkok",
        "manila": "Asia/Manila",
        "philippines": "Asia/Manila",
        "seoul": "Asia/Seoul",
        "south korea": "Asia/Seoul",
        "korea": "Asia/Seoul",
        "jakarta": "Asia/Jakarta",
        "indonesia": "Asia/Jakarta"
    }

    # 8. Latin America
    LATIN_AMERICA_LOCATIONS = {
        "mexico city": "America/Mexico_City",
        "mexico": "America/Mexico_City",
        "guadalajara": "America/Mexico_City",
        "sao paulo": "America/Sao_Paulo",
        "brazil": "America/Sao_Paulo",
        "rio de janeiro": "America/Sao_Paulo",
        "buenos aires": "America/Buenos_Aires",
        "argentina": "America/Buenos_Aires",
        "bogota": "America/Bogota",
        "colombia": "America/Bogota",
        "santiago": "America/Santiago",
        "chile": "America/Santiago",
        "lima": "America/Lima",
        "peru": "America/Lima"
    }

    # 9. Africa
    AFRICA_LOCATIONS = {
        "johannesburg": "Africa/Johannesburg",
        "cape town": "Africa/Johannesburg",
        "south africa": "Africa/Johannesburg",
        "cairo": "Africa/Cairo",
        "egypt": "Africa/Cairo",
        "nairobi": "Africa/Nairobi",
        "kenya": "Africa/Nairobi",
        "lagos": "Africa/Lagos",
        "nigeria": "Africa/Lagos"
    }

    # 10. United States Regions
    US_EASTERN = {
        "miami", "detroit", "new york", "new york city", "nyc", "durham",
        "atlanta", "philadelphia", "orlando", "tampa", "fort myers", "naples", "boston",
        "baltimore", "columbus", "indianapolis", "washington", "dc", "south florida",
        "raleigh", "charlotte", "cleveland", "florida", "ohio", "michigan", "pennsylvania",
        "georgia", "north carolina"
    }

    US_CENTRAL = {
        "chicago", "dallas", "houston", "des moines", "kansas city", "milwaukee",
        "texas", "austin", "san antonio", "minneapolis", "st louis", "st. louis",
        "nashville", "memphis", "illinois", "iowa", "wisconsin", "missouri", "oklahoma"
    }

    US_MOUNTAIN = {
        "denver", "phoenix", "scottsdale", "boise", "salt lake city", "albuquerque",
        "colorado", "arizona", "idaho", "utah", "new mexico"
    }

    US_PACIFIC = {
        "los angeles", "irvine", "san diego", "san francisco", "sf", "seattle",
        "portland", "las vegas", "california", "washington state", "oregon", "nevada",
        "los angelis"
    }

    @classmethod
    def _matches_location(cls, clean: str, loc_set: set) -> bool:
        for loc in loc_set:
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return True
        return False

    @classmethod
    def get_timezone_for_location(cls, location: str) -> str:
        if not location:
            return "America/New_York"

        clean = re.sub(r'["\']', '', location).lower().strip()

        # 1. India
        if cls._matches_location(clean, cls.INDIA_LOCATIONS):
            return "Asia/Kolkata"

        # 2. United Kingdom
        if cls._matches_location(clean, cls.UK_LOCATIONS):
            return "Europe/London"

        # 3. Canada
        for loc, tz in cls.CANADA_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 4. Australia & NZ
        for loc, tz in cls.AUSTRALIA_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 5. Europe
        for loc, tz in cls.EUROPE_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 6. Middle East
        for loc, tz in cls.MIDDLE_EAST_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 7. Asia Pacific
        for loc, tz in cls.ASIA_PACIFIC_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 8. Latin America
        for loc, tz in cls.LATIN_AMERICA_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 9. Africa
        for loc, tz in cls.AFRICA_LOCATIONS.items():
            if re.search(rf"\b{re.escape(loc)}\b", clean):
                return tz

        # 10. US Pacific
        if cls._matches_location(clean, cls.US_PACIFIC):
            return "America/Los_Angeles"

        # 11. US Mountain
        if cls._matches_location(clean, cls.US_MOUNTAIN):
            return "America/Denver"

        # 12. US Central
        if cls._matches_location(clean, cls.US_CENTRAL):
            return "America/Chicago"

        # 13. US Eastern
        if cls._matches_location(clean, cls.US_EASTERN):
            return "America/New_York"

        # Default fallback for unknown international locations: US Eastern
        return "America/New_York"

    @classmethod
    def get_current_utc(cls) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    @classmethod
    def get_local_time(cls, location: str, now_utc: Optional[datetime.datetime] = None) -> datetime.datetime:
        tz_name = cls.get_timezone_for_location(location)
        current_utc = now_utc or cls.get_current_utc()
        return current_utc.astimezone(ZoneInfo(tz_name))

    @classmethod
    def is_in_followup_window(
        cls,
        location: str,
        morning_start_hour: int = 10,
        morning_end_hour: int = 12,
        now_utc: Optional[datetime.datetime] = None
    ) -> Tuple[bool, str]:
        """
        Determines whether the agent's current local time is within the prime morning
        outreach window (10:00 AM to 12:00 PM, centered at 10:30 AM local time).
        Blocks emails outside business hours (especially night hours).
        """
        local_dt = cls.get_local_time(location, now_utc=now_utc)
        time_display = local_dt.strftime("%I:%M %p")
        tz_name = cls.get_timezone_for_location(location)
        hour = local_dt.hour
        minute = local_dt.minute

        # Between 10:00 AM and 11:59 AM (10:00 AM - 12:00 PM)
        if morning_start_hour <= hour < morning_end_hour:
            return True, f"Current local time {time_display} ({tz_name}) is in prime morning outreach window (10:00-11:30 AM)"

        # Night time check (after 7 PM or before 8:30 AM)
        if hour >= 19 or hour < 8 or (hour == 8 and minute < 30):
            return False, f"Current local time {time_display} ({tz_name}) is outside business hours (night time in {location})"

        # Outside prime 10:00-10:30 AM window
        return False, f"Current local time {time_display} ({tz_name}) is outside target 10:00-10:30 AM window"

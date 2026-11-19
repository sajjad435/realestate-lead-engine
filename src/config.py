import os
from pathlib import Path
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env if present
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

class AppConfig(BaseModel):
    # Sender details
    sender_name: str = os.getenv("SENDER_NAME", "Sajjad Wali")
    sender_email: str = os.getenv("SENDER_EMAIL", "")
    sender_password: str = os.getenv("SENDER_APP_PASSWORD", "")
    portfolio_url: str = os.getenv("PORTFOLIO_URL", "https://sajjad-wali-portfolio.vercel.app/")
    
    # Limits and delays (Anti-Spam Human Throttle)
    dry_run: bool = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")
    max_daily_emails: int = int(os.getenv("MAX_DAILY_EMAILS", "20"))
    email_min_delay_sec: float = float(os.getenv("EMAIL_MIN_DELAY_SEC", "45.0"))
    email_max_delay_sec: float = float(os.getenv("EMAIL_MAX_DELAY_SEC", "90.0"))

    # File paths (resolved to project root)
    locations_csv_path: str = os.getenv("LOCATIONS_CSV", str(PROJECT_ROOT / "locations.csv"))
    database_path: str = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "leads_tracker.db"))
    pdf_report_path: str = os.getenv("PDF_REPORT_PATH", str(PROJECT_ROOT / "reports" / "daily_lead_report.pdf"))

    # Scraper & AI settings
    google_maps_api_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

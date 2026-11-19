import os
import sys
import argparse
from src.config import AppConfig
from src.pipeline import LeadAcquisitionPipeline
from src.sheet_manager import SheetManager

def main():
    parser = argparse.ArgumentParser(description="Real Estate Lead Generation & Cold Outreach Engine")
    parser.add_argument("--city", "--add-city", dest="city", type=str, help="Process a specific city/state directly (e.g. 'Detroit, MI' or 'Texas')")
    parser.add_argument("--live", action="store_true", help="Execute real live email sending via SMTP")
    parser.add_argument("--portfolio", type=str, help="Override portfolio URL")
    parser.add_argument("--limit", type=int, default=20, help="Max emails per day")
    parser.add_argument("--followup", action="store_true", help="Process automated follow-ups for previously contacted leads")
    parser.add_argument("--ignore-timezone", action="store_true", help="Bypass local business hours check and send immediately")
    args = parser.parse_args()

    config = AppConfig()
    if args.live:
        config.dry_run = False
    if args.portfolio:
        config.portfolio_url = args.portfolio
    if args.limit:
        config.max_daily_emails = args.limit

    print("=" * 65)
    print(" 🚀 REAL ESTATE LEAD GENERATOR & COLD OUTREACH ENGINE")
    print("=" * 65)
    print(f" Mode:           {'🔴 LIVE (Real Emails)' if not config.dry_run else '🟢 DRY-RUN (Safe Simulation)'}")
    print(f" Daily Limit:    {config.max_daily_emails} emails")
    print(f" Channels:       🗺️ Maps | 📸 Instagram | 📘 Facebook | 🔥 Reddit Intent")
    print(f" Gemini AI Brain:{' 🧠 Active (Gemini 2.5 Flash)' if config.gemini_api_key else ' ⚪ Disabled'}")
    print(f" Portfolio URL:  {config.portfolio_url}")
    print(f" Locations File: {config.locations_csv_path}")
    print(f" CRM Database:   {config.database_path}")
    print(f" PDF Report:     {config.pdf_report_path}")
    print("-" * 65)

    sheet_mgr = SheetManager(csv_path=config.locations_csv_path)

    if args.city:
        sheet_mgr.add_location(args.city)
        print(f"✅ Added location: '{args.city}' to {config.locations_csv_path}")

    pipeline = LeadAcquisitionPipeline(
        csv_path=config.locations_csv_path,
        db_path=config.database_path,
        pdf_path=config.pdf_report_path,
        dry_run=config.dry_run,
        max_daily_emails=config.max_daily_emails,
        delay_seconds=0.01 if config.dry_run else 0.0,
        min_delay=config.email_min_delay_sec,
        max_delay=config.email_max_delay_sec,
        sender_email=config.sender_email,
        sender_password=config.sender_password,
        sender_name=config.sender_name,
        portfolio_url=config.portfolio_url,
        maps_api_key=config.google_maps_api_key,
        gemini_api_key=config.gemini_api_key
    )

    if args.followup:
        print("⏳ Checking for pending follow-ups (leads contacted >= 3 days ago)...")
        print(f" 🌐 Timezone Check: {'Active (Only local morning ~10:30 AM)' if not args.ignore_timezone else 'Bypassed (Send now)'}")
        count = pipeline.run_followups(
            days_threshold=0 if config.dry_run else 3,
            enforce_business_hours=not args.ignore_timezone
        )
        print(f"📬 Follow-up emails dispatched: {count}")
        return

    pending = sheet_mgr.get_pending_locations()
    if not pending:
        print("ℹ️ No pending locations found in sheet/CSV.")
        print("👉 Add locations in 'locations.csv' or run:")
        print("   python main.py --city 'Detroit, MI'")
        print("   python main.py --city 'Texas'")
        print("   python main.py --city 'Miami, FL'")
        return

    print(f"📍 Found {len(pending)} pending location(s): {[p.raw_location for p in pending]}")
    print("⏳ Running Lead Discovery, Filter (No-Website Only), Deduplication, and Outreach...")

    metrics = pipeline.run()

    print("\n" + "=" * 65)
    print(" 📊 EXECUTION SUMMARY")
    print("=" * 65)
    print(f" Locations Processed:       {metrics.total_locations}")
    print(f" Total Profiles Scraped:    {metrics.total_scraped}")
    print(f" Qualified (No Website):    {metrics.total_filtered_no_website}")
    print(f" Emails Sent Successfully:  {metrics.total_emails_sent}")
    print(f" Duplicates Skipped:        {metrics.total_duplicates_skipped}")
    print("-" * 65)
    print(f"📄 PDF Report Generated at: {os.path.abspath(config.pdf_report_path)}")
    print("✅ All done!")

if __name__ == "__main__":
    main()

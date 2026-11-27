import os
from typing import List, Optional
from src.models import Lead, LocationInput, RunMetrics
from src.filter import LeadFilter
from src.db import LeadTrackerDB
from src.sheet_manager import SheetManager
from src.scrapers.maps_finder import GoogleMapsFinder
from src.scrapers.instagram_finder import InstagramFinder
from src.scrapers.facebook_finder import FacebookFinder
from src.scrapers.intent_finder import IntentFinder
from src.mailer import ColdEmailer
from src.reporter import PDFReporter
from src.site_builder import SiteBuilder
from src.social_dm_manager import SocialDMManager
from src.timezone_helper import TimezoneHelper

class LeadAcquisitionPipeline:
    def __init__(
        self,
        csv_path: str = "locations.csv",
        db_path: str = "leads_tracker.db",
        pdf_path: str = "daily_lead_report.pdf",
        dry_run: bool = True,
        max_daily_emails: int = 25,
        delay_seconds: float = 0.0,
        min_delay: float = 45.0,
        max_delay: float = 90.0,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
        sender_name: str = "Hamzha",
        portfolio_url: str = "https://hamzha.dev",
        maps_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        template_dir: Optional[str] = None
    ):
        self.csv_path = csv_path
        self.db_path = db_path
        self.pdf_path = pdf_path
        self.dry_run = dry_run
        
        self.sheet_manager = SheetManager(csv_path=self.csv_path)
        self.db = LeadTrackerDB(db_path=self.db_path)
        self.maps_finder = GoogleMapsFinder(api_key=maps_api_key, gemini_api_key=gemini_api_key)
        self.insta_finder = InstagramFinder(gemini_api_key=gemini_api_key)
        self.fb_finder = FacebookFinder(gemini_api_key=gemini_api_key)
        self.intent_finder = IntentFinder(gemini_api_key=gemini_api_key)
        self.site_builder = SiteBuilder(
            dry_run=dry_run,
            template_dir=template_dir
        )
        
        self.emailer = ColdEmailer(
            dry_run=dry_run,
            max_daily_emails=max_daily_emails,
            delay_seconds=delay_seconds,
            min_delay=min_delay,
            max_delay=max_delay,
            sender_email=sender_email,
            sender_password=sender_password,
            sender_name=sender_name,
            portfolio_url=portfolio_url
        )
        self.reporter = PDFReporter(output_path=self.pdf_path)
        self.social_dm_manager = SocialDMManager(csv_path="social_dm_leads.csv")

    def run(self, scan_inbound_intent: bool = True) -> RunMetrics:
        metrics = RunMetrics()
        self.insta_finder.social_dm_leads = []
        self.fb_finder.social_dm_leads = []
        pending_locations = self.sheet_manager.get_pending_locations()
        metrics.total_locations = len(pending_locations)

        if not pending_locations:
            return metrics

        # Scan high-intent inbound inquiries from Reddit & public posts if enabled
        intent_leads = self.intent_finder.search_intent(max_leads=10) if scan_inbound_intent else []
        if intent_leads:
            print(f"🔥 Found {len(intent_leads)} high-intent inbound realtor website inquiries!")

        processed_location_names = []

        for loc_idx, loc in enumerate(pending_locations):
            processed_location_names.append(loc.raw_location)
            loc_leads_found = 0
            loc_emails_sent = 0

            # 1. Scrape Google Maps, Instagram, Facebook Pages (+ Inbound Intent on first location)
            maps_leads = self.maps_finder.search_city(loc)
            insta_leads = self.insta_finder.search_city(loc)
            fb_leads = self.fb_finder.search_city(loc)
            all_raw_leads = maps_leads + insta_leads + fb_leads + (intent_leads if loc_idx == 0 else [])
            metrics.total_scraped += len(all_raw_leads)

            # 2. Filter & Deduplicate & Outreach
            for lead in all_raw_leads:
                is_qualified, reason = LeadFilter.evaluate(lead)
                if not is_qualified:
                    if lead.email:
                        skip_detail = f"Business already has active website ({lead.website})" if reason == "HAS_WEBSITE" else reason
                        print(f"   ℹ️ [{lead.name}] Filter check: {skip_detail} -> Skipped")
                    continue

                metrics.total_filtered_no_website += 1
                loc_leads_found += 1

                # Check Duplicate
                if self.db.is_already_contacted(lead.email):
                    metrics.total_duplicates_skipped += 1
                    print(f"   ℹ️ [{lead.name}] Duplicate email ({lead.email}) already contacted in database -> Skipped")
                    continue

                print(f"   🚀 [{lead.name}] Qualified lead! Dispatching cold email to {lead.email}...")
                # Personal website prototype feature stopped as requested by user.
                # Send standard cold email pitch with portfolio link
                success, msg, email_content = self.emailer.send(lead)
                if success:
                    lead.email_content = email_content
                    lead.status = "SENT"
                    msg_id = getattr(lead, "message_id", None) or getattr(self.emailer, "last_message_id", None)
                    self.db.record_lead_contacted(lead, email_content, status="SENT", message_id=msg_id)
                    metrics.total_emails_sent += 1
                    loc_emails_sent += 1
                else:
                    if "limit reached" in msg:
                        break

            # 3. Update Sheet row
            self.sheet_manager.update_status(
                location=loc.raw_location,
                status="COMPLETED",
                leads_found=loc_leads_found,
                emails_sent=loc_emails_sent
            )

        # 4. Record Social DM Leads & Dispatch Digest Alert Email
        raw_social_leads = self.insta_finder.social_dm_leads + self.fb_finder.social_dm_leads
        new_social_dm_leads = []
        for s_lead in raw_social_leads:
            if self.social_dm_manager.record_social_lead(s_lead):
                new_social_dm_leads.append(s_lead)

        if new_social_dm_leads and self.emailer.sender_email:
            print(f"\n📱 [Social DM Alert] Found {len(new_social_dm_leads)} qualified agent(s) with NO website (no email listed).")
            print(f"   Saved to '{self.social_dm_manager.csv_path}' for Instagram & Facebook manual DM.")
            self.social_dm_manager.send_digest_email(
                leads=new_social_dm_leads,
                recipient_email=self.emailer.sender_email,
                sender_email=self.emailer.sender_email,
                sender_password=self.emailer.sender_password,
                sender_name=self.emailer.sender_name,
                portfolio_url=self.emailer.portfolio_url,
                dry_run=self.emailer.dry_run
            )

        # 5. Generate Final PDF Report
        recent_records = self.db.get_records_for_report(limit=100)
        self.reporter.generate(
            metrics=metrics,
            leads=recent_records,
            cities=processed_location_names
        )

        # 5. Email PDF Report to User (if sender_email is configured)
        if self.emailer.sender_email:
            leads_breakdown = "\n".join([
                f"  • {r.get('name', 'Realtor')} ({r.get('city', '')}) - {r.get('email', '')}\n    Source: {r.get('source', '')} | Link: {r.get('profile_url') or 'N/A'}"
                for r in recent_records[:max(metrics.total_emails_sent, 5)]
            ])
            summary = (
                f"- Locations Processed: {', '.join(processed_location_names)}\n"
                f"- Total Profiles Scraped: {metrics.total_scraped}\n"
                f"- Qualified (No Website): {metrics.total_filtered_no_website}\n"
                f"- Cold Emails Sent Today: {metrics.total_emails_sent}\n"
                f"- Duplicates Skipped: {metrics.total_duplicates_skipped}\n\n"
                f"Verified Leads & Source Links:\n{leads_breakdown}"
            )
            success, msg = self.emailer.send_report_email(
                recipient_email=self.emailer.sender_email,
                pdf_path=self.pdf_path,
                summary_text=summary
            )
            if success:
                print(f"\n📧 [Executive Report] ✅ PDF Report successfully emailed to: {self.emailer.sender_email}")
            else:
                print(f"\n⚠️ [Executive Report Notice] Could not email PDF report to {self.emailer.sender_email}: {msg}")

        return metrics

    def run_followups(self, days_threshold: int = 3, enforce_business_hours: bool = True) -> int:
        due_leads = self.db.get_leads_due_for_followup(days_threshold=days_threshold)
        sent_count = 0
        if not due_leads:
            print("   ℹ️ No leads currently due for follow-up (all leads are either followed up or < 3 days old).")
            return 0

        print(f"\n📬 [Automated Follow-ups] Found {len(due_leads)} leads eligible for scheduled follow-up:")
        for record in due_leads:
            name = record.get("name", "Realtor")
            city = record.get("city", "") or record.get("state", "")
            target_stage = record.get("target_stage", 1)

            # Location-aware timezone check: Ensure follow-up is dispatched only in the agent's local morning (~10:30 AM)
            if enforce_business_hours:
                in_window, tz_msg = TimezoneHelper.is_in_followup_window(city)
                if not in_window:
                    print(f"   ⏳ [{name} | {city}] Follow-up (Stage {target_stage}) postponed: {tz_msg}")
                    continue

            if self.emailer.sent_count_today >= self.emailer.max_daily_emails:
                print(f"   ⚠️ Daily email limit ({self.emailer.max_daily_emails}) reached. Remaining follow-ups postponed.")
                break

            lead = Lead(
                name=name,
                city=record.get("city", ""),
                state=record.get("state", ""),
                email=record.get("email"),
                source=record.get("source", "Outreach")
            )
            original_content = record.get("email_content")
            contacted_at = record.get("contacted_at")
            
            # Retrieve real Gmail Message-ID to ensure Gmail nests the follow-up directly under the first email
            original_msg_id = record.get("message_id") or getattr(lead, "message_id", None)
            if not original_msg_id or "initial@mail.com" in str(original_msg_id) or "thread.ref" in str(original_msg_id):
                original_msg_id = self.db.get_message_id_for_email(lead.email)
                if not original_msg_id and self.emailer.sender_email and self.emailer.sender_password and not getattr(self, "dry_run", self.emailer.dry_run):
                    original_msg_id = self.db.sync_message_id_from_imap(
                        lead.email,
                        self.emailer.sender_email,
                        self.emailer.sender_password
                    )

            print(f"   🚀 [{name}] Dispatching clean follow-up email (Stage {target_stage}) to {lead.email}...")
            success, msg, _ = self.emailer.send_followup(
                lead,
                stage=target_stage,
                original_msg_id=original_msg_id,
                original_content=original_content,
                contacted_date=contacted_at
            )
            if success:
                self.db.mark_followup_sent(lead.email, stage=target_stage)
                sent_count += 1
            else:
                print(f"   ⚠️ Notice for {lead.email}: {msg}")

        print(f"✅ Dispatched {sent_count} follow-up email(s) successfully.")
        return sent_count

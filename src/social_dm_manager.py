import os
import csv
import smtplib
import email.utils
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Tuple, Optional, Dict
from src.models import Lead

CSV_HEADERS = [
    "Name",
    "Platform",
    "City",
    "Profile_URL",
    "Phone",
    "Snippet",
    "Date_Added",
    "Status"
]

class SocialDMManager:
    """
    Manages real estate leads who have NO website and NO public email,
    saving their Instagram and Facebook profiles for manual DM outreach
    and notifying the user via email digest with clickable links.
    """
    def __init__(self, csv_path: str = "social_dm_leads.csv"):
        self.csv_path = csv_path
        self._ensure_csv_exists()

    def _ensure_csv_exists(self):
        if not os.path.exists(self.csv_path):
            dir_name = os.path.dirname(self.csv_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)

    def _get_existing_profile_urls(self) -> set:
        if not os.path.exists(self.csv_path):
            return set()
        urls = set()
        try:
            with open(self.csv_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    u = (row.get("Profile_URL") or "").strip().rstrip("/")
                    if u:
                        urls.add(u)
        except Exception:
            pass
        return urls

    def record_social_lead(self, lead: Lead) -> bool:
        """
        Appends a lead without email to social_dm_leads.csv if not already present.
        Returns True if newly added, False if duplicate or invalid.
        """
        if not lead.profile_url:
            return False

        self._ensure_csv_exists()

        clean_url = lead.profile_url.strip().rstrip("/")
        existing_urls = self._get_existing_profile_urls()
        if clean_url in existing_urls:
            return False

        row = [
            lead.name,
            lead.source,
            lead.city or "",
            clean_url,
            lead.phone or "",
            (lead.snippet or "").replace("\n", " ").strip()[:150],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "PENDING_MANUAL_DM"
        ]

        with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        return True

    def build_digest_email_content(
        self,
        leads: List[Lead],
        sender_name: str = "Sajjad Wali",
        portfolio_url: str = "https://sajjad-wali-portfolio.vercel.app/"
    ) -> Tuple[str, str]:
        """
        Builds a human-friendly email digest with direct clickable profile links
        and a ready-to-use DM script.
        """
        count = len(leads)
        subject = f"📬 [Social DM Alert] {count} Real Estate Leads Ready for Instagram & Facebook DM"

        leads_list_text = []
        for i, lead in enumerate(leads, 1):
            phone_str = f" | Phone: {lead.phone}" if lead.phone else ""
            leads_list_text.append(
                f"{i}. {lead.name} ({lead.city})\n"
                f"   Platform: {lead.source}\n"
                f"   Profile Link: {lead.profile_url}{phone_str}\n"
            )

        formatted_list = "\n".join(leads_list_text)

        body = f"""Hi {sender_name},

During your latest lead scan, we found {count} qualified real estate agents who currently have NO dedicated website, but did not have a public email listed on their profile.

These leads have been saved to '{self.csv_path}'. You can directly tap their profile links below to send them an Instagram DM or Facebook message:

============================================================
🎯 REAL ESTATE AGENTS TO DM:
============================================================
{formatted_list}
============================================================
💡 READY-TO-USE DM PITCH SCRIPT (Copy & Paste):
============================================================
"Hi {{Agent Name}}, I came across your listings in {{City}} and really liked your profile!

I noticed that you don't currently have a dedicated personal website for your listings and buyer inquiries. I specialize in designing modern, high-converting websites for realtors.

Would you be open if I send over a quick sample website preview first? If you like the design, we can take it from there.

You can also check out some of my previous work here:
{portfolio_url}

Looking forward to hearing from you!"
============================================================

Best regards,
Real Estate Lead Engine Automation
"""
        return subject, body

    def send_digest_email(
        self,
        leads: List[Lead],
        recipient_email: str,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
        sender_name: str = "Sajjad Wali",
        portfolio_url: str = "https://sajjad-wali-portfolio.vercel.app/",
        dry_run: bool = False,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587
    ) -> Tuple[bool, str]:
        """
        Sends the digest email to the user so they can manually DM leads on social media.
        """
        if not leads:
            return True, "No social DM leads to notify."

        if not recipient_email:
            return False, "Recipient email is missing."

        subject, body = self.build_digest_email_content(
            leads=leads,
            sender_name=sender_name,
            portfolio_url=portfolio_url
        )

        if dry_run:
            print(f"   [DRY-RUN] Social DM Alert Email simulated for {recipient_email} ({len(leads)} leads)")
            return True, f"[DRY-RUN] Digest email simulated for {recipient_email}"

        from_email = sender_email or recipient_email
        if not from_email or not sender_password:
            return False, "Missing SMTP credentials for sending digest email."

        try:
            msg = MIMEMultipart()
            msg["From"] = f"Lead Engine Alert <{from_email}>"
            msg["To"] = recipient_email
            msg["Subject"] = subject
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(from_email, sender_password)
                server.sendmail(from_email, recipient_email, msg.as_string())

            print(f"   ✉️ Successfully dispatched Social DM Alert email to: {recipient_email}")
            return True, f"Digest sent to {recipient_email}"
        except Exception as e:
            err_msg = f"Failed to send Social DM digest: {str(e)}"
            print(f"   ⚠️ {err_msg}")
            return False, err_msg

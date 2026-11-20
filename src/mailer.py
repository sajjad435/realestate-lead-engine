import os
import re
import time
import random
import smtplib
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Tuple, Optional
from src.models import Lead
from src.anti_spam import AntiSpamSanitizer

class EmailTemplate:
    DEFAULT_BODY_WITH_PREVIEW = """{greeting}

I came across your real estate profile in {city} and really liked your property listings.

While reviewing your business profile, I noticed that you don't currently have a dedicated website to capture organic local buyer and seller leads.

To show you what's possible, I went ahead and already built a modern, custom prototype website specifically for {business_name}:

👉 Live Website Preview: {preview_url}

It includes an interactive property showcase, tap-to-call mobile buttons, Google Maps location, and customer reviews to convert local traffic into direct client inquiries. If you like the design, I can easily connect it to your own custom domain and customize all listings and details exactly to your preferences.

You can also check out my background and portfolio of previous client work here:
👉 Portfolio: {portfolio_url}

Would you be open to a quick 5-minute chat this week to discuss getting this live for your business?

Best regards,

{sender_name}
Web Developer & Real Estate Growth Consultant
Portfolio: {portfolio_url}
"""

    DEFAULT_BODY = """{greeting}

{hook}

While reviewing your business profile, I noticed that you don't currently have a dedicated website to capture organic local buyer and seller leads. Several nearby agents in {city} are connecting with clients through dedicated websites—and without one, you might be missing out on buyers and sellers searching for local agents on Google and Maps.

I build custom realtor websites tailored to your brand, colors, photos, and name (sample: {portfolio_url}).

I'd love to put together a sample preview draft for you. If you like it, we can talk; if not, no problem at all.

Open to seeing a quick preview this week?

Best regards,

{sender_name}
Web Developer & Real Estate Web Consultant
Portfolio: {portfolio_url}
"""

    FOLLOWUP_BODY_STAGE_1 = """{greeting}

Just floating this back to the top of your inbox in case it got buried under your client showings.

I'd still love to share that quick sample website preview tailored for {city} buyers if you're open to taking a look.

Would you be open to checking out a quick preview draft?

Best regards,

{sender_name}
Web Developer & Real Estate Web Consultant
Portfolio: {portfolio_url}
"""

    FOLLOWUP_BODY_STAGE_2 = """{greeting}

I know how busy showing schedules and client deals can get in {city}.

I put together a couple of ideas on how modern property listings with instant mobile-friendly tour features can help attract more direct buyer inquiries.

Would you have 3-5 minutes this week for me to send that preview link over?

Best regards,

{sender_name}
Web Developer & Real Estate Web Consultant
Portfolio: {portfolio_url}
"""

    FOLLOWUP_BODY_STAGE_3 = """{greeting}

Quick final follow-up from my side — I don't want to clutter your inbox if you're already all set with your current web setup.

If you ever decide down the road that you'd like a modern, dedicated website to capture more local {city} buyer & seller leads, feel free to reach back out anytime.

Wishing you great success with your upcoming listings and closings!

Best regards,

{sender_name}
Web Developer & Real Estate Web Consultant
Portfolio: {portfolio_url}
"""

    # Backward compatibility alias
    FOLLOWUP_BODY = FOLLOWUP_BODY_STAGE_1

    @staticmethod
    def clean_city_name(city: Optional[str]) -> str:
        if not city:
            return ""
        # Strip CLI flags like --live, --city, stray quotes, etc.
        c = re.sub(r"\s*--[a-zA-Z0-9_-]+.*", "", city)
        return re.sub(r'["\']', '', c).strip()

    @classmethod
    def _clean_candidate(cls, word: str, city_lower: str, stop_words: set) -> Optional[str]:
        if not word:
            return None
        # Remove numbers, keep all Unicode letters (including accented ë, é, ç, etc.)
        clean = re.sub(r"[^\w]", "", word, flags=re.UNICODE).strip()
        clean = re.sub(r"\d+", "", clean)
        if not clean:
            return None
        
        clean_lower = clean.lower()
        if clean_lower == city_lower or clean_lower in stop_words:
            return None
            
        # Suffix stripping for common real estate handles/usernames (e.g. nikkisells -> nikki)
        suffixes = [
            "realtor", "realty", "sells", "selling", "sold", "broker", 
            "homes", "home", "properties", "property", "team", "group",
            "agent", "agents", "fl", "ca", "tx", "ny"
        ]
        if city_lower and len(city_lower) >= 3:
            suffixes.append(city_lower)
            
        for suffix in suffixes:
            if clean_lower.endswith(suffix) and len(clean_lower) > len(suffix) + 2:
                candidate = clean[:-len(suffix)]
                cand_lower = candidate.lower()
                if cand_lower not in stop_words and cand_lower != city_lower and 2 <= len(candidate) <= 12:
                    return candidate[:1].upper() + candidate[1:]
                    
        # Length check: A real person's first name is typically between 2 and 12 characters.
        if 2 <= len(clean) <= 12 and clean_lower not in stop_words and clean_lower != city_lower:
            return clean[:1].upper() + clean[1:]
            
        return None

    @classmethod
    def extract_salutation_name(cls, lead: Lead) -> Optional[str]:
        raw_name = (lead.name or "").strip()
        city_lower = (lead.city or "").strip().lower()
        
        stop_words = {
            "realtor", "realty", "real", "estate", "broker", "brokerage", "homes", 
            "properties", "team", "group", "holdings", "investments", "associates",
            "llc", "inc", "co", "corp", "agency", "agents",
            "info", "contact", "sales", "support", "hello", "admin", "office", "inquiries", "mail", "help"
        }
        
        # Priority 1: Dotted or separated email address (e.g. megan.khoury@compass.com, eddie.santiago@...)
        # Email prefixes like first.last are significantly more accurate than concatenated social handles
        if lead.email:
            email_user = lead.email.split("@")[0].lower()
            parts = re.split(r"[._-]", email_user)
            if len(parts) >= 2:
                cand = cls._clean_candidate(parts[0], city_lower, stop_words)
                if cand:
                    # If raw_name has the human accented version of this name (e.g. "Éric" for "eric"), prefer it!
                    if raw_name:
                        for token in re.sub(r"[^\w\s]", " ", raw_name, flags=re.UNICODE).split():
                            if token and not token.isdigit():
                                import unicodedata
                                norm_token = ''.join(c for c in unicodedata.normalize('NFD', token) if unicodedata.category(c) != 'Mn').lower()
                                norm_cand = ''.join(c for c in unicodedata.normalize('NFD', cand) if unicodedata.category(c) != 'Mn').lower()
                                if norm_token == norm_cand and len(token) >= 2:
                                    return token[:1].upper() + token[1:]
                    return cand

        # Priority 2: Name field inspection (e.g. "Sophia Sanchez", "Sarah Jenkins", or handle "Nikkisells")
        if raw_name:
            clean_tokens = [w for w in re.sub(r"[^\w\s]", " ", raw_name, flags=re.UNICODE).split() if w and not w.isdigit()]
            if len(clean_tokens) >= 2:
                # Multi-word name: check first word (e.g. "Sophia" from "Sophia Sanchez")
                cand = cls._clean_candidate(clean_tokens[0], city_lower, stop_words)
                if cand:
                    return cand
            elif len(clean_tokens) == 1:
                # Single-word name or handle (e.g. "Nikkisells" -> "Nikki")
                cand = cls._clean_candidate(clean_tokens[0], city_lower, stop_words)
                if cand:
                    return cand

        # Priority 3: Single-token email prefix (e.g. "nikkisells239@gmail.com" -> "Nikki")
        if lead.email:
            email_user = lead.email.split("@")[0].lower()
            cand = cls._clean_candidate(email_user, city_lower, stop_words)
            if cand:
                return cand

        return None

    @classmethod
    def generate_personalized_hook(cls, lead: Lead) -> str:
        """
        Generates a concise (12-18 words), non-spam 1-sentence personalized hook.
        Keeps the email ultra-compact and tailored to the lead's exact platform/achievements.
        """
        if lead.custom_hook and lead.custom_hook.strip():
            return lead.custom_hook.strip()

        city = cls.clean_city_name(lead.city or (lead.state if lead.state else "your area"))

        # 1. Google Maps / Rating hook
        if lead.rating and lead.rating >= 4.0:
            if lead.review_count and lead.review_count > 0:
                return f"Really impressed by your {lead.rating}/5 rating across {lead.review_count} client reviews in {city} — really impressive reputation."
            return f"Really impressed by your {lead.rating}/5 rating across local clients in {city} — really impressive reputation."

        # 2. Facebook agency hook
        if lead.source == "Facebook" and lead.name and len(lead.name.split()) >= 2:
            return f"I came across {lead.name} in {city} and really liked your active local property updates."

        # 3. Instagram social hook
        if lead.source == "Instagram" and lead.snippet:
            clean_snip = lead.snippet.lower()
            if "tour" in clean_snip:
                return f"I came across your profile in {city} and really liked how you showcase your local property tours."
            if "waterfront" in clean_snip or "luxury" in clean_snip:
                return f"I came across your profile in {city} and really liked your waterfront and property updates."
            if "relocation" in clean_snip:
                return f"I came across your profile in {city} and really liked your local relocation and property posts."

        # 4. Reddit inbound intent hook
        if lead.source == "Reddit Intent":
            return "I saw your recent note about looking for an effective way to showcase your real estate listings online."

        # 5. Default natural hook
        return f"I came across your profile in {city} and really liked your property posts and listings."

    @classmethod
    def render(cls, lead: Lead, sender_name: str = "Hamzha", portfolio_url: str = "https://hamzha.dev") -> Tuple[str, str]:
        salutation_name = cls.extract_salutation_name(lead)
        city_display = cls.clean_city_name(lead.city or (lead.state if lead.state else "your area"))
        business_display = lead.name or "your real estate business"
        
        if salutation_name:
            greeting = f"Hi {salutation_name},"
            subject = f"Quick question regarding {city_display} real estate listings - {salutation_name}"
        else:
            greeting = "Hi there,"
            subject = f"Quick question regarding {city_display} real estate listings"

        hook = cls.generate_personalized_hook(lead)

        # Personal website prototype feature stopped as requested by user.
        # Send clean, high-converting cold email asking if they want a free preview.
        body = cls.DEFAULT_BODY.format(
            greeting=greeting,
            hook=hook,
            city=city_display,
            portfolio_url=portfolio_url,
            sender_name=sender_name
        )
        subject = AntiSpamSanitizer.clean(subject)
        body = AntiSpamSanitizer.clean(body)
        return subject, body

    @classmethod
    def render_followup(
        cls,
        lead: Lead,
        stage: int = 1,
        sender_name: str = "Hamzha",
        portfolio_url: str = "https://hamzha.dev",
        original_content: Optional[str] = None,
        contacted_date: Optional[str] = None
    ) -> Tuple[str, str]:
        salutation_name = cls.extract_salutation_name(lead)
        city_display = cls.clean_city_name(lead.city or (lead.state if lead.state else "your area"))

        orig_subject = None
        if original_content:
            if original_content.startswith("Subject:"):
                parts = original_content.split("\n", 2)
                orig_subject = parts[0].replace("Subject:", "").strip()

        if orig_subject:
            subject = orig_subject if orig_subject.startswith("Re: ") else f"Re: {orig_subject}"
        elif salutation_name:
            subject = f"Re: Quick question regarding {city_display} real estate listings - {salutation_name}"
        else:
            subject = f"Re: Quick question regarding {city_display} real estate listings"

        greeting = f"Hi {salutation_name}," if salutation_name else "Hi there,"
        preview_url = lead.website_preview_url or portfolio_url

        # Select distinct follow-up template per stage
        if stage == 2:
            template = cls.FOLLOWUP_BODY_STAGE_2
        elif stage >= 3:
            template = cls.FOLLOWUP_BODY_STAGE_3
        else:
            template = cls.FOLLOWUP_BODY_STAGE_1

        body = template.format(
            greeting=greeting,
            city=city_display,
            preview_url=preview_url,
            portfolio_url=portfolio_url,
            sender_name=sender_name
        )

        # Body remains completely clean without manual quote spam (no '--- On ... wrote: > ...').
        # Native RFC In-Reply-To & References headers handle clean thread hierarchy in Gmail & all email clients.

        subject = AntiSpamSanitizer.clean(subject)
        body = AntiSpamSanitizer.clean(body)
        return subject, body


class ColdEmailer:
    """
    Handles cold email dispatch with throttling, daily limits,
    dry-run testing mode, and SMTP delivery.
    """
    def __init__(
        self,
        dry_run: bool = True,
        max_daily_emails: int = 25,
        delay_seconds: float = 0.0,
        min_delay: float = 45.0,
        max_delay: float = 90.0,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
        sender_name: str = "Hamzha",
        portfolio_url: str = "https://hamzha.dev",
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587
    ):
        self.dry_run = dry_run
        self.max_daily_emails = max_daily_emails
        self.delay_seconds = delay_seconds
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.sender_name = sender_name
        self.portfolio_url = portfolio_url
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sent_count_today = 0

    def _apply_anti_spam_delay(self):
        if self.dry_run or os.getenv("TEST_MODE") == "1":
            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)
            return

        # Live mode: Human randomized delay between 45 to 90 seconds
        delay = random.uniform(self.min_delay, self.max_delay)
        print(f"   ⏳ [Anti-Spam Human Throttle] Waiting {delay:.1f} seconds before sending next email to protect inbox reputation...")
        time.sleep(delay)

    def build_mime_message(self, lead: Lead) -> MIMEText:
        subject, body = EmailTemplate.render(
            lead=lead,
            sender_name=self.sender_name,
            portfolio_url=self.portfolio_url
        )
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = lead.email
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        domain = self.sender_email.split("@")[1] if (self.sender_email and "@" in self.sender_email) else "gmail.com"
        msg_id = getattr(lead, "message_id", None) or email.utils.make_msgid(domain=domain)
        lead.message_id = msg_id
        self.last_message_id = msg_id
        msg["Message-ID"] = msg_id
        if self.sender_email:
            msg["Reply-To"] = self.sender_email
        return msg

    def send(self, lead: Lead) -> Tuple[bool, str, str]:
        if not lead.email:
            return False, "Lead has no email address", ""

        if self.sent_count_today >= self.max_daily_emails:
            return False, f"Daily email limit reached ({self.max_daily_emails})", ""

        subject, body = EmailTemplate.render(
            lead=lead,
            sender_name=self.sender_name,
            portfolio_url=self.portfolio_url
        )

        full_content = f"Subject: {subject}\n\n{body}"

        # Ensure message_id is generated even in dry-run mode for record keeping
        domain = self.sender_email.split("@")[1] if (self.sender_email and "@" in self.sender_email) else "gmail.com"
        msg_id = getattr(lead, "message_id", None) or email.utils.make_msgid(domain=domain)
        lead.message_id = msg_id
        self.last_message_id = msg_id

        if self.dry_run:
            self.sent_count_today += 1
            self._apply_anti_spam_delay()
            return True, f"[DRY-RUN] Email simulated for {lead.email}", full_content

        # Real SMTP Delivery
        if not self.sender_email or not self.sender_password:
            return False, "SMTP credentials not provided", full_content

        try:
            msg = self.build_mime_message(lead)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, lead.email, msg.as_string())

            self.sent_count_today += 1
            print(f"   ✉️ Successfully delivered email #{self.sent_count_today} to: {lead.email}")
            self._apply_anti_spam_delay()

            return True, f"Successfully sent email to {lead.email}", full_content
        except Exception as e:
            return False, f"SMTP Error sending to {lead.email}: {str(e)}", full_content

    def build_followup_mime_message(
        self,
        lead: Lead,
        stage: int = 1,
        original_msg_id: Optional[str] = None,
        original_content: Optional[str] = None,
        contacted_date: Optional[str] = None
    ) -> MIMEText:
        subject, body = EmailTemplate.render_followup(
            lead=lead,
            stage=stage,
            sender_name=self.sender_name,
            portfolio_url=self.portfolio_url,
            original_content=original_content,
            contacted_date=contacted_date
        )
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = lead.email
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        domain = self.sender_email.split("@")[1] if "@" in (self.sender_email or "") else "mail.com"
        msg["Message-ID"] = email.utils.make_msgid(domain=domain)
        msg["Reply-To"] = self.sender_email or "info@mail.com"

        # Threading RFC headers to nest follow-up directly into the original conversation thread
        thread_ref = original_msg_id or getattr(lead, "message_id", None) or email.utils.make_msgid(domain="thread.ref")
        msg["In-Reply-To"] = thread_ref
        msg["References"] = thread_ref
        return msg

    def send_followup(
        self,
        lead: Lead,
        stage: int = 1,
        original_msg_id: Optional[str] = None,
        original_content: Optional[str] = None,
        contacted_date: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        if not lead.email:
            return False, "Lead has no email address", ""

        if self.sent_count_today >= self.max_daily_emails:
            return False, f"Daily email limit reached ({self.max_daily_emails})", ""

        subject, body = EmailTemplate.render_followup(
            lead=lead,
            stage=stage,
            sender_name=self.sender_name,
            portfolio_url=self.portfolio_url,
            original_content=original_content,
            contacted_date=contacted_date
        )
        full_content = f"Subject: {subject}\n\n{body}"

        if self.dry_run:
            self.sent_count_today += 1
            self._apply_anti_spam_delay()
            return True, f"[DRY-RUN] Follow-up (Stage {stage}) simulated for {lead.email}", full_content

        if not self.sender_email or not self.sender_password:
            return False, "SMTP credentials not provided", full_content

        try:
            msg = self.build_followup_mime_message(
                lead=lead,
                stage=stage,
                original_msg_id=original_msg_id,
                original_content=original_content,
                contacted_date=contacted_date
            )

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, lead.email, msg.as_string())

            self.sent_count_today += 1
            self._apply_anti_spam_delay()
            return True, f"Successfully sent follow-up (Stage {stage}) to {lead.email}", full_content
        except Exception as e:
            return False, f"SMTP Error sending follow-up to {lead.email}: {str(e)}", full_content

    def send_report_email(self, recipient_email: str, pdf_path: str, summary_text: str = "") -> Tuple[bool, str]:
        if not os.path.exists(pdf_path):
            return False, f"Report PDF file not found at {pdf_path}"

        subject = f"📊 Real Estate Lead Generation & Outreach Report - {os.path.basename(pdf_path)}"
        body = f"""Hi {self.sender_name},

Here is your automated real estate lead outreach summary and executive report.

Summary of Today's Run:
{summary_text}

The complete detailed CRM table, contacted agent list, and email pitches are attached in the PDF report below.

Best regards,
Automated Lead Engine"""

        if self.dry_run:
            return True, f"[DRY-RUN] Report email simulated to {recipient_email}"

        if not self.sender_email or not self.sender_password:
            return False, "SMTP credentials missing"

        try:
            msg = MIMEMultipart()
            msg["From"] = f"Lead Engine System <{self.sender_email}>"
            msg["To"] = recipient_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
                msg.attach(part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, msg.as_string())

            return True, f"Report PDF successfully emailed to {recipient_email}"
        except Exception as e:
            return False, f"SMTP Error emailing report to {recipient_email}: {str(e)}"

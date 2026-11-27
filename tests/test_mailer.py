import pytest
from src.mailer import ColdEmailer, EmailTemplate
from src.models import Lead

def test_email_template_rendering_standard_pitch_from_screenshot():
    lead = Lead(
        name="Samridhi Properties & Developers",
        city="ranchi",
        email="spdrealties@gmail.com",
        source="Google Maps"
    )
    rendered_subject, rendered_body = EmailTemplate.render(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    assert "Hi Samridhi," in rendered_body
    assert "I came across your profile in ranchi and really liked your property posts and listings." in rendered_body
    assert "While reviewing your business profile, I noticed that you don't currently have a dedicated website to capture organic local buyer and seller leads." in rendered_body
    assert "Several nearby agents in ranchi are connecting with clients through dedicated websites" in rendered_body
    assert "searching for local agents on Google and Maps" in rendered_body
    assert "tailored to your brand, colors, photos, and name" in rendered_body
    assert "sample preview draft" in rendered_body
    assert "If you like it, we can talk; if not, no problem at all." in rendered_body
    assert "Would it be alright if I send over a quick 30-second preview link for your brand, or are you all set right now?" in rendered_body
    assert "Portfolio: https://sajjad-wali-portfolio.vercel.app/" in rendered_body
    assert "Sajjad Wali" in rendered_body
    assert "Web Developer & Real Estate Web Consultant" in rendered_body
    # Ensure prototype preview features are disabled
    assert "Live Website Preview:" not in rendered_body
    assert "already built" not in rendered_body

def test_email_template_ignores_website_preview_url_when_feature_stopped():
    lead = Lead(
        name="Sarah Jenkins Realty",
        city="Detroit",
        email="sarah@realty.com",
        source="Google Maps",
        website_preview_url="https://sarah-jenkins-realty.vercel.app"
    )
    rendered_subject, rendered_body = EmailTemplate.render(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    # Even if website_preview_url was attached, standard pitch must be sent as requested by user
    assert "Live Website Preview:" not in rendered_body
    assert "https://sarah-jenkins-realty.vercel.app" not in rendered_body
    assert "sample preview draft" in rendered_body
    assert "Would it be alright if I send over a quick 30-second preview link for your brand, or are you all set right now?" in rendered_body

def test_email_template_rendering_fallback():
    lead = Lead(
        name="Sarah Jenkins",
        city="Detroit",
        email="sarah@realty.com",
        source="Google Maps"
    )
    rendered_subject, rendered_body = EmailTemplate.render(
        lead=lead,
        sender_name="Hamzha",
        portfolio_url="https://hamzha.dev"
    )
    assert "https://hamzha.dev" in rendered_body
    assert "Detroit" in rendered_subject or "Sarah" in rendered_subject

def test_followup_email_template_rendering():
    lead = Lead(
        name="Sarah Jenkins",
        city="Detroit",
        email="sarah@realty.com",
        source="Google Maps"
    )
    subject, body = EmailTemplate.render_followup(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    assert "Re:" in subject
    assert "Detroit" in subject
    # Super-short, friendly conversational tone
    assert "floating this back" in body.lower() or "buried" in body.lower()
    assert "sample website preview" in body.lower() or "preview draft" in body.lower()
    assert "https://sajjad-wali-portfolio.vercel.app/" in body
    # Zero spam triggers or promotional emojis
    assert "👉" not in body
    assert "free" not in body.lower()
    assert "100%" not in body
    assert "guarantee" not in body.lower()
    # Ultra-compact length (< 90 words)
    assert len(body.split()) < 90

def test_followup_emailer_attaches_threading_headers():
    emailer = ColdEmailer(
        dry_run=True,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    lead = Lead(
        name="Sarah Jenkins",
        city="Detroit",
        email="sarah@realty.com",
        source="Google Maps",
        message_id="<sarah.original.123@gmail.com>"
    )
    msg = emailer.build_followup_mime_message(lead)
    assert "Re:" in msg["Subject"]
    assert msg["In-Reply-To"] == "<sarah.original.123@gmail.com>"
    assert msg["References"] == "<sarah.original.123@gmail.com>"
    assert msg["Message-ID"] is not None
    assert msg["Date"] is not None


def test_cold_emailer_dry_run_mode():
    emailer = ColdEmailer(dry_run=True, sender_name="Hamzha", portfolio_url="https://hamzha.dev")
    lead = Lead(
        name="Alex Mercer",
        city="Texas",
        email="alex@texasliving.com",
        source="Instagram",
        website_preview_url="https://alex-mercer-homes.vercel.app"
    )
    success, message, email_content = emailer.send(lead)
    assert success is True
    assert "[DRY-RUN]" in message
    assert "alex@texasliving.com" in message
    assert "https://hamzha.dev" in email_content
    assert "sample preview draft" in email_content
    assert "Would it be alright if I send over a quick 30-second preview link for your brand, or are you all set right now?" in email_content

def test_cold_emailer_rate_limiter():
    emailer = ColdEmailer(dry_run=True, max_daily_emails=2)
    lead1 = Lead(name="A1", city="Miami", email="a1@test.com")
    lead2 = Lead(name="A2", city="Miami", email="a2@test.com")
    lead3 = Lead(name="A3", city="Miami", email="a3@test.com")

    success1, _, _ = emailer.send(lead1)
    success2, _, _ = emailer.send(lead2)
    success3, msg3, _ = emailer.send(lead3)

    assert success1 is True
    assert success2 is True
    assert success3 is False
    assert "Daily email limit reached" in msg3

def test_email_template_uses_explicit_custom_hook():
    lead = Lead(
        name="Jason Archer",
        city="Boise",
        email="jason@archer.com",
        source="Instagram",
        custom_hook="I came across your profile in Boise and really liked how you showcase your local property tours."
    )
    subject, body = EmailTemplate.render(lead=lead, sender_name="Sajjad Wali")
    assert "how you showcase your local property tours" in body
    # Size constraint: Must be crisp and compact, matching default size (<= 155 words)
    assert len(body.split()) <= 155

def test_email_template_generates_rating_hook_for_google_maps():
    lead = Lead(
        name="Melanie Jones",
        city="Raleigh",
        email="melanie@realtor.com",
        source="Google Maps",
        rating=4.9,
        review_count=37
    )
    subject, body = EmailTemplate.render(lead=lead, sender_name="Sajjad Wali")
    assert "4.9" in body
    assert len(body.split()) <= 155

def test_email_template_generates_instagram_social_hook_from_snippet():
    lead = Lead(
        name="Elena Woods",
        city="Miami",
        email="elena@miamihomes.com",
        source="Instagram",
        snippet="Luxury waterfront tours and relocation guide"
    )
    subject, body = EmailTemplate.render(lead=lead, sender_name="Sajjad Wali")
    assert "waterfront" in body.lower() or "tour" in body.lower() or "relocation" in body.lower()
    assert len(body.split()) <= 155

def test_email_template_generates_facebook_agency_hook():
    lead = Lead(
        name="Premier Realty Partners",
        city="Austin",
        email="contact@austinpremier.com",
        source="Facebook"
    )
    subject, body = EmailTemplate.render(lead=lead, sender_name="Sajjad Wali")
    assert "Premier Realty Partners" in body
    assert len(body.split()) <= 155


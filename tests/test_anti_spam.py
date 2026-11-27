import pytest
from src.anti_spam import AntiSpamSanitizer
from src.mailer import EmailTemplate, ColdEmailer
from src.models import Lead

def test_anti_spam_sanitizer_replaces_spam_triggers_with_safe_words():
    sanitizer = AntiSpamSanitizer()
    
    # 1. 'free' -> safe alternative preserving meaning
    text_with_free = "Would you be open if I send over a quick free website preview first?"
    sanitized = sanitizer.clean(text_with_free)
    assert "free" not in sanitized.lower()
    assert "preview" in sanitized.lower()

    # 2. '100%' and 'guarantee'
    text_with_guarantee = "We offer 100% guarantee on all property sales"
    sanitized_guarantee = sanitizer.clean(text_with_guarantee)
    assert "100%" not in sanitized_guarantee
    assert "guarantee" not in sanitized_guarantee.lower()

    # 3. 'click here'
    text_with_click = "Please click here to view the listings"
    sanitized_click = sanitizer.clean(text_with_click)
    assert "click here" not in sanitized_click.lower()

def test_anti_spam_sanitizer_strips_promotional_emojis():
    sanitizer = AntiSpamSanitizer()
    text_with_emojis = "👉 Portfolio: https://example.com 🔥 New deal! 🚀 Scale your business"
    clean_text = sanitizer.clean(text_with_emojis)
    assert "👉" not in clean_text
    assert "🔥" not in clean_text
    assert "🚀" not in clean_text
    assert "https://example.com" in clean_text

def test_rendered_cold_email_is_completely_spam_word_free():
    lead = Lead(name="Samridhi Properties", city="Ranchi", email="spdrealties@gmail.com")
    subject, body = EmailTemplate.render(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    # Must NOT have known spam trigger words
    assert "free" not in body.lower()
    assert "100%" not in body
    assert "guarantee" not in body.lower()
    assert "click here" not in body.lower()
    assert "👉" not in body
    assert "👉" not in subject
    # Must be professional and clean
    assert "sample website preview" in body.lower() or "complimentary website preview" in body.lower() or "preview draft" in body.lower() or "preview link" in body.lower()

def test_cold_emailer_message_headers_include_rfc_anti_spam_fields():
    emailer = ColdEmailer(
        dry_run=False,
        sender_email="sajjadwali257@gmail.com",
        sender_password="fake-app-password",
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    lead = Lead(name="Alex Mercer", city="Dallas", email="alex@mercerrealty.com")
    msg = emailer.build_mime_message(lead)
    
    # Must contain essential RFC headers to prevent SpamAssassin penalty
    assert msg["From"] is not None
    assert msg["To"] == "alex@mercerrealty.com"
    assert msg["Subject"] is not None
    assert msg["Date"] is not None
    assert msg["Message-ID"] is not None
    assert msg["Reply-To"] == "sajjadwali257@gmail.com"

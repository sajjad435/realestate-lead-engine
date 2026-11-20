import pytest
from src.models import Lead
from src.mailer import EmailTemplate

def test_cold_email_new_high_converting_template():
    lead = Lead(name="Aarif Buddha", city="Patna", email="aarifkumar24@gmail.com")
    subject, body = EmailTemplate.render(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )

    # 1. Subject validation
    assert "Patna" in subject
    assert "Aarif" in subject

    # 2. Key messaging & competitive research angle
    assert "While reviewing your business profile, I noticed that you don't currently have a dedicated website to capture organic local buyer and seller leads." in body
    assert "Several nearby agents in Patna are connecting with clients through dedicated websites" in body
    assert "searching for local agents on Google and Maps" in body

    # 3. Customization by brand, colors, photos, name
    assert "tailored to your brand, colors, photos, and name" in body

    # 4. Zero-risk, spam-free sample preview offer
    assert "sample preview draft" in body
    assert "If you like it, we can talk; if not, no problem at all." in body
    assert "Open to seeing a quick preview this week?" in body

    # 5. Anti-spam check: Must NOT contain the spam trigger word "free"
    words = [w.strip(".,!?\"'").lower() for w in body.split()]
    assert "free" not in words

    # 6. Length check: Must be crisp and under 135 words total
    assert len(words) <= 135

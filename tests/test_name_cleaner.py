import pytest
from src.mailer import EmailTemplate
from src.models import Lead

def test_name_cleaner_prevents_city_name_as_first_name():
    lead = Lead(
        name="Tampa Realtor",
        city="Tampa",
        email="eddie.santiago@cbrealty.com",
        source="Instagram",
        profile_url="https://instagram.com/eddie.santiago"
    )
    subject, body = EmailTemplate.render(
        lead=lead,
        sender_name="Sajjad Wali",
        portfolio_url="https://sajjad-wali-portfolio.vercel.app/"
    )
    # Must NOT call them "Tampa"
    assert "Hi Tampa" not in body
    assert "- Tampa" not in subject
    # Must extract Eddie from eddie.santiago
    assert "Hi Eddie" in body
    assert subject.startswith("Eddie, quick question about your")

def test_name_cleaner_extracts_name_from_dotted_email():
    lead = Lead(
        name="Tampa Realtor",
        city="Tampa",
        email="charles.diaz@evrealestate.com",
        source="Instagram"
    )
    subject, body = EmailTemplate.render(lead)
    assert "Hi Charles" in body
    assert subject.startswith("Charles, quick question about your")

def test_name_cleaner_handles_real_person_name():
    lead = Lead(
        name="Sophia Sanchez",
        city="Tampa",
        email="sophia@realty.com",
        source="Google Maps"
    )
    subject, body = EmailTemplate.render(lead)
    assert "Hi Sophia" in body
    assert subject.startswith("Sophia, quick question about your")

def test_name_cleaner_generic_fallback_when_no_name_found():
    lead = Lead(
        name="54 Realty LLC",
        city="Tampa",
        email="info@54realty.com",
        source="Google Maps"
    )
    subject, body = EmailTemplate.render(lead)
    assert "Hi there," in body
    # Subject should not have trailing hyphen or city name
    assert subject == "quick question about your Tampa listings"

def test_name_cleaner_handles_concatenated_instagram_handles():
    # Exact case 1 from user screenshot: Megan Khoury
    lead1 = Lead(
        name="Megankhourynaplesrealtor",
        city="Naples",
        email="megan.khoury@compass.com",
        source="Instagram"
    )
    subject1, body1 = EmailTemplate.render(lead1)
    assert "Hi Megan," in body1
    assert "Megankhoury" not in body1
    assert "Megankhoury" not in subject1
    assert subject1.startswith("Megan, quick question about your")

    # Exact case 2 from user screenshot: Nikki Sells
    lead2 = Lead(
        name="Nikkisells",
        city="Naples",
        email="nikkisells239@gmail.com",
        source="Instagram"
    )
    subject2, body2 = EmailTemplate.render(lead2)
    assert "Hi Nikki," in body2
    assert "Nikkisells" not in body2
    assert "Nikkisells" not in subject2
    assert subject2.startswith("Nikki, quick question about your")

def test_name_cleaner_prevents_long_slug_when_no_clean_name():
    # Long mashup agency handle with generic email should fall back safely to "Hi there,"
    lead = Lead(
        name="Naplesluxurylistingsgroup",
        city="Naples",
        email="contact@luxurylistings.com",
        source="Instagram"
    )
    subject, body = EmailTemplate.render(lead)
    assert "Hi there," in body
    assert "Naplesluxurylistingsgroup" not in body
    assert "Naplesluxurylistingsgroup" not in subject
    assert subject == "quick question about your Naples listings"

def test_name_cleaner_extracts_from_underscored_email():
    lead = Lead(
        name="Florida Realtor Pro",
        city="Miami",
        email="robert_turner@floridaliving.com",
        source="Instagram"
    )
    subject, body = EmailTemplate.render(lead)
    assert "Hi Robert," in body
    assert subject.startswith("Robert, quick question about your")

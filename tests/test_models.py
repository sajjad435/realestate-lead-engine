import pytest
from src.models import Lead, LocationInput, RunMetrics

def test_lead_creation_and_attributes():
    lead = Lead(
        name="John Realtor",
        city="Detroit",
        state="MI",
        email="john@detroitrealty.com",
        phone="+13135550199",
        website=None,
        source="Google Maps",
        profile_url="https://maps.google.com/?cid=12345"
    )
    assert lead.name == "John Realtor"
    assert lead.city == "Detroit"
    assert lead.email == "john@detroitrealty.com"
    assert lead.website is None
    assert lead.source == "Google Maps"

def test_location_input_parsing():
    loc = LocationInput(raw_location="Detroit, MI")
    assert loc.city == "Detroit"
    assert loc.state == "MI"

    loc2 = LocationInput(raw_location="Texas")
    assert loc2.city == ""
    assert loc2.state == "Texas"

def test_location_input_normalizes_common_city_typos():
    loc = LocationInput(raw_location="montrial")
    assert loc.city == "Montreal"

    loc2 = LocationInput(raw_location="los angelis")
    assert loc2.city == "Los Angeles"

    loc3 = LocationInput(raw_location="philidelphia")
    assert loc3.city == "Philadelphia"


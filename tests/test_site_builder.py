import os
import shutil
import pytest
from src.models import Lead
from src.site_builder import SiteBuilder

@pytest.fixture
def temp_output_dir(tmp_path):
    output_dir = tmp_path / "generated_sites"
    output_dir.mkdir()
    return str(output_dir)

def test_slugify_business_name():
    assert SiteBuilder.slugify("Sarah Jenkins Realty, LLC") == "sarah-jenkins-realty"
    assert SiteBuilder.slugify("Kalyan Property & Real Estate") == "kalyan-property-real-estate"
    assert SiteBuilder.slugify("John's Homes 2026") == "johns-homes-2026"
    assert SiteBuilder.slugify("") == "realty-preview"

def test_build_prototype_site(temp_output_dir):
    lead = Lead(
        name="Apex Living Realty",
        city="Detroit",
        phone="+1 313-555-0199",
        address="100 Woodward Ave, Detroit, MI 48226",
        email="contact@apexliving.com",
        source="Google Maps"
    )

    builder = SiteBuilder(output_base_dir=temp_output_dir, dry_run=True)
    site_path = builder.build(lead)

    assert os.path.exists(site_path)
    assert os.path.exists(os.path.join(site_path, "index.html"))
    assert os.path.exists(os.path.join(site_path, "properties.html"))
    assert os.path.exists(os.path.join(site_path, "about.html"))
    assert os.path.exists(os.path.join(site_path, "contact.html"))
    assert os.path.exists(os.path.join(site_path, "styles.css"))

    # Inspect index.html content for customizations
    with open(os.path.join(site_path, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
        assert "Apex Living Realty" in html
        assert "Detroit" in html
        assert "+1 313-555-0199" in html
        assert "100 Woodward Ave" in html

def test_deploy_site_dry_run(temp_output_dir):
    lead = Lead(
        name="Lakeside Premier Homes",
        city="Orlando",
        phone="+1 407-555-0144",
        address="400 Lake Eola Pkwy, Orlando, FL 32801",
        email="lakeside@orlandohomes.com",
        source="Google Maps"
    )

    builder = SiteBuilder(output_base_dir=temp_output_dir, dry_run=True)
    preview_url = builder.build_and_deploy(lead)

    assert preview_url.startswith("https://")
    assert "lakeside-premier-homes" in preview_url
    assert lead.website_preview_url == preview_url

def test_site_customization_replaces_all_legacy_tokens(temp_output_dir):
    lead = Lead(
        name="Sunrise Real Estate",
        city="Phoenix",
        phone="+1 602-555-9988",
        address="777 Camelback Rd, Phoenix, AZ 85012",
        email="info@sunriserealty.com",
        source="Google Maps"
    )

    builder = SiteBuilder(output_base_dir=temp_output_dir, dry_run=True)
    site_path = builder.build(lead)

    with open(os.path.join(site_path, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
        # Verify that legacy brand names from template are completely replaced
        assert "Disha Property" not in html
        assert "Sunrise Real Estate" in html

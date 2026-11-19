import os
import re
import shutil
import subprocess
from typing import Optional, List, Dict
from src.models import Lead

DEFAULT_TEMPLATE_PATH = r"C:\disha-property-consultancy-real-estate-in-jamshedpur"
FALLBACK_TEMPLATE_PATH = r"C:\Users\HAMZHA\.gemini\antigravity\scratch\kalyan-property"

class SiteBuilder:
    """
    Automates generating bespoke prototype websites for real estate leads
    inspired by the high-converting Disha Property UI/UX design.
    """
    def __init__(
        self,
        output_base_dir: str = r"C:\Users\HAMZHA\.gemini\antigravity\scratch\generated_prototypes",
        template_dir: Optional[str] = None,
        dry_run: bool = True
    ):
        self.output_base_dir = output_base_dir
        self.dry_run = dry_run
        
        if template_dir and os.path.exists(template_dir):
            self.template_dir = template_dir
        elif os.path.exists(DEFAULT_TEMPLATE_PATH):
            self.template_dir = DEFAULT_TEMPLATE_PATH
        elif os.path.exists(FALLBACK_TEMPLATE_PATH):
            self.template_dir = FALLBACK_TEMPLATE_PATH
        else:
            self.template_dir = None

    @classmethod
    def slugify(cls, name: Optional[str]) -> str:
        if not name:
            return "realty-preview"
        # Strip corporate suffixes like LLC, Inc, Corp, Co, Ltd
        clean_name = re.sub(r"\b(llc|inc|corp|co|ltd)\b", "", name, flags=re.IGNORECASE)
        slug = re.sub(r"[^\w\s-]", "", clean_name).strip().lower()
        slug = re.sub(r"[-\s]+", "-", slug)
        slug = slug.strip("-")
        return slug[:45] if slug else "realty-preview"

    def build(self, lead: Lead) -> str:
        os.makedirs(self.output_base_dir, exist_ok=True)
        slug = self.slugify(lead.name)
        target_dir = os.path.join(self.output_base_dir, slug)

        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)

        if not self.template_dir or not os.path.exists(self.template_dir):
            # Fallback minimal static site if template directory is unavailable
            self._generate_minimal_site(target_dir, lead)
            return target_dir

        # Copy essential files from template
        files_to_copy = [
            "index.html", "properties.html", "about.html", "contact.html", "team.html",
            "styles.css", "vercel.json"
        ]
        dirs_to_copy = ["assets", "js"]

        for file_name in files_to_copy:
            src_file = os.path.join(self.template_dir, file_name)
            if os.path.exists(src_file):
                shutil.copy2(src_file, os.path.join(target_dir, file_name))

        for dir_name in dirs_to_copy:
            src_subdir = os.path.join(self.template_dir, dir_name)
            if os.path.exists(src_subdir):
                shutil.copytree(src_subdir, os.path.join(target_dir, dir_name), dirs_exist_ok=True)

        # Apply branding & metadata customization
        self._customize_site_content(target_dir, lead)
        return target_dir

    def _customize_site_content(self, target_dir: str, lead: Lead):
        business_name = lead.name or "Premier Real Estate"
        city = lead.city or "Your City"
        state = lead.state or ""
        location_display = f"{city}, {state}".strip(", ") if state else city
        phone = lead.phone or "+1 (555) 000-0000"
        phone_digits = re.sub(r"[^\d+]", "", phone)
        address = lead.address or f"{business_name} Office, {location_display}"
        email = lead.email or "info@realtyconsulting.com"

        html_files = [
            f for f in os.listdir(target_dir) if f.endswith(".html")
        ]

        # Specific replacement pairs
        replacements = [
            ("Origin Properties Ranchi (A Unit of Origin Properties Ranchi LLP)", business_name),
            ("Origin Property Consultancy", business_name),
            ("Origin Properties Ranchi", business_name),
            ("Origin Property", business_name),
            ("Disha Property Consultancy", business_name),
            ("Disha Property", business_name),
            ("Kalyan Property", business_name),
            ("Jama Masjid, Bariatu Rd, near RIMS Circle, Bariatu, Ranchi, Jharkhand 834009", address),
            ("Shop No 14, Kamani Center, Bistupur, Jamshedpur", address),
            ("Kishoreganj, 2nd floor, Samridhi Square, Chowk, Harmu Rd, Ranchi, Jharkhand 834001", address),
            ("Kishoreganj, 2nd floor, Samridhi Square, Chowk, Harmu Rd, Ranchi", address),
            ("contact@dishaproperty.com", email),
            ("info@kalyanproperty.com", email),
            ("contact@originproperties.com", email),
            ("+91 78701 67699", phone),
            ("+917870167699", phone_digits),
            ("917870167699", phone_digits.replace("+", "")),
            ("078701 67699", phone),
            ("+91 98351 65990", phone),
            ("+919835165990", phone_digits),
            ("084070 95000", phone),
            ("+91 84070 95000", phone),
            ("Jamshedpur", city),
            ("Ranchi", city),
            ("Jharkhand", location_display),
        ]

        for file_name in html_files:
            file_path = os.path.join(target_dir, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                for old_val, new_val in replacements:
                    content = content.replace(old_val, new_val)

                # Replace any tel: links and phone anchors
                content = re.sub(r'href="tel:[^"]*"', f'href="tel:{phone_digits}"', content)
                content = re.sub(
                    r'<a\s+href="tel:[^"]*"\s*>\s*<i\s+class="fa-solid\s+fa-phone"></i>\s*</a>',
                    f'<a href="tel:{phone_digits}" aria-label="Phone"><i class="fa-solid fa-phone"></i></a>',
                    content
                )

                # Update Page Title
                content = re.sub(
                    r"<title>.*?</title>",
                    f"<title>{business_name} | Real Estate in {location_display}</title>",
                    content,
                    flags=re.IGNORECASE
                )

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                print(f"Warning: could not customize {file_path}: {e}")

    def deploy(self, site_path: str, slug: str) -> str:
        """
        Deploys the generated site to Vercel or generates a live preview link.
        """
        if self.dry_run or os.getenv("TEST_MODE") == "1":
            return f"https://{slug}.vercel.app"

        try:
            # Clean any old .vercel cache
            vercel_cache = os.path.join(site_path, ".vercel")
            if os.path.exists(vercel_cache):
                shutil.rmtree(vercel_cache)

            # Deploy to production via Vercel CLI
            cmd = ["npx.cmd", "vercel", "--prod", "--yes"]
            result = subprocess.run(
                cmd,
                cwd=site_path,
                capture_output=True,
                text=True,
                timeout=90
            )

            # Match vercel output URL: https://xxx.vercel.app
            urls = re.findall(r"https://[a-zA-Z0-9-]+\.vercel\.app", result.stdout + " " + result.stderr)
            if urls:
                return urls[-1]

            return f"https://{slug}.vercel.app"
        except Exception as e:
            print(f"Deployment error: {e}")
            return f"https://{slug}.vercel.app"

    def build_and_deploy(self, lead: Lead) -> str:
        slug = self.slugify(lead.name)
        site_path = self.build(lead)
        preview_url = self.deploy(site_path, slug)
        lead.website_preview_url = preview_url
        return preview_url

    def _generate_minimal_site(self, target_dir: str, lead: Lead):
        name = lead.name or "Premier Realty"
        city = lead.city or "Your City"
        phone = lead.phone or ""
        address = lead.address or f"{name} Office, {city}"

        index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} | Real Estate in {city}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header class="header">
        <h1>{name}</h1>
        <p>Premium Real Estate Consultant in {city}</p>
        <a href="tel:{phone}" class="btn">Call {phone}</a>
    </header>
    <main>
        <section class="about">
            <h2>About {name}</h2>
            <p>Providing trusted property and real estate advisory in {city}.</p>
            <p><strong>Location:</strong> {address}</p>
        </section>
    </main>
</body>
</html>"""
        styles_css = """body { font-family: sans-serif; margin: 0; padding: 2rem; background: #0f172a; color: #f8fafc; }
.header { text-align: center; padding: 3rem 1rem; }
.btn { display: inline-block; background: #6366f1; color: #fff; padding: 0.75rem 1.5rem; text-decoration: none; border-radius: 8px; font-weight: bold; }"""

        with open(os.path.join(target_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        with open(os.path.join(target_dir, "properties.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        with open(os.path.join(target_dir, "about.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        with open(os.path.join(target_dir, "contact.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        with open(os.path.join(target_dir, "styles.css"), "w", encoding="utf-8") as f:
            f.write(styles_css)

import os
import datetime
from typing import List, Dict, Any
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from src.models import RunMetrics

class LeadReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(24, 43, 73)
        self.cell(0, 8, "REAL ESTATE CLIENT ACQUISITION & COLD OUTREACH REPORT", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cell(0, 5, f"Automated Execution Report | Generated: {now_str}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Confidential & Proprietary", align="C")


class PDFReporter:
    def __init__(self, output_path: str = "daily_lead_report.pdf"):
        self.output_path = output_path

    def generate(self, metrics: RunMetrics, leads: List[Dict[str, Any]], cities: List[str]) -> str:
        pdf = LeadReportPDF(orientation="P", unit="mm", format="A4")
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # 1. Target Locations Section
        pdf.set_fill_color(240, 244, 248)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(20, 30, 50)
        pdf.cell(0, 8, f"Target Locations Processed: {', '.join(cities)}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

        # 2. Executive Metrics Summary Table
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, "Total Scraped", 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(45, 7, "Qualified (No Website)", 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(50, 7, "Emails Sent Today", 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(50, 7, "Duplicates Skipped", 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(45, 7, str(metrics.total_scraped), 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(45, 7, str(metrics.total_filtered_no_website), 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(50, 7, str(metrics.total_emails_sent), 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(50, 7, str(metrics.total_duplicates_skipped), 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(6)

        # 3. Processed Leads Table with Source URL Link
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(24, 43, 73)
        pdf.cell(0, 8, "Outreach Log & Verified Lead Sources", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_fill_color(225, 235, 245)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(35, 6, "Agent / Business", 1, align="L", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(18, 6, "City", 1, align="L", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(18, 6, "Source", 1, align="C", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(45, 6, "Source Profile Link", 1, align="L", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(44, 6, "Email Address", 1, align="L", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(14, 6, "Status", 1, align="C", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(16, 6, "Follow-up", 1, align="C", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 7)
        for lead in leads:
            name = (lead.get("name") or "Realtor")[:20]
            city = (lead.get("city") or "")[:10]
            src = (lead.get("source") or "")[:10]
            source_link = lead.get("profile_url") or ""
            link_display = source_link[:26] + "..." if len(source_link) > 26 else (source_link or "N/A")
            email = (lead.get("email") or "")[:26]
            status = (lead.get("status") or "SENT")[:8]
            followup = str(lead.get("followup_due_date") or "")[:10]

            pdf.cell(35, 6, name, 1, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(18, 6, city, 1, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(18, 6, src, 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
            
            # Clickable source link
            if source_link.startswith("http"):
                pdf.set_text_color(10, 80, 200)
                pdf.cell(45, 6, link_display, 1, align="L", link=source_link, new_x=XPos.RIGHT, new_y=YPos.TOP)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.cell(45, 6, link_display, 1, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)

            pdf.cell(44, 6, email, 1, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(14, 6, status, 1, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(16, 6, followup, 1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(6)

        # 4. Sample Pitch Delivered Section
        if leads and leads[0].get("email_content"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(24, 43, 73)
            pdf.cell(0, 8, "Sample Cold Email Pitch Sent", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_font("Courier", "", 7)
            pdf.set_fill_color(248, 249, 250)
            sample_text = leads[0]["email_content"]
            clean_text = sample_text.encode("ascii", "ignore").decode("ascii")
            pdf.multi_cell(0, 4, clean_text, 1, fill=True)

        os.makedirs(os.path.dirname(os.path.abspath(self.output_path)), exist_ok=True)
        pdf.output(self.output_path)
        return self.output_path

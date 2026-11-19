import os
import re
import csv
import datetime
from typing import List, Optional
from src.models import LocationInput

class SheetManager:
    """
    Manages location inputs and status updates.
    Supports CSV and Google Sheets compatible structure.
    """
    HEADER = ["Location", "Status", "Leads_Found", "Emails_Sent", "Last_Processed"]

    def __init__(self, csv_path: str = "locations.csv"):
        self.csv_path = csv_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADER)

    def get_pending_locations(self) -> List[LocationInput]:
        pending = []
        with open(self.csv_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("Status", "").strip().upper()
                loc_raw = row.get("Location", "").strip()
                if status == "PENDING" and loc_raw:
                    pending.append(LocationInput(raw_location=loc_raw))
        return pending

    def update_status(self, location: str, status: str, leads_found: int = 0, emails_sent: int = 0):
        rows = []
        with open(self.csv_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn for fn in (reader.fieldnames or self.HEADER) if fn]
            for row in reader:
                # Remove any None / extra columns from malformed rows
                row.pop(None, None)
                clean_row = {k: v for k, v in row.items() if k in fieldnames}
                if clean_row.get("Location", "").strip().lower() == location.strip().lower():
                    clean_row["Status"] = status.upper()
                    clean_row["Leads_Found"] = str(leads_found)
                    clean_row["Emails_Sent"] = str(emails_sent)
                    clean_row["Last_Processed"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows.append(clean_row)

        with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(rows)

    def add_location(self, raw_location: str):
        # Sanitize raw_location by removing stray quotes and CLI flags like --live
        clean_loc = re.sub(r'["\']', '', raw_location).split("--")[0].strip()
        if not clean_loc:
            return
        with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([clean_loc, "PENDING", "0", "0", ""])

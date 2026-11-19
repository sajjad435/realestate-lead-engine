# 🏡 Real Estate Lead Generation & Cold Outreach Engine

An automated, Test-Driven (TDD) client acquisition engine that:
1. **Reads target locations** (Cities/States like Detroit, Texas, Miami, Florida) from a Sheet/CSV.
2. **Finds Real Estate Agents** from **Google Maps** and **Instagram**.
3. **Applies Strict Filtering**: Extracts ONLY agents whose **website does not exist**, but who have a valid email address.
4. **Guarantees 0 Duplicates**: Persistent SQLite database tracks all contacted leads.
5. **Dispatches Cold Emails**: Sends personalized cold emails promoting your Website Portfolio URL with daily safe throttling (15–20 emails/day).
6. **Generates Daily PDF Reports**: Comprehensive PDF containing CRM details (Agent Name, City, Source, Email ID, Delivery Status, Follow-up Due Date, and sample pitch content).

---

## 📁 Project Structure

```
realestate-lead-engine/
├── .venv/                      # Python virtual environment
├── src/
│   ├── models.py               # Lead, Location, and RunMetrics models
│   ├── filter.py               # No-website and valid email filters
│   ├── db.py                   # SQLite deduplication & CRM tracker
│   ├── sheet_manager.py        # Location input sheet reader & updater
│   ├── mailer.py               # Cold email renderer & SMTP dispatcher
│   ├── reporter.py             # Executive PDF report generator
│   ├── config.py               # Central configuration & env vars
│   ├── scrapers/
│   │   ├── maps_finder.py      # Google Maps scraper & enricher
│   │   └── instagram_finder.py # Instagram scraper & email extractor
│   └── pipeline.py             # End-to-end pipeline orchestrator
├── tests/                      # Automated Test Suite (21/21 passing)
├── reports/                    # Generated PDF reports
├── locations.csv               # Input Sheet (City, Status, Leads_Found, Emails_Sent)
├── leads_tracker.db            # SQLite database tracking sent leads
├── main.py                     # CLI Runner
├── .env.example                # Sample environment configuration
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Activating the Environment
```powershell
cd C:\Users\HAMZHA\.gemini\antigravity\scratch\realestate-lead-engine
& .\.venv\Scripts\Activate.ps1
```

### 2. Adding Target Locations
You can edit `locations.csv` directly or use the CLI:
```powershell
python main.py --add-city "Detroit, MI"
python main.py --add-city "Texas"
python main.py --add-city "Miami, FL"
```

### 3. Running Safe Simulation (Dry-Run Mode)
```powershell
python main.py
```
This tests the full discovery, filtering, deduplication, and generates the PDF report **without sending real emails**.

### 4. Running Live Outreach (When ready)
To send real emails using your portfolio URL:
```powershell
python main.py --live --portfolio "https://yourportfolio.dev" --limit 20
```

### 5. Running the Automated Test Suite
```powershell
$env:PYTHONPATH="."
pytest tests
```
All 21 Unit & Integration tests pass with 100% success.

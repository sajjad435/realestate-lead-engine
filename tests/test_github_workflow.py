import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_requirements_file_exists_and_complete():
    req_path = PROJECT_ROOT / "requirements.txt"
    assert req_path.exists(), "requirements.txt must exist at project root for GitHub Actions"
    
    content = req_path.read_text(encoding="utf-8").lower()
    essential_packages = [
        "pydantic",
        "tzdata",
        "requests",
        "beautifulsoup4",
        "duckduckgo_search",
        "fpdf2",
        "pytest"
    ]
    for pkg in essential_packages:
        assert pkg in content, f"Essential package '{pkg}' missing from requirements.txt"

def test_github_workflow_file_exists_and_valid():
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "daily_followup.yml"
    assert workflow_path.exists(), ".github/workflows/daily_followup.yml must exist"
    
    content = workflow_path.read_text(encoding="utf-8")
    
    # 1. Triggers
    assert "workflow_dispatch:" in content, "Workflow must support manual trigger (workflow_dispatch)"
    assert "schedule:" in content, "Workflow must have automated cron schedule"
    assert "cron:" in content, "Workflow must have cron expression"
    
    # 2. Environment Secrets
    assert "SENDER_EMAIL" in content, "Workflow must reference SENDER_EMAIL secret"
    assert "SENDER_APP_PASSWORD" in content, "Workflow must reference SENDER_APP_PASSWORD secret"
    
    # 3. Execution
    assert "python main.py --followup" in content, "Workflow must execute main.py with --followup"
    
    # 4. Database Persistence (Database must be committed back so state is preserved)
    assert "git config" in content or "stefanzweifel/git-auto-commit-action" in content, "Workflow must persist leads_tracker.db changes"
    assert "leads_tracker.db" in content, "Workflow must track leads_tracker.db"

def test_followup_cli_dry_run_execution(tmp_path):
    import subprocess
    import sys
    
    # Use isolated test environment with DRY_RUN=True and empty test database
    test_db = tmp_path / "test_leads.db"
    env = os.environ.copy()
    env["DRY_RUN"] = "True"
    env["DATABASE_PATH"] = str(test_db)
    
    cmd = [sys.executable, str(PROJECT_ROOT / "main.py"), "--followup"]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, f"Followup command failed with error: {result.stderr}"
    assert "Checking for pending follow-ups" in result.stdout

def test_gitignore_protects_secrets_and_venv():
    gitignore_path = PROJECT_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist to protect sensitive secrets and heavy virtualenv"
    
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in content, ".gitignore must exclude .env to prevent leaking Gmail App Password"
    assert ".venv" in content, ".gitignore must exclude .venv"




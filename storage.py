import json
import os
from datetime import datetime

JOBS_FILE = "jobs_history.json"
jobs_store = {}

def load_jobs():
    """Load jobs from persistent storage."""
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading jobs: {e}")
            return []
    return []

def save_jobs(jobs):
    """Save jobs to persistent storage."""
    try:
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving jobs: {e}")

def get_job_stats():
    """Get statistics about stored jobs."""
    jobs = load_jobs()
    total = len(jobs)
    applied = sum(1 for j in jobs if j.get("applied"))
    pending = total - applied

    # Get unique companies
    companies = set(j.get("company", "Unknown") for j in jobs)

    # Get last scan date
    last_scan = None
    if jobs:
        last_scan = max(j.get("scraped_at", "") for j in jobs)

    return {
        "total": total,
        "applied": applied,
        "pending": pending,
        "companies": len(companies),
        "last_scan": last_scan
    }
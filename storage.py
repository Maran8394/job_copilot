import json
import os
from datetime import datetime

JOBS_FILE = "jobs_history.json"
jobs_store = {}


def _normalize_platform(value):
    text = str(value or "").strip().lower()
    if text in {"jobstreet", "jobstreet_malaysia", "my.jobstreet.com"}:
        return "jobstreet"
    return "linkedin"

def load_jobs():
    """Load jobs from persistent storage."""
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            
            # Auto-assign unique persistent IDs if missing
            if isinstance(jobs, list):
                updated = False
                for idx, job in enumerate(jobs, 1):
                    if not isinstance(job, dict):
                        continue
                    if "id" not in job or not isinstance(job["id"], int):
                        job["id"] = idx
                        updated = True
                    normalized_platform = _normalize_platform(job.get("platform"))
                    if job.get("platform") != normalized_platform:
                        job["platform"] = normalized_platform
                        updated = True
                if updated:
                    # Save back to ensure persistence of the new IDs
                    save_jobs(jobs)
            return jobs
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
    applied = sum(1 for j in jobs if j.get("applied") or j.get("status") == "submitted")
    pending = total - applied

    # Get unique companies
    companies = set(j.get("company", "Unknown") for j in jobs)
    by_platform = {}
    for job in jobs:
        platform = _normalize_platform(job.get("platform"))
        by_platform[platform] = by_platform.get(platform, 0) + 1

    # Get last scan date
    last_scan = None
    if jobs:
        last_scan = max(j.get("scraped_at", "") for j in jobs)

    return {
        "total": total,
        "applied": applied,
        "pending": pending,
        "companies": len(companies),
        "last_scan": last_scan,
        "by_platform": by_platform
    }

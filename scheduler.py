
import schedule
import time
import threading
from datetime import datetime
from linkedin import search_jobs
from telegram_bot import send_message
from storage import get_job_stats
import os

# Configuration
SEARCH_CONFIG = [
    ("AI Engineer", "Kuala Lumpur, Malaysia"),
    ("Machine Learning Engineer", "Kuala Lumpur, Malaysia"),
    ("Python Developer", "Kuala Lumpur, Malaysia"),
    ("LLM Engineer", "Kuala Lumpur, Malaysia"),
    ("AI Developer", "Kuala Lumpur, Malaysia"),
]

MAX_JOBS_PER_SEARCH = 10
RUN_DAYS = ["tuesday", "thursday"]
RUN_TIME = "09:00"  # 9 AM

def run_job_search():
    """Run the full job search cycle."""
    today = datetime.now().strftime("%A").lower()

    if today not in RUN_DAYS:
        print(f"⏭️ Today is {today}. Skipping (runs on {', '.join(RUN_DAYS)}).")
        return

    print(f"\n🚀 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting scheduled job search...")
    send_message(f"🚀 Scheduled Job Search Started!\n📅 {datetime.now().strftime('%A, %B %d')}\n\nSearching top 10 recent jobs per query...")

    total_sent = 0

    for keywords, location in SEARCH_CONFIG:
        try:
            print(f"\n{'='*50}")
            print(f"🔍 Query: {keywords} in {location}")
            print(f"{'='*50}")

            jobs = search_jobs(
                keywords=keywords,
                location=location,
                max_jobs=MAX_JOBS_PER_SEARCH
            )

            if jobs:
                total_sent += len(jobs)

            # Cooldown between searches
            time.sleep(15)

        except Exception as e:
            print(f"❌ Error in search {keywords}: {e}")
            send_message(f"⚠️ Error searching {keywords}: {str(e)[:100]}")
            continue

    # Send summary
    stats = get_job_stats()
    summary = f"""✅ Search Complete!

📊 Today's Summary:
• New jobs sent: {total_sent}
• Total in database: {stats['total']}
• Applied: {stats['applied']}
• Pending: {stats['pending']}

Next scan: Next {RUN_DAYS[0] if today == RUN_DAYS[1] else RUN_DAYS[1]} at {RUN_TIME}

Commands:
/approve_<id> - Apply to job
/answer_<id> - Save missing form answers
/decline_<id> - Skip job
/status - Show stats
"""
    send_message(summary)
    print(f"\n✅ Cycle complete. Total sent today: {total_sent}")

def manual_search():
    """Run search immediately (for testing)."""
    print("\n🔄 Running manual search...")
    run_job_search()

def start_scheduler():
    """Start the scheduler."""
    print(f"\n📅 Job Copilot Scheduler")
    print(f"Runs on: {', '.join(day.title() for day in RUN_DAYS)} at {RUN_TIME}")
    print(f"Max jobs per search: {MAX_JOBS_PER_SEARCH}")
    print(f"Search queries: {len(SEARCH_CONFIG)}")
    print(f"\n⏳ Waiting for scheduled time...\n")

    # Schedule the job
    schedule.every().tuesday.at(RUN_TIME).do(run_job_search)
    schedule.every().thursday.at(RUN_TIME).do(run_job_search)

    # Also run immediately on startup if it's a run day (optional)
    # run_job_search()

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        manual_search()
    else:
        start_scheduler()

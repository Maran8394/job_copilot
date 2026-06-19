
import schedule
import time
import threading
from datetime import datetime
from linkedin import search_jobs as search_linkedin_jobs
from jobstreet import search_jobs as search_jobstreet_jobs
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
PLATFORM_SEARCHES = [
    ("LinkedIn", search_linkedin_jobs),
    ("JobStreet Malaysia", search_jobstreet_jobs),
]


def _normalize_platform_filter(platform):
    value = str(platform or "both").strip().lower()
    if value in {"linkedin", "jobstreet", "both"}:
        return value
    return "both"


def _selected_platforms(platform_filter):
    platform_filter = _normalize_platform_filter(platform_filter)
    if platform_filter == "linkedin":
        return [("LinkedIn", search_linkedin_jobs)]
    if platform_filter == "jobstreet":
        return [("JobStreet Malaysia", search_jobstreet_jobs)]
    return PLATFORM_SEARCHES


def run_job_search(platform="both"):
    """Run the full job search cycle."""
    platform_filter = _normalize_platform_filter(platform)
    today = datetime.now().strftime("%A").lower()

    # if today not in RUN_DAYS:
    #     print(f"⏭️ Today is {today}. Skipping (runs on {', '.join(RUN_DAYS)}).")
    #     return

    print(f"\n🚀 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting scheduled job search...")
    send_message(
        f"🚀 Scheduled Job Search Started!\n"
        f"📅 {datetime.now().strftime('%A, %B %d')}\n\n"
        f"Searching {platform_filter.title() if platform_filter != 'both' else 'LinkedIn and JobStreet Malaysia'}..."
    )

    total_sent = 0
    per_platform_sent = {}

    for platform_name, search_fn in _selected_platforms(platform_filter):
        print(f"\n🧭 Platform: {platform_name}")
        platform_total = 0

        for keywords, location in SEARCH_CONFIG:
            try:
                print(f"\n{'='*50}")
                print(f"🔍 Query: {keywords} in {location}")
                print(f"{'='*50}")

                jobs = search_fn(
                    keywords=keywords,
                    location=location,
                    max_jobs=MAX_JOBS_PER_SEARCH
                )

                if jobs:
                    total_sent += len(jobs)
                    platform_total += len(jobs)

                # Cooldown between searches
                time.sleep(15)

            except Exception as e:
                print(f"❌ Error in search {platform_name} / {keywords}: {e}")
                send_message(f"⚠️ Error searching {platform_name}: {str(e)[:100]}")
                continue

        per_platform_sent[platform_name] = platform_total

    # Send summary
    stats = get_job_stats()
    summary = f"""✅ Search Complete!

📊 Today's Summary:
• New jobs sent: {total_sent}
• LinkedIn sent: {per_platform_sent.get("LinkedIn", 0)}
• JobStreet sent: {per_platform_sent.get("JobStreet Malaysia", 0)}
• Total in database: {stats['total']}
• Applied: {stats['applied']}
• Pending: {stats['pending']}

Next scan: Next {RUN_DAYS[0] if today == RUN_DAYS[1] else RUN_DAYS[1]} at {RUN_TIME}

Commands:
/approve_<id> - Apply to job
/answer_<id> - Save missing form answers
/decline_<id> - Skip job
/jobstreet_otp_<code> or /otp_<code> - Continue JobStreet login
/status - Show stats
"""
    send_message(summary)
    print(f"\n✅ Cycle complete. Total sent today: {total_sent}")


def manual_search(platform="both"):
    """Run search immediately (for testing)."""
    print("\n🔄 Running manual search...")
    run_job_search(platform=platform)


def start_scheduler(platform="both"):
    """Start the scheduler."""
    platform_filter = _normalize_platform_filter(platform)
    print(f"\n📅 Job Copilot Scheduler")
    print(f"Runs on: {', '.join(day.title() for day in RUN_DAYS)} at {RUN_TIME}")
    print(f"Max jobs per search: {MAX_JOBS_PER_SEARCH}")
    print(f"Search queries: {len(SEARCH_CONFIG)}")
    print(f"Platforms: {platform_filter}")
    print(f"\n⏳ Waiting for scheduled time...\n")

    # Schedule the job
    schedule.every().tuesday.at(RUN_TIME).do(run_job_search, platform=platform_filter)
    schedule.every().thursday.at(RUN_TIME).do(run_job_search, platform=platform_filter)

    # Also run immediately on startup if it's a run day (optional)
    # run_job_search()

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    import sys

    platform = "both"
    if "--platform" in sys.argv:
        index = sys.argv.index("--platform")
        if index + 1 < len(sys.argv):
            platform = sys.argv[index + 1]

    if "--now" in sys.argv:
        manual_search(platform=platform)
    else:
        start_scheduler(platform=platform)

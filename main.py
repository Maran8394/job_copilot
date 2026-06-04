import threading
import time
import os
import sys
from dotenv import load_dotenv
from scheduler import start_scheduler, manual_search, RUN_DAYS, RUN_TIME
from listener import check_updates
from telegram_bot import send_message
from storage import get_job_stats

load_dotenv()

def main():
    print("🚀 AI Job Copilot Starting...")
    print("=" * 50)

    # Verify env vars
    required = ["BOT_TOKEN", "CHAT_ID", "NVIDIA_API_KEY"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {missing}")
        return

    # Check if manual mode
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        print("\n🔄 MANUAL MODE: Running search immediately...")
        manual_search()
        return

    # Show current stats
    stats = get_job_stats()
    print(f"📊 Current Stats:")
    print(f"   Total jobs: {stats['total']}")
    print(f"   Applied: {stats['applied']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   Companies: {stats['companies']}")
    if stats['last_scan']:
        print(f"   Last scan: {stats['last_scan'][:10]}")

    print(f"\n📅 Schedule: {', '.join(day.title() for day in RUN_DAYS)} at {RUN_TIME}")
    print(f"📋 Max jobs per search: 10")
    print(f"🔍 Queries: AI Engineer, ML Engineer, Python Dev, LLM Engineer, AI Developer")

    send_message(
        f"🚀 AI Job Copilot Started!\n\n"
        f"📅 Schedule: {', '.join(day.title() for day in RUN_DAYS)} at {RUN_TIME}\n"
        f"📊 Jobs in DB: {stats['total']} | Applied: {stats['applied']}\n\n"
        f"Commands:\n"
        f"/approve_<id> - Apply to job\n"
        f"/answer_<id> - Save missing form answers\n"
        f"/decline_<id> - Skip job\n"
        f"/status - Show stats\n"
        f"/search_now - Run search now"
    )

    # Start listener in background
    print("\n🎧 Starting Telegram listener...")
    listener_thread = threading.Thread(target=check_updates, daemon=True)
    listener_thread.start()

    # Start scheduler in main thread
    print("⏳ Starting scheduler...\n")
    time.sleep(2)
    start_scheduler()

if __name__ == "__main__":
    main()

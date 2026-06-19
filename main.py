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


def _get_arg_value(flag, default=None):
    if flag not in sys.argv:
        return default
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv):
        return default
    return sys.argv[index + 1]


def _normalize_platform(platform):
    value = str(platform or "both").strip().lower()
    if value in {"linkedin", "jobstreet", "both"}:
        return value
    return "both"

def main():
    print("🚀 AI Job Copilot Starting...")
    print("=" * 50)

    # Verify env vars
    required = ["BOT_TOKEN", "CHAT_ID", "NVIDIA_API_KEY"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {missing}")
        return

    platform = _normalize_platform(_get_arg_value("--platform", "both"))

    # Check if manual mode
    if "--now" in sys.argv:
        print("\n🔄 MANUAL MODE: Running search immediately...")
        manual_search(platform=platform)
        return

    # Show current stats
    stats = get_job_stats()
    print(f"📊 Current Stats:")
    print(f"   Total jobs: {stats['total']}")
    print(f"   Applied: {stats['applied']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   Companies: {stats['companies']}")
    if stats.get("by_platform"):
        breakdown = ", ".join(f"{name}: {count}" for name, count in stats["by_platform"].items())
        print(f"   By platform: {breakdown}")
    if stats['last_scan']:
        print(f"   Last scan: {stats['last_scan'][:10]}")

    print(f"\n📅 Schedule: {', '.join(day.title() for day in RUN_DAYS)} at {RUN_TIME}")
    print(f"🧭 Platform mode: {platform}")
    print(f"📋 Max jobs per search: 10")
    print(f"🔍 Queries: AI Engineer, ML Engineer, Python Dev, LLM Engineer, AI Developer")

    send_message(
        f"🚀 AI Job Copilot Started!\n\n"
        f"📅 Schedule: {', '.join(day.title() for day in RUN_DAYS)} at {RUN_TIME}\n"
        f"🧭 Platform: {platform}\n"
        f"📊 Jobs in DB: {stats['total']} | Applied: {stats['applied']}\n\n"
        f"Commands:\n"
        f"/approve_<id> - Apply to job\n"
        f"/answer_<id> - Save missing form answers\n"
        f"/decline_<id> - Skip job\n"
        f"/jobstreet_otp_<code> or /otp_<code> - Continue JobStreet login\n"
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
    start_scheduler(platform=platform)

if __name__ == "__main__":
    main()

import requests
import time
import os
import threading
from dotenv import load_dotenv
from candidate_profile import load_candidate_profile
from storage import jobs_store, load_jobs, save_jobs, get_job_stats
from apply import apply_to_job
from telegram_bot import send_message
from scheduler import manual_search

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
offset = None
running = True

def send_message_to_user(text):
    """Send message back to user via Telegram."""
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def process_approval(job_id):
    """Handle approved job application."""
    # Reload jobs from storage
    all_jobs = load_jobs()

    # Find job by ID (rank)
    job = None
    for j in all_jobs:
        if j.get("id") == job_id or (job_id <= len(all_jobs) and all_jobs[job_id-1]):
            job = all_jobs[job_id-1] if job_id <= len(all_jobs) else None
            break

    if not job:
        send_message_to_user(f"❌ Job {job_id} not found")
        return False, "Job not found"

    if job.get("applied"):
        send_message_to_user(f"⏭️ Already applied to Job {job_id}: {job['title']}")
        return False, "Already applied"

    print(f"Processing approval for job {job_id}: {job['title']} at {job['company']}")
    send_message_to_user(f"⏳ Starting application for Job {job_id}: {job['title']}...")

    result = apply_to_job(job, job_id=job_id)
    success = bool(result.get("success"))
    message = result.get("message", "")
    status = result.get("status", "error")
    summary = result.get("summary")

    if success and status == "submitted":
        job["applied"] = True
        job["status"] = "submitted"
        job["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_jobs(all_jobs)
        send_message_to_user(
            f"✅ Successfully applied!\n"
            f"💼 {job['title']}\n"
            f"🏢 {job['company']}\n"
            f"📍 {job.get('location', 'N/A')}"
        )
    elif status in {"ready_for_review", "needs_answers"}:
        job["status"] = status
        if summary:
            job["form_analysis"] = summary
        save_jobs(all_jobs)
        if status == "needs_answers":
            missing = summary.get("missing_fields", []) if summary else []
            missing_text = "\n".join([f"{idx + 1}. {item}" for idx, item in enumerate(missing)]) or "None"
            send_message_to_user(
                f"🧾 Form prepared for Job {job_id}:\n"
                f"{job['title']}\n"
                f"{job['company']}\n\n"
                f"Missing fields:\n{missing_text}\n\n"
                f"Reply with answers:\n"
                f"/answer_{job_id} field=value; field=value"
            )
        else:
            send_message_to_user(
                f"🧾 Form prepared for manual review:\n"
                f"{job['title']}\n"
                f"{job['company']}\n\n"
                f"LinkedIn submit was not clicked.\n"
                f"Please review and submit manually in the browser."
            )
    else:
        send_message_to_user(
            f"❌ Failed to apply to Job {job_id}:\n"
            f"{message}\n\n"
            f"🔗 Apply manually: {job.get('url', 'N/A')}"
        )

    return success, message


def handle_answer_command(job_id, payload):
    """Store user-provided answers for a pending application."""
    profile = load_candidate_profile()
    all_jobs = load_jobs()
    job = all_jobs[job_id - 1] if 0 < job_id <= len(all_jobs) else None

    if not payload.strip():
        pending = profile.pending_applications.get(str(job_id), {})
        missing = pending.get("missing_fields", [])
        if not missing and job and job.get("form_analysis"):
            missing = job["form_analysis"].get("missing_fields", [])

        missing_text = "\n".join([f"{idx + 1}. {item}" for idx, item in enumerate(missing)]) or "None"
        send_message_to_user(
            f"📝 Answer format for Job {job_id}:\n"
            f"{job['title'] if job else 'Unknown job'}\n\n"
            f"Send:\n"
            f"/answer_{job_id} field=value; field=value\n\n"
            f"Missing fields:\n{missing_text}"
        )
        return

    answers = {}
    for chunk in payload.split(";"):
        part = chunk.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            answers[key] = value

    if not answers:
        send_message_to_user(
            f"❌ Could not parse answers for Job {job_id}.\n"
            f"Use: /answer_{job_id} field=value; field=value"
        )
        return

    profile.update_custom_answers(job_id, answers)

    if job is not None:
        job["status"] = "answered"
        save_jobs(all_jobs)

    send_message_to_user(
        f"✅ Saved {len(answers)} answer(s) for Job {job_id}.\n"
        f"These values will be reused in future applications."
    )

def check_updates():
    global offset, running

    while running:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            if offset:
                url += f"?offset={offset}"

            response = requests.get(url, timeout=30).json()

            if not response.get("ok"):
                time.sleep(5)
                continue

            for result in response.get("result", []):
                offset = result["update_id"] + 1

                message = result.get("message", {})
                text = message.get("text", "")

                print(f"Received: {text}")

                if text.startswith("/approve_"):
                    try:
                        job_id = int(text.split("_")[1])
                        thread = threading.Thread(target=process_approval, args=(job_id,))
                        thread.start()
                    except (ValueError, IndexError):
                        send_message_to_user("❌ Invalid format. Use /approve_<job_id>")

                elif text.startswith("/decline_"):
                    try:
                        job_id = int(text.split("_")[1])
                        all_jobs = load_jobs()
                        if job_id <= len(all_jobs):
                            all_jobs[job_id-1]["status"] = "declined"
                            save_jobs(all_jobs)
                            send_message_to_user(
                                f"❌ Declined Job {job_id}:\n"
                                f"{all_jobs[job_id-1]['title']}"
                            )
                    except:
                        send_message_to_user("Invalid command")

                elif text.startswith("/answer_"):
                    try:
                        command, *rest = text.split(" ", 1)
                        job_id = int(command.split("_")[1])
                        payload = rest[0] if rest else ""
                        handle_answer_command(job_id, payload)
                    except (ValueError, IndexError):
                        send_message_to_user("❌ Invalid format. Use /answer_<job_id> field=value")

                elif text == "/status":
                    stats = get_job_stats()
                    send_message_to_user(
                        f"📊 Stats:\n"
                        f"Total: {stats['total']}\n"
                        f"Applied: {stats['applied']}\n"
                        f"Pending: {stats['pending']}\n"
                        f"Companies: {stats['companies']}"
                    )

                elif text == "/search_now":
                    send_message_to_user("🔄 Starting manual search...")
                    thread = threading.Thread(target=manual_search)
                    thread.start()

                elif text == "/stop":
                    running = False
                    send_message_to_user("🛑 Stopping...")

        except Exception as e:
            print(f"Listener error: {e}")

        time.sleep(2)

if __name__ == "__main__":
    print("🎧 Telegram listener started...")
    check_updates()

import requests
import os
from html import escape
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_message(text):
    """Send plain text message."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send message: {e}")

def send_job(job_id, title, company, location, posted, url, apply_type, analysis, platform="linkedin"):
    """Send job notification to Telegram."""
    summary = "\n".join([f"• {point}" for point in analysis.get("summary", [])[:3]])
    concerns = analysis.get("concerns", [])
    concerns_text = "\n".join([f"⚠️ {c}" for c in concerns[:2]]) if concerns else ""

    # Add ranking info
    rank = analysis.get("rank", job_id)
    composite = analysis.get("composite_score", analysis.get("fit_score", 0))

    text = f"""🚀 <b>Rank #{rank} - High Match Job</b>

💼 <b>{title}</b>
🏢 {company}
🌐 {platform.title()}

📍 {location}
🕒 {posted}

🎯 Fit Score: {analysis.get('fit_score', 0)}%
⭐ Composite Score: {composite}
🛂 Visa: {analysis.get('visa_sponsorship', 'unknown')}
📈 Level: {analysis.get('seniority', 'unknown')}
⚡️ Apply Type: {apply_type}

<b>Summary:</b>
{summary}

{concerns_text}

🔗 <a href="{url}">View Job</a>

/approve_{job_id}
/decline_{job_id}
"""

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        requests.post(api_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send job: {e}")


def _format_field_item(item):
    """Render a field entry from either a string or analyzer dict."""
    if isinstance(item, dict):
        label = item.get("display_label") or item.get("label") or item.get("name") or item.get("field_type") or "Unknown"
        field_type = item.get("field_type")
        value = item.get("value")
        if value not in (None, ""):
            return f"{label}: {value}"
        if field_type:
            return f"{label} ({field_type})"
        return str(label)

    return str(item)


def send_form_analysis(job_id, summary):
    """Send Easy Apply form analysis to Telegram."""
    missing_fields = summary.get("missing_fields", [])
    fillable_fields = summary.get("fillable_fields", [])
    unknown_fields = summary.get("unknown_fields", [])

    missing_text = "\n".join([f"{idx + 1}. {escape(_format_field_item(field))}" for idx, field in enumerate(missing_fields)]) or "None"
    fillable_text = "\n".join([f"{idx + 1}. {escape(_format_field_item(field))}" for idx, field in enumerate(fillable_fields)]) or "None"
    unknown_text = "\n".join([f"{idx + 1}. {escape(_format_field_item(field))}" for idx, field in enumerate(unknown_fields)]) or "None"

    text = (
        f"🧾 <b>Easy Apply Form Analysis</b>\n\n"
        f"💼 Job: <b>{escape(summary.get('job_title', 'Unknown'))}</b>\n"
        f"🏢 Company: <b>{escape(summary.get('company', 'Unknown'))}</b>\n"
        f"🎯 Autofill Confidence: {summary.get('autofill_confidence', 0.0)}\n\n"
        f"<b>Fillable Fields:</b>\n{fillable_text}\n\n"
        f"<b>Missing Fields:</b>\n{missing_text}\n\n"
        f"<b>Unknown Fields:</b>\n{unknown_text}\n\n"
        f"Reply with answers:\n"
        f"/answer_{job_id} field=value; field=value"
    )

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        requests.post(api_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send form analysis: {e}")

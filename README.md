# Job Copilot 🚀

A private automation suite for discovering job postings and handling applications via a Telegram-driven flow on LinkedIn and JobStreet Malaysia.

## 📋 Prerequisites
- Python 3.10+
- Google Chrome installed locally
- Telegram Account & Bot Token

## 🛠️ Setup Instructions

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   git clone git@github.com:Maran8394/job_copilot.git
   cd job_copilot
   ```

2. **Set up the virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

5. **Configure Environment Variables**:
   Copy the example environment file and fill in your details:
   ```bash
   cp .env.example .env
   ```
   **Required `.env` Variables:**
   - `BOT_TOKEN`: Your Telegram Bot API Token.
   - `CHAT_ID`: Your Telegram Chat ID.
   - `NVIDIA_API_KEY`: API Key for LLM processing (NVIDIA).
   - `EMAIL` or `JOBSTREET_EMAIL`: Email used for JobStreet login if the site asks for OTP.
   - `JOBSTREET_PASSWORD` is optional and only needed if JobStreet prompts for a password before OTP.

## 🚀 Running the Project

### Start the full suite (Scheduler + Listener + Bot)
This starts the background job scheduler and the Telegram listener.
```bash
python main.py
```

### Run an immediate job search
To bypass the scheduler and run an immediate search cycle across LinkedIn and JobStreet:
```bash
python main.py --now
```
You can restrict the platform with:
```bash
python main.py --now --platform linkedin
python main.py --now --platform jobstreet
python main.py --now --platform both
```

### Run only the Telegram listener
If you just want to listen for `/approve_<id>` or `/status` commands without running searches:
```bash
python listener.py
```

### Run only the Job Scheduler
To run a manual search cycle directly via the scheduler script:
```bash
python scheduler.py --now
```
Platform selection works there too:
```bash
python scheduler.py --now --platform linkedin
python scheduler.py --now --platform jobstreet
```

## 📂 Project Structure

- `main.py` - Primary entrypoint to start all services.
- `scheduler.py` - Controls scheduled and manual job search runs.
- `listener.py` - Polls for Telegram commands (e.g., `/approve_<id>`, `/status`, `/jobstreet_otp_<code>`).
- `telegram_bot.py` - Handles sending notifications and job cards to Telegram.
- `linkedin.py` & `apply.py` - LinkedIn scraping and Easy Apply flows.
- `jobstreet.py` - JobStreet Malaysia scraping, OTP login, and application flow.
- `llm.py`, `candidate_profile.py`, `easy_apply_analyzer.py`, `field_mapper.py` - LLM analysis and application field mapping logic.
- `storage.py` - Reads and writes persistent job data.
- `jobs_history.json` - Persistent local storage of job state (ignored in git).
- `browser_profile/` - Persistent Chrome profiles for Playwright (ignored in git).

## ⚠️ Notes
- **Do not commit** `.env`, `jobs_history.json`, or `browser_profile/`. These contain personal data and credentials.
- Ensure your Telegram bot is running to receive job alerts and trigger the application processes.

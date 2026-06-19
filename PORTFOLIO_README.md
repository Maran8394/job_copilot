# 🚀 Job Copilot: Automated Job Discovery & Application Assistant

> **Note:** This repository is kept private as it contains personal configurations and automation scripts. This README serves as an architectural overview and portfolio showcase of the project.

## 📖 Overview

**Job Copilot** is a Python automation project designed to streamline the job search and application process. It discovers LinkedIn job postings, delivers them to a Telegram chat for review, and prepares Easy Apply forms for manual submission after user approval. The system uses Playwright for browser automation and a local candidate profile plus field-mapping layer to autofill supported fields without auto-submitting applications.

## ✨ Key Features

- **Automated Job Scraping:** Uses Playwright browser automation to search for tailored job postings on LinkedIn based on configurable criteria.
- **Telegram Integration:** Delivers detailed, formatted job cards directly to Telegram. Users can review jobs on the go without logging into job boards.
- **Interactive Approval Flow:** Users can approve or reject jobs directly via Telegram commands (e.g., `/approve_12345`).
- **Easy Apply Form Analyzer:** When a job is approved, the system launches a Playwright session to inspect the Easy Apply form, classify visible fields, and autofill only high-confidence supported inputs.
- **Candidate Profile Autofill:** Candidate data comes from `.env` and optional `candidate_profile.json`, including answers saved from Telegram for future reuse.
- **Manual Submission Control:** The flow stops before final submission, so the user retains control over whether to click Submit in the browser.
- **State Management:** Maintains a robust local history (`jobs_history.json`) to prevent duplicate applications and track application statuses.

## 🛠️ Technology Stack

- **Language:** Python 3.10+
- **Browser Automation:** [Playwright](https://playwright.dev/python/) for robust, undetectable headless scraping and form submission.
- **Messaging:** Telegram Bot API via direct HTTP requests for push notifications and command polling.
- **AI / LLMs:** NVIDIA API is used for job analysis in `llm.py`; the Easy Apply form flow itself uses rule-based field mapping and profile data.
- **Environment Management:** `python-dotenv` for secret management.

## 🧠 How It Works

1. **The Scheduler (`scheduler.py`):** Wakes up at predefined intervals to initiate a job search cycle.
2. **The Scraper (`linkedin.py`):** Uses a persistent Playwright browser profile to navigate LinkedIn, extract job postings, and filter out irrelevant or already-processed jobs.
3. **The Notifier (`telegram_bot.py`):** Formats the discovered jobs and pushes them to the user's Telegram app.
4. **The Listener (`listener.py`):** Continuously polls Telegram for user commands. 
5. **The Application Flow (`apply.py`, `easy_apply_analyzer.py`, `field_mapper.py`, `candidate_profile.py`):** When the listener detects an `/approve_<id>` command, it spins up an application worker. The worker navigates to the job page, inspects the Easy Apply form, maps visible fields to candidate profile data, autofills supported fields, and stops before final submission. If LinkedIn asks for missing answers, the bot sends a Telegram prompt and stores the response in `candidate_profile.json` for reuse.

## 💡 Why I Built This

The modern job search is incredibly repetitive and time-consuming. I wanted to build a system that abstracted away the manual labor of finding and preparing applications, allowing me to review high-quality opportunities asynchronously via my phone, autofill what can be safely inferred, and keep final submission under manual control.

This project allowed me to dive deep into **advanced web automation**, **stateful conversational bots**, and **practical form analysis** for dynamic web applications.

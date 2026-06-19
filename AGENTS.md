# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python automation project for job discovery and Telegram-driven application flow.

- `main.py` is the primary entrypoint.
- `scheduler.py` controls scheduled and manual search runs.
- `linkedin.py` and `apply.py` handle Playwright-based scraping and Easy Apply flows.
- `listener.py` polls Telegram commands such as `/approve_<id>` and `/status`.
- `storage.py` reads and writes persistent job data in `jobs_history.json`.
- `telegram_bot.py` sends notifications to Telegram.
- `browser_profile/` stores the persistent Chrome profile used by Playwright.

## Build, Test, and Development Commands
Use the project virtual environment and install dependencies from `requirements.txt`.

- `python main.py` starts the bot, listener, and scheduler.
- `python main.py --now` runs one immediate search cycle.
- `python scheduler.py --now` runs the scheduler job search directly.
- `python listener.py` starts only the Telegram update loop.
- `python apply.py` is not a normal entrypoint; it is called from the approval flow.

## Coding Style & Naming Conventions
Use standard Python style: 4-space indentation, `snake_case` for functions and variables, and `UPPER_CASE` for configuration constants such as `RUN_TIME` and `SEARCH_CONFIG`.

- Prefer small helper functions and explicit `try/except` blocks around network and browser actions.
- Keep user-facing log and Telegram messages short and actionable.
- Avoid introducing new dependencies unless they are required for Playwright, HTTP, or scheduling work.

## Testing Guidelines
There is no automated test suite in the repository today. When changing behavior, validate manually by:

- running `python main.py --now`
- checking `jobs_history.json` updates
- confirming Telegram commands such as `/status` and `/approve_<id>`

If you add tests, place them under `tests/` and name them `test_*.py`.

## Configuration & Secrets
Runtime settings come from environment variables loaded with `python-dotenv`. Required values include `BOT_TOKEN`, `CHAT_ID`, and `NVIDIA_API_KEY`.

- Do not commit secrets, browser session data, or personal job history.
- Treat `browser_profile/` and `jobs_history.json` as local state.

## Commit & Pull Request Guidelines
No git history is available in this workspace, so there is no established commit convention to mirror. Use clear, imperative commit messages such as `Fix Telegram approval handling`.

Pull requests should include:

- a brief summary of behavior changes
- manual verification steps
- screenshots or sample Telegram output when the UI/message flow changes

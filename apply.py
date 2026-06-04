import os
import random
import time

from playwright.sync_api import Error, TimeoutError as PlaywrightTimeout, sync_playwright

from candidate_profile import load_candidate_profile
from easy_apply_analyzer import EasyApplyAnalyzer
from field_mapper import validate_value
from telegram_bot import send_form_analysis


AUTOFILL_THRESHOLD = 0.82


def human_like_delay(min_ms=500, max_ms=2000):
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def _page_locator(page, scope_selector, selector):
    if scope_selector and scope_selector != "body":
        return page.locator(f"{scope_selector} {selector}")
    return page.locator(selector)


def _safe_fill(locator, value):
    try:
        locator.fill(str(value))
        return True
    except Exception:
        return False


def _safe_click(locator):
    try:
        locator.first.click()
        return True
    except Exception:
        return False


def _select_option(locator, field, value):
    option_labels = [str(option).strip() for option in field.get("options", []) if str(option).strip()]
    text_value = str(value).strip()

    choices = []
    if isinstance(value, bool):
        if option_labels:
            yes_choices = [opt for opt in option_labels if opt.lower() in {"yes", "true", "y", "1"}]
            no_choices = [opt for opt in option_labels if opt.lower() in {"no", "false", "n", "0"}]
            choices = yes_choices if value else no_choices
        choices = choices or (["Yes"] if value else ["No"])
    elif option_labels:
        if text_value:
            choices.append(text_value)
        if text_value.lower() in {"yes", "no"}:
            choices.append(text_value.title())
    else:
        choices.append(text_value)

    for choice in choices:
        try:
            locator.select_option(label=choice)
            return True
        except Exception:
            try:
                locator.select_option(value=choice)
                return True
            except Exception:
                continue

    return False


def _click_choice_by_label(page, field, value):
    option_labels = [str(option).strip() for option in field.get("options", []) if str(option).strip()]
    if not option_labels:
        return False

    desired_labels = []
    if isinstance(value, bool):
        desired_labels = [
            label
            for label in option_labels
            if label.lower() in ({"yes", "true", "y", "1"} if value else {"no", "false", "n", "0"})
        ]
    else:
        desired = str(value).strip().lower()
        desired_labels = [label for label in option_labels if label.lower() == desired]

    if not desired_labels:
        return False

    for label in desired_labels:
        try:
            if _safe_click(page.get_by_label(label, exact=True)):
                return True
        except Exception:
            continue

    for label in desired_labels:
        try:
            if _safe_click(page.get_by_role("radio", name=label)):
                return True
        except Exception:
            continue

    for label in desired_labels:
        try:
            if _safe_click(page.get_by_role("checkbox", name=label)):
                return True
        except Exception:
            continue

    return False


def _autofill_field(page, field, profile):
    field_type = field.get("field_type", "unknown")
    confidence = float(field.get("confidence", 0.0) or 0.0)
    value = field.get("value")
    label = field.get("label", "")

    if confidence < AUTOFILL_THRESHOLD or value is None:
        return False, "low-confidence-or-missing"

    if not validate_value(field_type, value):
        return False, "invalid-value"

    selector = field.get("selector", "")
    index = int(field.get("index", 0))
    dom_type = field.get("dom_type", "")
    scope_selector = field.get("scope_selector", "body")
    locator = _page_locator(page, scope_selector, selector).nth(index)

    try:
        if dom_type in {"input", "textarea"} and field_type not in {"sponsorship", "work_authorization", "relocation"}:
            if _safe_fill(locator, value):
                print(f"[AUTOFILL] Filled value: {value}")
                return True, "filled"
            return False, "fill-failed"

        if dom_type == "select":
            if _select_option(locator, field, value):
                print(f"[AUTOFILL] Filled value: {value}")
                return True, "filled"
            return False, "select-failed"

        if dom_type in {"radio", "checkbox"}:
            if _click_choice_by_label(page, field, value):
                print(f"[AUTOFILL] Filled value: {value}")
                return True, "filled"
            if isinstance(value, bool):
                try:
                    if value:
                        locator.check()
                        print(f"[AUTOFILL] Checked value: {label}")
                        return True, "filled"
                    return True, "skipped-unchecked"
                except Exception:
                    pass
            return False, "choice-failed"

    except Exception as exc:
        print(f"[AUTOFILL] Failed for {label}: {exc}")
        return False, "error"

    return False, "unsupported"


def _apply_fields(page, summary):
    profile = load_candidate_profile()
    scope_selector = summary.get("scope_selector", "body")
    autofilled = 0

    for field in summary.get("fields", []):
        field = dict(field)
        field["scope_selector"] = scope_selector
        if field.get("status") != "fillable":
            continue

        field_type = field.get("field_type", "unknown")
        value = field.get("value")
        if value is None:
            continue

        if not validate_value(field_type, value):
            continue

        filled, reason = _autofill_field(page, field, profile)
        if filled:
            autofilled += 1
        else:
            print(f"[FIELD] Skipped {field.get('label', '')} -> {reason}")

    return autofilled


def _find_button(page, texts):
    selectors = []
    for text in texts:
        selectors.extend(
            [
                f"button:has-text('{text}')",
                f"[role='button']:has-text('{text}')",
            ]
        )

    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                return locator.first
        except Exception:
            continue
    return None


def handle_easy_apply(page, job_data, job_id=None):
    """Handles LinkedIn Easy Apply multi-step form without final submission."""
    analyzer = EasyApplyAnalyzer()
    profile = load_candidate_profile()
    job_key = job_id if job_id is not None else job_data.get("id")

    try:
        apply_btn = page.locator("button.jobs-apply-button:has-text('Easy Apply')")
        if apply_btn.count() == 0:
            return {
                "success": False,
                "status": "unsupported",
                "message": "Easy Apply button not found",
            }

        apply_btn.first.click()
        human_like_delay(1500, 3000)

        max_steps = 8
        step = 0
        last_summary = None

        while step < max_steps:
            step += 1
            print(f"[FORM] Step {step}")
            human_like_delay(800, 1800)

            summary = analyzer.analyze(page, job_data)
            summary["scope_selector"] = analyzer.find_scope_selector(page)
            last_summary = summary
            print(
                f"[FORM] fields={summary.get('field_count', 0)} "
                f"fillable={len(summary.get('fillable_fields', []))} "
                f"missing={len(summary.get('missing_fields', []))}"
            )

            if job_key is not None:
                profile.store_pending_application(job_key, summary)

            autofilled = _apply_fields(page, summary)
            print(f"[AUTOFILL] Filled {autofilled} field(s)")

            post_fill_summary = analyzer.analyze(page, job_data)
            post_fill_summary["scope_selector"] = analyzer.find_scope_selector(page)
            last_summary = post_fill_summary
            if job_key is not None:
                profile.store_pending_application(job_key, post_fill_summary)

            if post_fill_summary.get("missing_fields"):
                send_form_analysis(job_key or job_data.get("title", "job"), post_fill_summary)
                return {
                    "success": False,
                    "status": "needs_answers",
                    "message": "Missing fields detected; waiting for user answers",
                    "summary": post_fill_summary,
                }

            submit_btn = _find_button(page, ["Submit application", "Send application"])
            if submit_btn is not None:
                send_form_analysis(job_key or job_data.get("title", "job"), post_fill_summary)
                return {
                    "success": True,
                    "status": "ready_for_review",
                    "message": "Form prepared for manual submission",
                    "summary": post_fill_summary,
                }

            review_btn = _find_button(page, ["Review"])
            next_btn = _find_button(page, ["Next"])

            if review_btn is not None:
                review_btn.click()
                human_like_delay(1200, 2200)
                continue

            if next_btn is not None:
                next_btn.click()
                human_like_delay(1200, 2200)
                continue

            if page.locator(".jobs-easy-apply-content").count() == 0:
                return {
                    "success": False,
                    "status": "closed",
                    "message": "Apply modal closed unexpectedly",
                    "summary": summary,
                }

            primary_btn = page.locator("button.artdeco-button--primary")
            if primary_btn.count() > 0:
                try:
                    primary_btn.first.click()
                    human_like_delay(1200, 2200)
                    continue
                except Exception:
                    pass

            break

        if last_summary is not None:
            send_form_analysis(job_key or job_data.get("title", "job"), last_summary)

        return {
            "success": True,
            "status": "ready_for_review",
            "message": "Form prepared for manual submission",
            "summary": last_summary,
        }

    except Exception as exc:
        return {
            "success": False,
            "status": "error",
            "message": f"Error during apply: {exc}",
        }


def apply_to_job(job_data, job_id=None):
    """Main entry point: inspect and prepare a LinkedIn Easy Apply application."""
    if not job_data:
        return {
            "success": False,
            "status": "error",
            "message": "No job data provided",
        }

    if job_data.get("apply_type") != "Easy Apply":
        return {
            "success": False,
            "status": "unsupported",
            "message": "Not an Easy Apply job",
        }

    with sync_playwright() as p:
        browser = None
        try:
            launch_args = {
                "user_data_dir": "./browser_profile",
                "headless": False,
                "slow_mo": 300,
                "args": ["--disable-blink-features=AutomationControlled"],
            }

            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    launch_args["executable_path"] = path
                    break

            browser = p.chromium.launch_persistent_context(**launch_args)
            page = browser.new_page()

            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """
            )

            print(f"  Navigating to job: {job_data['url']}")
            page.goto(job_data["url"], wait_until="networkidle", timeout=30000)
            human_like_delay(3000, 5000)

            result = handle_easy_apply(page, job_data, job_id=job_id)
            return result

        except Exception as exc:
            return {
                "success": False,
                "status": "error",
                "message": f"Browser error: {exc}",
            }
        finally:
            if browser:
                browser.close()


if __name__ == "__main__":
    print("Apply module - use via listener")

from playwright.sync_api import Error, sync_playwright, TimeoutError as PlaywrightTimeout
from telegram_bot import send_job
from storage import jobs_store, save_jobs, load_jobs
from llm import analyze_job
import time
import random
from datetime import datetime

# Updated selectors for current LinkedIn UI
SELECTORS = {
    "job_card": "li.scaffold-layout__list-item, li.jobs-search-results__list-item",
    "title": "strong, a.job-card-list__title, .job-card-container__link",
    "company": ".artdeco-entity-lockup__subtitle, .job-card-container__company-name",
    "description": ".jobs-description__content, .jobs-box__html-content",
    "location": ".job-details-jobs-unified-top-card__primary-description-container, .job-card-container__metadata-wrapper",
    "posted": "span.tvm__text, .job-search-card__listdate",
    "apply_button": "button.jobs-apply-button",
    "job_cards_container": ".jobs-search-results-list",
    "sort_button": "button[aria-label*='Sort']",
    "most_recent_option": "button[role='menuitemradio']:has-text('Most recent')"
}

def get_search_url(keywords="AI Engineer", location="Kuala Lumpur, Malaysia"):
    return (
        "https://www.linkedin.com/jobs/search/"
        f"?keywords={keywords.replace(' ', '%20')}"
        f"&location={location.replace(' ', '%20')}"
        "&f_AL=true"
        "&sortBy=R"  # R = Most Recent
    )

def human_like_delay(min_ms=800, max_ms=2500):
    time.sleep(random.uniform(min_ms, max_ms) / 1000)

def scroll_jobs_list(page):
    """Scroll the jobs list to load more items."""
    try:
        for _ in range(5):
            page.evaluate("""
                const list = document.querySelector('.jobs-search-results-list');
                if (list) list.scrollTop = list.scrollHeight;
            """)
            human_like_delay(1000, 2000)
    except:
        pass

def sort_by_most_recent(page):
    """Click sort dropdown and select Most Recent."""
    try:
        # Try to find and click sort button
        sort_btn = page.locator(SELECTORS["sort_button"])
        if sort_btn.count() > 0:
            sort_btn.first.click()
            human_like_delay(1000, 2000)

            # Click Most Recent option
            recent_opt = page.locator(SELECTORS["most_recent_option"])
            if recent_opt.count() > 0:
                recent_opt.first.click()
                human_like_delay(2000, 3000)
                print("Sorted by Most Recent")
                return True
    except Exception as e:
        print(f"Could not sort by most recent: {e}")
    return False

def parse_posted_time(posted_text):
    """Convert LinkedIn posted text to hours for sorting."""
    posted_lower = posted_text.lower()

    if "hour" in posted_lower or "hr" in posted_lower:
        # Extract number
        import re
        match = re.search(r'(\d+)', posted_lower)
        if match:
            return int(match.group(1))
        return 1
    elif "minute" in posted_lower or "min" in posted_lower:
        return 0
    elif "day" in posted_lower or "d" in posted_lower:
        match = re.search(r'(\d+)', posted_lower)
        if match:
            return int(match.group(1)) * 24
        return 24
    elif "week" in posted_lower or "w" in posted_lower:
        match = re.search(r'(\d+)', posted_lower)
        if match:
            return int(match.group(1)) * 24 * 7
        return 24 * 7
    elif "month" in posted_lower or "mo" in posted_lower:
        return 24 * 30
    else:
        return 999  # Unknown = oldest

def rank_jobs(jobs_data):
    """Rank jobs by fit score and recency."""
    scored_jobs = []

    for job in jobs_data:
        analysis = job.get("analysis", {})
        fit_score = analysis.get("fit_score", 0)
        posted_hours = job.get("posted_hours", 999)
        visa = analysis.get("visa_sponsorship", "unclear")
        seniority = analysis.get("seniority", "unknown")

        # Calculate composite score
        # Fit score is 70% weight, recency is 30% weight
        # Normalize recency: newer = higher score (max 100 for < 1 hour)
        recency_score = max(0, 100 - (posted_hours * 2))

        # Visa bonus: likely = +10 points
        visa_bonus = 10 if visa == "likely" else 0

        # Seniority bonus: mid-level preferred
        seniority_bonus = 0
        if seniority == "mid":
            seniority_bonus = 5
        elif seniority == "junior":
            seniority_bonus = 3

        composite_score = (fit_score * 0.7) + (recency_score * 0.3) + visa_bonus + seniority_bonus

        scored_jobs.append({
            **job,
            "composite_score": round(composite_score, 1),
            "recency_score": recency_score
        })

    # Sort by composite score descending
    scored_jobs.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored_jobs

def search_jobs(keywords="AI Engineer", location="Kuala Lumpur, Malaysia", max_jobs=10):
    search_url = get_search_url(keywords, location)

    with sync_playwright() as p:
        browser = None
        all_jobs = []

        def handle_route(route):
            try:
                if route.request.resource_type in ["image", "font", "media", "stylesheet"]:
                    route.abort()
                else:
                    route.continue_()
            except Error:
                pass

        try:
            # Cross-platform Chrome detection
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            ]

            executable_path = None
            import os as os_module
            for path in chrome_paths:
                if os_module.path.exists(path):
                    executable_path = path
                    break

            launch_args = {
                "user_data_dir": "./browser_profile",
                "headless": False,
                "slow_mo": random.randint(300, 700),
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    f"--window-size={random.randint(1200,1400)},{random.randint(800,1000)}",
                ]
            }

            if executable_path:
                launch_args["executable_path"] = executable_path

            browser = p.chromium.launch_persistent_context(**launch_args)
            page = browser.new_page()
            page.route("**/*", handle_route)

            # Stealth
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
            """)

            print(f"\n🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Searching: {keywords} in {location}")
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            human_like_delay(4000, 6000)

            # Sort by most recent
            sort_by_most_recent(page)

            # Scroll to load more jobs
            scroll_jobs_list(page)

            # Try multiple selectors for job cards
            jobs = []
            for selector in SELECTORS["job_card"].split(", "):
                jobs = page.locator(selector).all()
                if jobs:
                    print(f"Found {len(jobs)} jobs using selector: {selector}")
                    break

            if not jobs:
                print("No jobs found.")
                return []

            print(f"\n📋 Processing up to {min(len(jobs), 15)} jobs...")

            for idx, job in enumerate(jobs[:15]):  # Process first 15 to get top 10
                try:
                    job.click()
                    human_like_delay(2000, 4000)

                    # Extract title
                    title = "Unknown"
                    for sel in SELECTORS["title"].split(", "):
                        try:
                            title = page.locator(sel).first.inner_text(timeout=2000).strip()
                            if title:
                                break
                        except:
                            continue

                    # Extract company
                    company = "Unknown"
                    for sel in SELECTORS["company"].split(", "):
                        try:
                            company = page.locator(sel).first.inner_text(timeout=2000).strip()
                            if company:
                                break
                        except:
                            continue

                    # Extract description
                    description = ""
                    for sel in SELECTORS["description"].split(", "):
                        try:
                            description = page.locator(sel).inner_text(timeout=3000)
                            if description:
                                break
                        except:
                            continue

                    # Extract location
                    location_text = "Unknown"
                    for sel in SELECTORS["location"].split(", "):
                        try:
                            location_text = page.locator(sel).first.inner_text(timeout=2000).strip()
                            if location_text and location_text != company:
                                break
                        except:
                            continue

                    # Extract posted time
                    posted = "Unknown"
                    for sel in SELECTORS["posted"].split(", "):
                        try:
                            posted = page.locator(sel).first.inner_text(timeout=2000).strip()
                            if posted:
                                break
                        except:
                            continue

                    # Determine apply type
                    apply_type = "External"
                    try:
                        apply_text = page.locator(SELECTORS["apply_button"]).inner_text(timeout=2000)
                        if "Easy Apply" in apply_text:
                            apply_type = "Easy Apply"
                    except:
                        pass

                    # Check if already applied
                    try:
                        if page.locator("span.artdeco-button__text:has-text('Applied')").count() > 0:
                            print(f"  ↳ Skipping already applied: {title}")
                            continue
                    except:
                        pass

                    current_url = page.url
                    posted_hours = parse_posted_time(posted)

                    print(f"\n  [{idx+1}] {title} @ {company}")
                    print(f"      Posted: {posted} | Apply: {apply_type}")

                    # LLM Analysis
                    if not description:
                        print(f"      ⚠️ No description, skipping")
                        continue

                    analysis = analyze_job(description)

                    if not analysis:
                        print(f"      ⚠️ LLM analysis failed, skipping")
                        continue

                    fit_score = analysis.get("fit_score", 0)
                    visa = analysis.get("visa_sponsorship", "unclear")
                    seniority = analysis.get("seniority", "unknown")

                    print(f"      Fit: {fit_score}% | Visa: {visa} | Level: {seniority}")

                    # Store for ranking
                    job_data = {
                        "title": title,
                        "company": company,
                        "location": location_text,
                        "posted": posted,
                        "posted_hours": posted_hours,
                        "url": current_url,
                        "apply_type": apply_type,
                        "description": description,
                        "analysis": analysis,
                        "scraped_at": datetime.now().isoformat(),
                        "keywords": keywords,
                        "search_location": location
                    }
                    all_jobs.append(job_data)

                except Exception as e:
                    print(f"  ❌ Error processing job {idx+1}: {e}")
                    continue

        except Exception as e:
            print(f"Browser error: {e}")
        finally:
            if browser is not None:
                browser.close()

        # Rank all collected jobs
        print(f"\n📊 Ranking {len(all_jobs)} jobs...")
        ranked_jobs = rank_jobs(all_jobs)

        # Send top 10 to Telegram
        top_jobs = ranked_jobs[:max_jobs]
        print(f"\n🏆 Top {len(top_jobs)} Jobs:\n")

        # Load existing jobs to avoid duplicates
        existing = load_jobs()
        existing_urls = {j.get("url") for j in existing}

        sent_count = 0
        for rank, job in enumerate(top_jobs, 1):
            # Skip duplicates
            if job["url"] in existing_urls:
                print(f"  [{rank}] ⏭️ Already sent: {job['title']}")
                continue

            analysis = job["analysis"]
            composite = job.get("composite_score", 0)

            print(f"  [{rank}] ⭐ {job['title']} @ {job['company']} (Score: {composite})")

            # Add rank to analysis for display
            analysis["rank"] = rank
            analysis["composite_score"] = composite

            send_job(
                rank,
                job["title"],
                job["company"],
                job["location"],
                job["posted"],
                job["url"],
                job["apply_type"],
                analysis
            )

            # Store with rank as ID
            jobs_store[rank] = job
            existing.append(job)
            sent_count += 1

        # Save to persistent storage
        save_jobs(existing)

        print(f"\n✅ Sent {sent_count} new jobs to Telegram")
        print(f"📁 Total stored jobs: {len(existing)}")

        return top_jobs

if __name__ == "__main__":
    search_jobs()
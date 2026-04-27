"""
scraper.py
----------
Weekly scraper for Google Play Store reviews across 5 major AI products:
ChatGPT, Claude, Google Gemini, Microsoft Copilot, and Perplexity.

Behaviour:
  - First run (no last_run.json):
      Fetches reviews within the fixed HISTORY_START ~ HISTORY_END window
      for ALL apps, ensuring a fair and consistent time-comparable dataset.
      Fetch count is set high (FIRST_RUN_COUNT) so we don't artificially
      cap popular apps — date filtering does the real bounding work.

  - Subsequent runs (weekly):
      Fetches only reviews posted after the last recorded run time,
      keeping the dataset continuously up-to-date without duplicates.

Why fixed time window?
  Without it, high-traffic apps (ChatGPT) fill 5000 reviews in 2 days,
  while low-traffic apps (Perplexity) need 60 days. Sentiment comparisons
  across different time windows are misleading — events like outages or
  feature launches affect scores but only appear in some apps' data.

Deduplication is applied via reviewId as a safety net.

Run manually : python scraper.py
Scheduled    : via cron or GitHub Actions (weekly)

Output:
  - Appends new rows to CSV_FILE
  - Updates last_run.json with the current run timestamp
  - Appends to scraper_log.txt
"""

import pandas as pd
import json
import os
from datetime import datetime, timezone
from google_play_scraper import reviews, Sort

# ── Config ─────────────────────────────────────────────────────────────────────
APPS = {
    'ChatGPT':           'com.openai.chatgpt',
    'Claude':            'com.anthropic.claude',
    'Google_Gemini':     'com.google.android.apps.bard',
    'Microsoft_Copilot': 'com.microsoft.copilot',
    'Perplexity':        'ai.perplexity.app.android',
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE      = os.path.join(BASE_DIR, '..', 'data', 'reviews_live.csv')
LOG_FILE      = os.path.join(BASE_DIR, '..', 'logs', 'scraper_log.txt')
LAST_RUN_FILE = os.path.join(BASE_DIR, '..', 'logs', 'last_run.json')

# ── Time window for first run (backfill) ───────────────────────────────────────
# All apps will be filtered to this SAME window so comparisons are fair.
# Adjust HISTORY_END to today's date when you re-run a fresh backfill.
HISTORY_START = datetime(2026,4, 1, tzinfo=timezone.utc)   # Q1 2026 start
HISTORY_END   = datetime(2026, 4, 24, tzinfo=timezone.utc)  # Q1 2026 end

# Set high enough that we don't hit the cap before the date filter does.
# ChatGPT may have 100k+ reviews in this window — 50k gives us headroom.
FIRST_RUN_COUNT  = 100000
SUBSEQUENT_COUNT = 20000   # max to fetch per app on weekly runs

# ── Logging ────────────────────────────────────────────────────────────────────
def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

# ── Last run time ──────────────────────────────────────────────────────────────
def load_last_run():
    """Return the last run datetime (UTC-aware), or None if first run."""
    if not os.path.exists(LAST_RUN_FILE):
        return None
    with open(LAST_RUN_FILE, 'r') as f:
        data = json.load(f)
    dt = datetime.fromisoformat(data['last_run'])
    # Ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def save_last_run(dt):
    os.makedirs(os.path.dirname(LAST_RUN_FILE), exist_ok=True)
    with open(LAST_RUN_FILE, 'w') as f:
        json.dump({'last_run': dt.isoformat()}, f)

# ── Scrape ─────────────────────────────────────────────────────────────────────
def scrape_app(app_name, package_id, date_from, date_to, count):
    """
    Fetch reviews for one app between date_from and date_to (both inclusive).

    date_from : datetime (tz-aware) — only keep reviews AFTER this
    date_to   : datetime (tz-aware) — only keep reviews AT OR BEFORE this
                Set to None for weekly runs (no upper bound needed)
    count     : max reviews to fetch from the API before date filtering
    """
    try:
        result, _ = reviews(
            package_id,
            lang='en',
            country='us',
            sort=Sort.NEWEST,
            count=count
        )

        filtered = []
        for r in result:
            review_dt = r['at']
            # Make tz-aware if needed
            if review_dt.tzinfo is None:
                review_dt = review_dt.replace(tzinfo=timezone.utc)

            # Lower bound: must be after date_from
            if review_dt <= date_from:
                continue
            # Upper bound: only applied on first run
            if date_to and review_dt > date_to:
                continue
            filtered.append(r)

        rows = []
        for r in filtered:
            rows.append({
                'review_id':           r.get('reviewId', ''),
                'App':                 app_name,
                'Review_Date':         r['at'].strftime('%Y-%m-%d %H:%M:%S'),
                'Star_Rating':         r['score'],
                'Review_Text':         r.get('content', ''),
                'Word_Count':          len(str(r.get('content', '')).split()),
                'Review_Length_Chars': len(str(r.get('content', ''))),
                'Thumbs_Up_Count':     r.get('thumbsUpCount', 0),
                'App_Version':         r.get('appVersion', 'Unknown'),
                'Sentiment_Polarity':  None,
                'Review_Theme':        None,
            })

        log(f"  ✓ {app_name}: {len(rows)} reviews "
            f"({date_from.strftime('%Y-%m-%d')} → "
            f"{date_to.strftime('%Y-%m-%d') if date_to else 'now'})")
        return rows

    except Exception as e:
        log(f"  ✗ {app_name}: {e}")
        return []

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    run_time = datetime.now(tz=timezone.utc)
    last_run = load_last_run()

    log("=" * 55)

    if last_run:
        # ── Weekly incremental run ─────────────────────────────────
        log(f"Weekly run — fetching reviews since {last_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        date_from = last_run
        date_to   = None          # no upper bound, get everything up to now
        count     = SUBSEQUENT_COUNT
    else:
        # ── First run: fixed historical window ─────────────────────
        log(f"FIRST RUN — backfilling {HISTORY_START.strftime('%Y-%m-%d')} "
            f"→ {HISTORY_END.strftime('%Y-%m-%d')} (same window for all apps)")
        date_from = HISTORY_START
        date_to   = HISTORY_END
        count     = FIRST_RUN_COUNT

    # Load existing data
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    if os.path.exists(CSV_FILE):
        existing_df = pd.read_csv(CSV_FILE)
        existing_ids = set(existing_df['review_id'].dropna().tolist()) \
            if 'review_id' in existing_df.columns else set()
        log(f"Loaded existing CSV: {len(existing_df):,} rows")
    else:
        existing_df = pd.DataFrame()
        existing_ids = set()
        log("No existing CSV — will create new file")

    # Scrape all apps
    all_new_rows = []
    for app_name, package_id in APPS.items():
        rows = scrape_app(app_name, package_id, date_from, date_to, count)
        new_rows = [r for r in rows if r['review_id'] not in existing_ids]
        all_new_rows.extend(new_rows)
        existing_ids.update(r['review_id'] for r in new_rows)

    if not all_new_rows:
        log("No new reviews found")
        save_last_run(run_time)
        log("Done")
        return

    # Summary: reviews per app
    from collections import Counter
    app_counts = Counter(r['App'] for r in all_new_rows)
    log("Reviews fetched per app:")
    for app_name in APPS:
        log(f"  {app_name:25s}: {app_counts.get(app_name, 0):,}")

    # Append and save
    new_df      = pd.DataFrame(all_new_rows)
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df.to_csv(CSV_FILE, index=False)

    save_last_run(run_time)
    log(f"Added {len(all_new_rows):,} new reviews → total {len(combined_df):,} rows")
    log("Done — run clean_data.py next to fill Sentiment_Polarity and Review_Theme")

if __name__ == '__main__':
    main()
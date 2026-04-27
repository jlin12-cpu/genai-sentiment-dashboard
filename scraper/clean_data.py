"""
clean_data.py
-------------
Post-processing pipeline for newly scraped reviews.

Newly scraped reviews (appended by scraper.py) are missing two key columns
that were pre-computed in the original dataset:

  - Sentiment_Polarity : float (-1.0 to 1.0), computed via TextBlob
  - Review_Theme       : categorical, assigned via keyword-based rules
                        (mirrors the classification logic of the original dataset)

This script detects rows with missing values in these columns, fills them in,
and saves the updated CSV back to disk.

Usage:
    python clean_data.py

Expected output:
    ✓ clean_data completed — X rows updated
"""

import pandas as pd
from textblob import TextBlob

# ── Config ─────────────────────────────────────────────────────────────────────
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, '..', 'data', 'reviews_live.csv')

# ── Keyword rules (mirrors original dataset classification logic) ───────────────
# Priority order: Pricing → Bugs → Accuracy → General
PRICING_KEYWORDS = [
    'subscription', 'pay', 'paid', 'premium', 'expensive',
    'cost', 'charge', 'billing', 'refund', 'paywall',
    'upgrade', 'pricing'
]

BUGS_KEYWORDS = [
    'bug', 'crash', 'glitch', 'freeze', 'broken',
    'performance', 'lag', 'loading failed', 'not working',
    'keeps crashing'
]

ACCURACY_KEYWORDS = [
    'wrong answer', 'incorrect', 'inaccurate', 'hallucin',
    'mislead', 'unreliable', 'wrong information',
    'false information', 'logic error', 'accuracy'
]

# ── Functions ──────────────────────────────────────────────────────────────────
def compute_sentiment(text):
    """Compute TextBlob sentiment polarity for a single review text."""
    if not isinstance(text, str) or text.strip() == '':
        return 0.0
    return TextBlob(text).sentiment.polarity

def classify_theme(text):
    """
    Assign a Review_Theme based on keyword rules.
    Priority: Pricing/Subscription > Bugs/Performance > Accuracy/Logic Issues > General
    """
    if not isinstance(text, str):
        return 'General'
    text_lower = text.lower()
    if any(k in text_lower for k in PRICING_KEYWORDS):
        return 'Pricing/Subscription'
    if any(k in text_lower for k in BUGS_KEYWORDS):
        return 'Bugs/Performance'
    if any(k in text_lower for k in ACCURACY_KEYWORDS):
        return 'Accuracy/Logic Issues'
    return 'General'

def main():
    # Load CSV
    df = pd.read_csv(CSV_FILE)

    # Identify rows missing Sentiment_Polarity or Review_Theme
    missing_mask = (
        df['Sentiment_Polarity'].isna() |
        df['Review_Theme'].isna()
    )
    missing_count = missing_mask.sum()

    if missing_count == 0:
        print('✓ clean_data completed — no rows needed updating')
        return

    print(f'Found {missing_count} rows with missing fields, processing...')

    # Fill Sentiment_Polarity
    sentiment_missing = df['Sentiment_Polarity'].isna()
    if sentiment_missing.sum() > 0:
        df.loc[sentiment_missing, 'Sentiment_Polarity'] = (
            df.loc[sentiment_missing, 'Review_Text'].apply(compute_sentiment)
        )

    # Fill Review_Theme
    theme_missing = df['Review_Theme'].isna()
    if theme_missing.sum() > 0:
        df.loc[theme_missing, 'Review_Theme'] = (
            df.loc[theme_missing, 'Review_Text'].apply(classify_theme)
        )

    # Save updated CSV
    df.to_csv(CSV_FILE, index=False)
    print(f'✓ clean_data completed — {missing_count} rows updated')

if __name__ == '__main__':
    main()
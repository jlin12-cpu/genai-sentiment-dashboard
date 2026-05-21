"""
build_dashboard_data.py
-----------------------
Aggregates reviews_live.csv into insights_data.json for the dashboard.

Computes per-app statistics including:
  - Average star rating and sentiment polarity
  - Standard deviation (rating polarization)
  - Review theme counts
  - Rating distribution (1-5 stars)
  - Top keywords for positive and negative reviews
  - Sample reviews (most positive and most negative)
  - Daily and monthly time series

Run: python build_dashboard_data.py
Output: dashboard/insights_data.json
"""

import pandas as pd
import json
import numpy as np
from collections import Counter
import re
import os

# Real-word filter: log-odds tends to surface product-specific MISSPELLINGS
# (e.g. "gimini", "geminis", "nise", "supar") because they're unique to one
# product. wordfreq lets us keep only genuine English words. Falls back to a
# no-op if the library isn't installed (so the script still runs).
try:
    from wordfreq import zipf_frequency
    _HAS_WORDFREQ = True
except ImportError:
    _HAS_WORDFREQ = False
    print("  [warn] wordfreq not installed — skipping misspelling filter. "
          "Run: pip install wordfreq")

_MIN_ZIPF = 2.8   # tokens rarer than this (misspellings/slang) are dropped

from functools import lru_cache

@lru_cache(maxsize=None)
def _is_real_word(w):
    if not _HAS_WORDFREQ:
        return True
    return zipf_frequency(w, 'en') >= _MIN_ZIPF

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Base function words ─────────────────────────────────────────────────────────
_BASE_STOP = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with',
    'is','are','was','were','be','been','being','have','has','had','do','does',
    'did','will','would','could','should','may','might','shall','can','need',
    'i','you','he','she','it','we','they','me','him','her','us','them',
    'my','your','his','its','our','their','this','that','these','those',
    'what','which','who','how','when','where','why','not','no','so','if',
    'as','by','from','up','about','than','then','just','more','very','too',
    'app','use','using','used','also','get','got','one','like','would','really',
    'much','even','still','im',
    'ai','know','make','way','time','every','thing','things','well','back',
    'see','want','now','new','out','all','some','after','into','over',
    'only','other','such','because','while','however','although','many','most',
    'there','please','give','always','something','anything','nothing',
    'everything','think','people','same','before',
}

# Generic sentiment words — true everywhere, so they carry no differentiating signal.
_EMOTION_STOP = {
    'love','best','nice','amazing','awesome','excellent','super','perfect',
    'helpful','useful','wonderful','fantastic','terrible','worst','useless',
    'horrible','worse','better','bad','good','great','cool','okay','fine',
}

# Apostrophe-clipped fragments left over from contractions (doesn't -> doesn).
# Mostly neutralised by the tokenizer below, but kept as a safety net.
_FRAGMENT_STOP = {
    'doesn','cant','dont','ive','wont','didnt','isnt','wasnt','aren','don',
    'didn','wasn','isn','couldn','wouldn','shouldn','won','hasn','haven',
}

# Product / brand names — each product's own name dominates its reviews and is noise.
_PRODUCT_STOP = {
    'chatgpt','claude','gemini','copilot','perplexity','google','microsoft',
    'openai','anthropic','chat','gpt',
}

# Polite / filler words: legitimate English, survive every other filter, but
# carry no signal about a product's strengths or weaknesses (just gratitude/etc).
# NOTE: deliberately does NOT include fast/slow/loading/button/screen/voice/etc.,
# which look generic but actually point to performance/UI/feature areas.
_POLITE_STOP = {
    'thanks','thank','welcome','please','sorry','hello','okay',
    'guys','dear','greetings',
}

STOPWORDS = _BASE_STOP | _EMOTION_STOP | _FRAGMENT_STOP | _PRODUCT_STOP | _POLITE_STOP

def _tokenize(text):
    """Lowercase, collapse contractions (doesn't->doesnt) so apostrophes don't
    create fragments, then keep alpha tokens >3 chars that aren't stopwords."""
    if not isinstance(text, str):
        return []
    text = re.sub(r"([a-z])'([a-z])", r"\1\2", text.lower())
    return [w for w in re.findall(r'[a-z]+', text)
            if w not in STOPWORDS and len(w) > 3 and _is_real_word(w)]

def _count_tokens(texts):
    c = Counter()
    for t in texts:
        c.update(_tokenize(t))
    return c

def get_top_words(target_counts, rest_counts, n=30, alpha=0.01, min_freq=5):
    """Weighted log-odds-ratio with an informative Dirichlet prior
    (Monroe, Colaresi & Quinn 2008). Surfaces words that are *distinctive*
    to this product vs the rest of the corpus, instead of raw frequency.

    Returns {word: rounded z-score} for the top-n distinctive words.
    Pass pre-counted Counters so the corpus is tokenized only once.
    """
    vocab = set(target_counts) | set(rest_counts)
    n_t = sum(target_counts.values())
    n_r = sum(rest_counts.values())
    a0 = alpha * len(vocab)
    scores = {}
    for w in vocab:
        y_t = target_counts.get(w, 0)
        y_r = rest_counts.get(w, 0)
        if y_t + y_r < min_freq:          # skip very-low-frequency noise
            continue
        log_t = np.log((y_t + alpha) / (n_t + a0 - y_t - alpha))
        log_r = np.log((y_r + alpha) / (n_r + a0 - y_r - alpha))
        delta = log_t - log_r
        var = 1.0 / (y_t + alpha) + 1.0 / (y_r + alpha)
        z = delta / np.sqrt(var)
        if z > 0:                          # only words *over*-represented here
            scores[w] = round(float(z), 3)
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:n]
    return {w: s for w, s in top}

def build_data():
    print("Loading CSV data...")
    df = pd.read_csv(
        os.path.join(BASE_DIR, '..', 'data', 'reviews_live.csv'),
        low_memory=False
    )

    df['Review_Date'] = pd.to_datetime(df['Review_Date'])
    df['Date_Only']   = df['Review_Date'].dt.strftime('%Y-%m-%d')
    df['Month_Year']  = df['Review_Date'].dt.strftime('%Y-%m')

    apps = df['App'].unique().tolist()

    # Pre-tokenize positive (>=4*) and negative (<=2*) review text per app ONCE,
    # so the log-odds comparison (this app vs all others) is cheap.
    pos_counts_by_app, neg_counts_by_app = {}, {}
    for app in apps:
        app_df = df[df['App'] == app]
        pos_counts_by_app[app] = _count_tokens(app_df[app_df['Star_Rating'] >= 4]['Review_Text'])
        neg_counts_by_app[app] = _count_tokens(app_df[app_df['Star_Rating'] <= 2]['Review_Text'])
    pos_total = Counter()
    neg_total = Counter()
    for c in pos_counts_by_app.values():
        pos_total.update(c)
    for c in neg_counts_by_app.values():
        neg_total.update(c)

    # 1. Overview
    overview = []
    for app in apps:
        app_df = df[df['App'] == app]

        rating_dist = app_df['Star_Rating'].value_counts().sort_index()
        rating_distribution = {int(k): int(v) for k, v in rating_dist.items()}
        for star in [1, 2, 3, 4, 5]:
            if star not in rating_distribution:
                rating_distribution[star] = 0

        # log-odds: this app's words vs the rest of the corpus
        pos_rest = pos_total.copy()
        for w, c in pos_counts_by_app[app].items():
            pos_rest[w] -= c
        neg_rest = neg_total.copy()
        for w, c in neg_counts_by_app[app].items():
            neg_rest[w] -= c

        neg_samples = (
            app_df[app_df['Star_Rating'] == 1]
            .nsmallest(5, 'Sentiment_Polarity')[['Star_Rating', 'Review_Text']]
            .apply(lambda r: {'star': int(r['Star_Rating']), 'text': str(r['Review_Text'])[:200]}, axis=1)
            .tolist()
        )
        pos_samples = (
            app_df[app_df['Star_Rating'] == 5]
            .nlargest(5, 'Sentiment_Polarity')[['Star_Rating', 'Review_Text']]
            .apply(lambda r: {'star': int(r['Star_Rating']), 'text': str(r['Review_Text'])[:200]}, axis=1)
            .tolist()
        )

        overview.append({
            'App':                 app,
            'Avg_Star':            round(float(app_df['Star_Rating'].mean()), 4),
            'Avg_Sentiment':       round(float(app_df['Sentiment_Polarity'].mean()), 4),
            'Std_Dev':             round(float(app_df['Star_Rating'].std()), 4),
            'Theme_Counts':        app_df['Review_Theme'].value_counts().to_dict(),
            # Themes from low-star (<=2) reviews only. The full Theme_Counts is
            # dominated by 'General' because most reviews match no theme keyword;
            # restricting to complaints surfaces real pain points and shrinks General.
            'Theme_Counts_Neg':    app_df[app_df['Star_Rating'] <= 2]['Review_Theme'].value_counts().to_dict(),
            'Rating_Distribution': rating_distribution,
            'Total_Reviews':       int(len(app_df)),
            'Keywords_Positive':   get_top_words(pos_counts_by_app[app], pos_rest, 30),
            'Keywords_Negative':   get_top_words(neg_counts_by_app[app], neg_rest, 30),
            'Sample_Reviews_Neg':  neg_samples,
            'Sample_Reviews_Pos':  pos_samples,
        })

    # 2. Daily Time Series
    time_series = {}
    for app in apps:
        app_df = df[df['App'] == app]
        daily = (
            app_df.groupby('Date_Only')
            .agg(Avg_Sentiment=('Sentiment_Polarity','mean'),
                 Avg_Star=('Star_Rating','mean'),
                 Count=('Star_Rating','count'))
            .reset_index()
            .sort_values('Date_Only')
        )
        time_series[app] = {
            'dates':         daily['Date_Only'].tolist(),
            'avg_sentiment': [round(v, 4) for v in daily['Avg_Sentiment'].tolist()],
            'avg_star':      [round(v, 4) for v in daily['Avg_Star'].tolist()],
            'count':         daily['Count'].tolist()
        }

    # 3. Monthly Time Series
    monthly_series = {}
    for app in apps:
        app_df = df[df['App'] == app]
        monthly = (
            app_df.groupby('Month_Year')
            .agg(Avg_Sentiment=('Sentiment_Polarity','mean'),
                 Avg_Star=('Star_Rating','mean'),
                 Count=('Star_Rating','count'))
            .reset_index()
            .sort_values('Month_Year')
        )
        monthly_series[app] = {
            'months':        monthly['Month_Year'].tolist(),
            'avg_sentiment': [round(v, 4) for v in monthly['Avg_Sentiment'].tolist()],
            'avg_star':      [round(v, 4) for v in monthly['Avg_Star'].tolist()],
            'count':         monthly['Count'].tolist()
        }

    output_data = {
        'apps':                apps,
        'overview':            overview,
        'time_series_daily':   time_series,
        'time_series_monthly': monthly_series,
    }

    with open(os.path.join(BASE_DIR, 'insights_data.json'), "w") as f:
        json.dump(output_data, f)

    print("insights_data.json updated successfully!")
    print(f"  New fields: Rating_Distribution, Std_Dev, Keywords_Positive, Keywords_Negative, Sample_Reviews")

if __name__ == "__main__":
    build_data()
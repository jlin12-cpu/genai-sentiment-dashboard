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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STOPWORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with',
    'is','are','was','were','be','been','being','have','has','had','do','does',
    'did','will','would','could','should','may','might','shall','can','need',
    'i','you','he','she','it','we','they','me','him','her','us','them',
    'my','your','his','its','our','their','this','that','these','those',
    'what','which','who','how','when','where','why','not','no','so','if',
    'as','by','from','up','about','than','then','just','more','very','too',
    'app','use','using','used','also','get','got','one','like','would','really',
    'much','even','still','good','great','bad','cant','dont','ive','its','im',
    'ai','know','make','way','time','every','thing','things','well','back',
    'see','want','now','new','out','all','some','been','after','into','over',
    'only','other','such','because','while','however','although','many','most'
}

def get_top_words(texts, n=30):
    words = []
    for text in texts:
        if not isinstance(text, str):
            continue
        tokens = re.findall(r'[a-z]+', text.lower())
        words.extend([w for w in tokens if w not in STOPWORDS and len(w) > 3])
    freq = Counter(words).most_common(n)
    return {w: c for w, c in freq}

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

    # 1. Overview
    overview = []
    for app in apps:
        app_df = df[df['App'] == app]

        rating_dist = app_df['Star_Rating'].value_counts().sort_index()
        rating_distribution = {int(k): int(v) for k, v in rating_dist.items()}
        for star in [1, 2, 3, 4, 5]:
            if star not in rating_distribution:
                rating_distribution[star] = 0

        pos_texts = app_df[app_df['Star_Rating'] >= 4]['Review_Text']
        neg_texts = app_df[app_df['Star_Rating'] <= 2]['Review_Text']

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
            'Rating_Distribution': rating_distribution,
            'Total_Reviews':       int(len(app_df)),
            'Keywords_Positive':   get_top_words(pos_texts, 30),
            'Keywords_Negative':   get_top_words(neg_texts, 30),
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
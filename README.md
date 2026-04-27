# Generative AI Reviews — Sentiment & Insights Dashboard

Aggregated data from roughly 50k user reviews of generative AI apps, shown in a static web page (Chart.js): KPIs, sentiment over time, average star ratings, and topic mix. A Jupyter notebook supports exploratory analysis and sentiment experiments; a Python script turns the raw CSV into JSON for the dashboard.

## Features

- Filter by product (all / single app): ChatGPT, Microsoft Copilot, Google Gemini, Perplexity, Claude  
- KPIs: total reviews, average star rating, average sentiment polarity  
- Line chart: daily average sentiment (when “All” is selected, multiple product lines)  
- Bar chart: average star rating  
- Doughnut chart: share of review themes (e.g. pricing, bugs, accuracy)  

## Repository layout

| File | Description |
|------|-------------|
| `The_ Generative_AI_Ecosystem_50k_User_Reviews_2026.csv` | Raw review dataset |
| `build_dashboard_data.py` | Aggregates the CSV into `insights_data.json` |
| `insights_data.json` | Summary data consumed by the dashboard (created/updated by the script) |
| `index.html` / `styles.css` / `app.js` | Static dashboard page and logic |
| `app-reviews-eda-sentiment-analysis.ipynb` | EDA and sentiment analysis notebook |
| `analysis_results.md` | Written analysis and interpretation |

## Requirements

- **Dashboard**: a modern browser; open the page via a **local HTTP server** (see below), otherwise the browser may block `fetch` to `insights_data.json` for security reasons.  
- **Data build**: Python 3.9+ (recommended) with `pandas` installed (the script imports `numpy`, but the current aggregation does not use it—you can run with `pandas` only).

```bash
pip install pandas
```

To reproduce the full notebook workflow, also install whatever it imports, e.g. `numpy`, `matplotlib`, `seaborn`, `nltk`, `textblob`, etc.

## Quick start

### 1. Build dashboard data

From the project root:

```bash
python build_dashboard_data.py
```

On success, `insights_data.json` is written or overwritten in the current directory.

### 2. Start a local static server

Still from the project root:

```bash
python -m http.server 8080
```

Use any free port you prefer.

### 3. Open the dashboard

In your browser:

```text
http://localhost:8080/index.html
```

If you use another port, replace `8080` accordingly.

## Data note

The dataset is meant to compare several LLM-related apps on stars, text sentiment, and themes. If the data is for a course, competition, or synthetic, label the source clearly in public demos so it is not mistaken for unauthorized real user data.

## Stack

- Front end: plain HTML / CSS / JavaScript, [Chart.js](https://www.chartjs.org/) (CDN)  
- Data: `pandas` aggregation → JSON  
- Analysis: `app-reviews-eda-sentiment-analysis.ipynb` (pandas, plotting, TextBlob, etc.)  

## License

Redistribution and commercial use depend on the assets you actually hold or generated; if nothing is stated otherwise, treat this as personal learning and portfolio use only.

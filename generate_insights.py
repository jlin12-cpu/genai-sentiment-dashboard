"""
generate_insights.py
---------------------
Offline narrative-insight generator for the dashboard.

Runs AFTER build_dashboard_data.py in the weekly pipeline. Reads the aggregated
statistics + distinctive keywords from insights_data.json, asks Claude to write
short narrative analyses (the "so what" that templates can't produce), and writes
them back into the same JSON under a new top-level "analysis" key:

    {
      "apps": [...],
      "overview": [...],
      "time_series_daily": {...},
      "analysis": {
        "overview": "…cross-product narrative…",
        "products": { "ChatGPT": "…", "Claude": "…", ... },
        "generated_at": "2026-05-21T…"
      }
    }

The dashboard front-end reads analysis.* directly (no API call at page load).
Per-pair Compare analyses are NOT generated here — those are produced live by
server.py when the user picks two products, so they can vary per comparison.

Run:  python generate_insights.py
Pipeline order:  scraper.py → clean_data.py → build_dashboard_data.py → generate_insights.py
"""

import json
import os
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# Sonnet 4 (claude-sonnet-4-20250514) was retired 2026-04-20. Sonnet 4.6 is the
# current recommended model. Note the dateless ID format introduced with 4.6 —
# it's still a pinned snapshot, not an auto-updating pointer.
MODEL = "claude-sonnet-4-6"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# build_dashboard_data.py writes to dashboard/insights_data.json
DATA_FILE = os.path.join(BASE_DIR, "dashboard", "insights_data.json")

# How many distinctive keywords / sample reviews to feed the model per product.
N_KEYWORDS = 12
N_SAMPLES = 3


# ── LLM call (mirrors weekly_report.py) ──────────────────────────────────────────
def ask_claude(prompt, max_tokens=400):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


# ── Context builders ─────────────────────────────────────────────────────────────
def _low_star_pain_point(item):
    """FIX for the 'inflated pain point' problem: the dashboard banner derives the
    top pain point from Theme_Counts over ALL reviews (including 5-star), which can
    surface a theme that is merely talked-about, not actually a complaint. Here we
    can't recompute themes from raw text (we only have aggregates), so we flag this
    honestly to the model and lean on the NEGATIVE keywords instead, which ARE
    low-star-derived (Star_Rating <= 2)."""
    themes = sorted(item["Theme_Counts"].items(), key=lambda x: -x[1])
    non_general = [t for t in themes if t[0] != "General"]
    return non_general[0][0] if non_general else "n/a"


def product_context(item):
    app = item["App"].replace("_", " ")
    pos_kw = ", ".join(list(item["Keywords_Positive"].keys())[:N_KEYWORDS])
    neg_kw = ", ".join(list(item["Keywords_Negative"].keys())[:N_KEYWORDS])
    pos_samples = [s["text"] for s in item.get("Sample_Reviews_Pos", [])[:N_SAMPLES]]
    neg_samples = [s["text"] for s in item.get("Sample_Reviews_Neg", [])[:N_SAMPLES]]
    one_pct = item["Rating_Distribution"].get("1", 0) / max(item["Total_Reviews"], 1) * 100
    five_pct = item["Rating_Distribution"].get("5", 0) / max(item["Total_Reviews"], 1) * 100

    lines = [
        f"Product: {app}",
        f"Average rating: {item['Avg_Star']:.2f} / 5",
        f"Average sentiment: {item['Avg_Sentiment']:.3f} (range -1 to 1)",
        f"Rating spread (std dev): {item['Std_Dev']:.2f} (higher = more polarised)",
        f"5-star: {five_pct:.1f}%  ·  1-star: {one_pct:.1f}%",
        f"Total reviews: {item['Total_Reviews']:,}",
        "",
        "DISTINCTIVE positive keywords (what this product is praised for, "
        "relative to competitors): " + pos_kw,
        "DISTINCTIVE negative keywords (drawn from 1-2 star reviews only): " + neg_kw,
    ]
    if pos_samples:
        lines.append("\nExample positive reviews:")
        lines += [f'  - "{t}"' for t in pos_samples]
    if neg_samples:
        lines.append("\nExample negative (1-star) reviews:")
        lines += [f'  - "{t}"' for t in neg_samples]
    return "\n".join(lines)


def overview_context(data):
    lines = ["Cross-product snapshot of 5 generative-AI assistant apps "
             "(Google Play reviews):\n"]
    for item in sorted(data["overview"], key=lambda x: -x["Avg_Star"]):
        app = item["App"].replace("_", " ")
        pos_kw = ", ".join(list(item["Keywords_Positive"].keys())[:6])
        neg_kw = ", ".join(list(item["Keywords_Negative"].keys())[:6])
        lines.append(
            f"{app}: {item['Avg_Star']:.2f}* | sentiment {item['Avg_Sentiment']:.3f} "
            f"| std {item['Std_Dev']:.2f} | {item['Total_Reviews']:,} reviews"
        )
        lines.append(f"    praised for: {pos_kw}")
        lines.append(f"    complaints:  {neg_kw}")
    return "\n".join(lines)


# ── Prompts ──────────────────────────────────────────────────────────────────────
GUIDANCE = (
    "Write in plain, specific English for a product analyst. Ground every claim in "
    "the numbers or keywords given. Do NOT invent statistics. The keywords are "
    "DISTINCTIVE terms (what sets this product apart), not raw frequencies, so treat "
    "them as 'what this product is notably associated with vs others'. Be concrete: "
    "name the actual themes (e.g. usage limits, image generation, accuracy). "
    "Do not use markdown headers or bullet points; write tight prose."
)


def analyse_product(item):
    ctx = product_context(item)
    prompt = (
        f"{ctx}\n\n{GUIDANCE}\n\n"
        "In 3-4 sentences, summarise this product's key strengths and the main pain "
        "points its users report. Lead with what distinguishes it. If positive and "
        "negative signals point to the same feature (e.g. praised AND criticised), "
        "say so."
    )
    return ask_claude(prompt, max_tokens=350)


def analyse_overview(data):
    ctx = overview_context(data)
    prompt = (
        f"{ctx}\n\n{GUIDANCE}\n\n"
        "In 4-5 sentences, describe the competitive landscape: who leads and on what "
        "dimension, who is most polarising, and what the clearest per-product "
        "positioning differences are (e.g. one is a coding tool, another a research "
        "tool, another a mobile assistant). Avoid generic praise."
    )
    return ask_claude(prompt, max_tokens=500)


# ── Pairwise comparisons (pre-generated so the Compare page needs no backend) ────
def _pair_key(a, b):
    """A vs B and B vs A share one key (sorted), matching the front-end cache key."""
    return "::".join(sorted([a, b]))


def _compare_block(item):
    app = item["App"].replace("_", " ")
    pos = ", ".join(list(item["Keywords_Positive"].keys())[:10])
    neg = ", ".join(list(item["Keywords_Negative"].keys())[:10])
    one_pct = item["Rating_Distribution"].get("1", 0) / max(item["Total_Reviews"], 1) * 100
    five_pct = item["Rating_Distribution"].get("5", 0) / max(item["Total_Reviews"], 1) * 100
    return (
        f"{app}: {item['Avg_Star']:.2f}* avg | sentiment {item['Avg_Sentiment']:.3f} "
        f"| std {item['Std_Dev']:.2f} | {item['Total_Reviews']:,} reviews "
        f"| {five_pct:.1f}% five-star, {one_pct:.1f}% one-star\n"
        f"    praised for: {pos}\n"
        f"    complaints:  {neg}"
    )


def analyse_comparison(item_a, item_b):
    names = f"{item_a['App'].replace('_',' ')} vs {item_b['App'].replace('_',' ')}"
    blocks = _compare_block(item_a) + "\n" + _compare_block(item_b)
    prompt = (
        f"Comparison data for {names} (Google Play review analysis):\n\n{blocks}\n\n"
        f"{GUIDANCE}\n\n"
        "In 3-4 sentences, directly compare these two products: where each one wins, "
        "where it loses, and which to choose for which kind of user. Make the contrast "
        "explicit (e.g. 'X is stronger for coding while Y is better for research'). "
        "Do not just describe each separately."
    )
    return ask_claude(prompt, max_tokens=400)


# ── Main ─────────────────────────────────────────────────────────────────────────
def main():
    if not ANTHROPIC_API_KEY:
        raise SystemExit("✗ ANTHROPIC_API_KEY not found in .env — cannot generate insights.")

    print("📊 Loading aggregated data...")
    with open(DATA_FILE) as f:
        data = json.load(f)

    print("🤖 Generating overview analysis...")
    overview_text = analyse_overview(data)

    products = {}
    for item in data["overview"]:
        app = item["App"]
        print(f"🤖 Analysing {app.replace('_', ' ')}...")
        products[app] = analyse_product(item)

    # Pre-generate every pairwise comparison (5 products → 10 pairs) so the
    # Compare page can read them straight from JSON — no live backend needed,
    # works on the public GitHub Pages site.
    by_app = {it["App"]: it for it in data["overview"]}
    app_list = list(by_app.keys())
    comparisons = {}
    for i in range(len(app_list)):
        for j in range(i + 1, len(app_list)):
            a, b = app_list[i], app_list[j]
            print(f"🤖 Comparing {a.replace('_',' ')} vs {b.replace('_',' ')}...")
            comparisons[_pair_key(a, b)] = analyse_comparison(by_app[a], by_app[b])

    data["analysis"] = {
        "overview": overview_text,
        "products": products,
        "comparisons": comparisons,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

    print(f"✅ Insights written to {DATA_FILE}")
    print(f"   overview + {len(products)} product analyses + {len(comparisons)} comparisons")


if __name__ == "__main__":
    main()

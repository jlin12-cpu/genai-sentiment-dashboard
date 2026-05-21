"""
server.py
---------
Minimal Flask backend proxy for the dashboard's Compare page.

WHY THIS EXISTS: the Compare page generates a fresh analysis every time the user
picks a different pair of products, so it can't be pre-generated offline. That
means a live LLM call — but the API key must NEVER be sent to the browser. This
server keeps the key server-side: the front-end calls THIS server, and THIS
server calls Claude.

Endpoints:
  GET  /api/health           -> {"ok": true}
  POST /api/compare          -> body: {"apps": ["ChatGPT", "Claude"]}
                                returns: {"analysis": "..."}

Run:
  cd <project root>
  source venv/bin/activate
  python server.py
  # serves on http://localhost:5001

The dashboard front-end (served separately on :8000) calls http://localhost:5001.
Because they're different origins, CORS is enabled for local development.
"""

import json
import os
import re

from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv

# Reuse the existing Google-Sheets-backed subscriber functions so the website
# signup writes to the SAME list the weekly mailer reads (closing the loop that
# was previously broken: front-end wrote to Formspree, mailer read Sheets).
from subscriber_mailer import add_subscriber, get_subscribers

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"   # current model; Sonnet 4 was retired 2026-04-20

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dashboard", "insights_data.json")

# Number of keywords fed into the comparison prompt per product.
N_KEYWORDS = 10

app = Flask(__name__)
# Local dev: allow the static dashboard (any localhost port) to call this server.
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:8000",
                                              "http://127.0.0.1:8000"]}})

# ── Analysis guidance (kept consistent with generate_insights.py) ────────────────
GUIDANCE = (
    "Write in plain, specific English for a product analyst. Ground every claim in "
    "the numbers or keywords given. Do NOT invent statistics. Keywords are DISTINCTIVE "
    "terms (what sets each product apart), not raw counts. Be concrete and name actual "
    "themes. No markdown headers or bullet points; write tight prose."
)


def _load_overview():
    with open(DATA_FILE) as f:
        return {item["App"]: item for item in json.load(f)["overview"]}


def _product_block(item):
    app_name = item["App"].replace("_", " ")
    pos = ", ".join(list(item["Keywords_Positive"].keys())[:N_KEYWORDS])
    neg = ", ".join(list(item["Keywords_Negative"].keys())[:N_KEYWORDS])
    one_pct = item["Rating_Distribution"].get("1", 0) / max(item["Total_Reviews"], 1) * 100
    five_pct = item["Rating_Distribution"].get("5", 0) / max(item["Total_Reviews"], 1) * 100
    return (
        f"{app_name}: {item['Avg_Star']:.2f}* avg | sentiment {item['Avg_Sentiment']:.3f} "
        f"| std {item['Std_Dev']:.2f} | {item['Total_Reviews']:,} reviews "
        f"| {five_pct:.1f}% five-star, {one_pct:.1f}% one-star\n"
        f"    praised for: {pos}\n"
        f"    complaints:  {neg}"
    )


def build_compare_prompt(items):
    blocks = "\n".join(_product_block(it) for it in items)
    names = " vs ".join(it["App"].replace("_", " ") for it in items)
    return (
        f"Comparison data for {names} (Google Play review analysis):\n\n{blocks}\n\n"
        f"{GUIDANCE}\n\n"
        "In 3-4 sentences, directly compare these products: where each one wins, where "
        "it loses, and which to choose for which kind of user. Make the contrast explicit "
        "(e.g. 'X is stronger for coding while Y is better for research'). Do not just "
        "describe each separately."
    )


def ask_claude(prompt, max_tokens=400):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "key_loaded": bool(ANTHROPIC_API_KEY)})


@app.route("/api/compare", methods=["POST"])
def compare():
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "Server is missing ANTHROPIC_API_KEY."}), 500

    body = request.get_json(silent=True) or {}
    apps = body.get("apps", [])
    if not isinstance(apps, list) or len(apps) < 2:
        return jsonify({"error": "Provide at least two app names in 'apps'."}), 400

    overview = _load_overview()
    items, unknown = [], []
    for a in apps:
        if a in overview:
            items.append(overview[a])
        else:
            unknown.append(a)
    if unknown:
        return jsonify({"error": f"Unknown app(s): {', '.join(unknown)}"}), 400

    try:
        analysis = ask_claude(build_compare_prompt(items))
    except Exception as e:
        # Don't leak internals to the browser; log server-side, return a clean message.
        print(f"[error] Claude call failed: {e}")
        return jsonify({"error": "Failed to generate analysis. Check server logs."}), 502

    return jsonify({"analysis": analysis})


# Basic email shape check (not exhaustive — just guards obvious junk).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()

    if not _EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    try:
        existing = [e.strip().lower() for e in get_subscribers()]
        if email in existing:
            # Idempotent: treat re-subscribe as success, don't add a duplicate row.
            return jsonify({"ok": True, "message": "You're already subscribed."})
        add_subscriber(email)
    except Exception as e:
        print(f"[error] subscribe failed: {e}")
        return jsonify({"error": "Could not save subscription. Check server logs."}), 502

    return jsonify({"ok": True, "message": "Subscribed! You'll receive weekly reports."})


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("⚠️  ANTHROPIC_API_KEY not found in .env — /api/compare will return 500.")
    print("🚀 Backend on http://localhost:5001  (Compare + Subscribe · Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5001, debug=False)

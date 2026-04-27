"""
weekly_report.py — reads secrets from .env
"""
import json, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import anthropic
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS     = os.getenv('GMAIL_ADDRESS')
GMAIL_APP_PW      = os.getenv('GMAIL_APP_PW')
SEND_TO           = os.getenv('GMAIL_ADDRESS')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dashboard", "insights_data.json")

def load_data():
    with open(DATA_FILE) as f: return json.load(f)

def build_context(data):
    lines = ["GenAI App Sentiment Data:\n"]
    for item in data["overview"]:
        app = item["App"].replace("_", " ")
        lines.append(f"{app}: {item['Avg_Star']:.2f}★ | sentiment {item['Avg_Sentiment']:.3f} | {item['Total_Reviews']:,} reviews")
        top_pain = sorted(item["Theme_Counts"].items(), key=lambda x: x[1], reverse=True)
        lines.append(f"  Top theme: {top_pain[0][0]} ({top_pain[0][1]:,} reviews)")
        lines.append(f"  Top positive keywords: {', '.join(list(item['Keywords_Positive'].keys())[:5])}")
        lines.append(f"  Top negative keywords: {', '.join(list(item['Keywords_Negative'].keys())[:5])}")
    return "\n".join(lines)

def ask_claude(prompt):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=800,
        messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text

def generate_report(data):
    ctx = build_context(data)
    summary  = ask_claude(f"{ctx}\n\nWrite a 3-sentence executive summary of the GenAI app sentiment landscape this week.")
    winner   = ask_claude(f"{ctx}\n\nIn 2 sentences, explain why {max(data['overview'], key=lambda x: x['Avg_Star'])['App'].replace('_',' ')} leads in ratings.")
    concerns = ask_claude(f"{ctx}\n\nIn 2-3 sentences, what are the most common user complaints across all GenAI apps?")
    return summary, winner, concerns

def build_html(data, summary, winner, concerns):
    date_str = datetime.now().strftime("%B %d, %Y")
    best_app = max(data["overview"], key=lambda x: x["Avg_Star"])
    colors = {"ChatGPT":"#10a37f","Claude":"#d97757","Google_Gemini":"#4285f4","Microsoft_Copilot":"#0078d4","Perplexity":"#22d3ee"}
    rows = ""
    for item in sorted(data["overview"], key=lambda x: x["Avg_Star"], reverse=True):
        color = colors.get(item["App"], "#666")
        rows += f"""<tr>
            <td style="padding:10px;border-bottom:1px solid #f0f0f0">
                <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:8px"></span>
                <strong>{item["App"].replace("_"," ")}</strong></td>
            <td style="padding:10px;border-bottom:1px solid #f0f0f0;text-align:center">{"★"*round(item["Avg_Star"])}{"☆"*(5-round(item["Avg_Star"]))} {item["Avg_Star"]:.2f}</td>
            <td style="padding:10px;border-bottom:1px solid #f0f0f0;text-align:center;color:{"#16a34a" if item["Avg_Sentiment"]>0.4 else "#dc2626"}">{item["Avg_Sentiment"]:.3f}</td>
            <td style="padding:10px;border-bottom:1px solid #f0f0f0;text-align:center;color:#666">{item["Total_Reviews"]:,}</td></tr>"""
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:'Helvetica Neue',Arial,sans-serif">
<div style="max-width:600px;margin:32px auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
  <div style="background:#2563eb;padding:32px;text-align:center">
    <div style="font-size:28px;font-weight:700;color:white">GenAI Sentiment</div>
    <div style="font-size:14px;color:rgba(255,255,255,0.8)">Weekly Report · {date_str}</div></div>
  <div style="padding:28px 32px;border-bottom:1px solid #f0f0f0">
    <div style="font-size:11px;font-weight:600;text-transform:uppercase;color:#2563eb;margin-bottom:10px">Executive Summary</div>
    <p style="font-size:15px;color:#374151;line-height:1.7;margin:0">{summary}</p></div>
  <div style="padding:28px 32px;border-bottom:1px solid #f0f0f0">
    <div style="font-size:11px;font-weight:600;text-transform:uppercase;color:#2563eb;margin-bottom:16px">Product Rankings</div>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="background:#f8fafc">
        <th style="padding:10px;text-align:left;color:#6b7280;font-weight:500">Product</th>
        <th style="padding:10px;text-align:center;color:#6b7280;font-weight:500">Rating</th>
        <th style="padding:10px;text-align:center;color:#6b7280;font-weight:500">Sentiment</th>
        <th style="padding:10px;text-align:center;color:#6b7280;font-weight:500">Reviews</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
  <div style="padding:28px 32px;border-bottom:1px solid #f0f0f0;background:#f0fdf4">
    <div style="font-size:11px;font-weight:600;text-transform:uppercase;color:#15803d;margin-bottom:10px">🏆 This Week's Leader</div>
    <div style="font-size:16px;font-weight:600;color:#111;margin-bottom:8px">{best_app["App"].replace("_"," ")} — {best_app["Avg_Star"]:.2f}★</div>
    <p style="font-size:14px;color:#374151;line-height:1.7;margin:0">{winner}</p></div>
  <div style="padding:28px 32px;border-bottom:1px solid #f0f0f0;background:#fff7ed">
    <div style="font-size:11px;font-weight:600;text-transform:uppercase;color:#c2410c;margin-bottom:10px">⚠️ Common User Concerns</div>
    <p style="font-size:14px;color:#374151;line-height:1.7;margin:0">{concerns}</p></div>
  <div style="padding:20px 32px;text-align:center;background:#f8fafc">
    <p style="font-size:12px;color:#9ca3af;margin:0">GenAI Sentiment Dashboard · Auto-generated weekly report<br>Data source: Google Play Store reviews</p></div>
</div></body></html>"""

def send_email(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 GenAI Weekly Sentiment Report — {datetime.now().strftime('%b %d, %Y')}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"]   = SEND_TO
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
        server.sendmail(GMAIL_ADDRESS, SEND_TO, msg.as_string())

def main():
    print("📊 Loading data...")
    data = load_data()
    print("🤖 Generating AI insights...")
    summary, winner, concerns = generate_report(data)
    print("✉️  Building email...")
    html = build_html(data, summary, winner, concerns)
    print("📬 Sending email...")
    send_email(html)
    print(f"✅ Report sent to {SEND_TO}!")

if __name__ == "__main__":
    main()

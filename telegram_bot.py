"""
telegram_bot.py
---------------
Telegram bot that answers questions about GenAI sentiment data
using Claude API + insights_data.json
"""

import json
import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dashboard", "insights_data.json")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def build_context(data):
    lines = ["Here is the latest GenAI app sentiment data from Google Play:\n"]
    for item in data["overview"]:
        app = item["App"].replace("_", " ")
        lines.append(f"## {app}")
        lines.append(f"- Average Star Rating: {item['Avg_Star']:.2f} / 5")
        lines.append(f"- Average Sentiment Polarity: {item['Avg_Sentiment']:.3f}")
        lines.append(f"- Rating Std Dev: {item['Std_Dev']:.2f}")
        lines.append(f"- Total Reviews: {item['Total_Reviews']:,}")
        themes = ", ".join([f"{k}: {v}" for k, v in item["Theme_Counts"].items()])
        lines.append(f"- Review Themes: {themes}")
        pos_kw = ", ".join(list(item["Keywords_Positive"].keys())[:6])
        neg_kw = ", ".join(list(item["Keywords_Negative"].keys())[:6])
        lines.append(f"- Top Positive Keywords: {pos_kw}")
        lines.append(f"- Top Negative Keywords: {neg_kw}")
        lines.append("")
    return "\n".join(lines)

def ask_claude(question, data_context):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": f"{data_context}\n\nBased on the data above, please answer this question concisely (2-4 sentences):\n{question}"}]
    )
    return message.content[0].text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your GenAI Sentiment Dashboard bot.\n\n"
        "Ask me anything about ChatGPT, Claude, Gemini, Copilot, or Perplexity user reviews!\n\n"
        "Commands:\n/summary — Overall market summary\n/top — Top rated product"
    )

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Generating summary...")
    try:
        data = load_data()
        ctx = build_context(data)
        answer = ask_claude("Give a brief 3-4 sentence summary of the overall GenAI app sentiment landscape.", ctx)
        await update.message.reply_text(f"📊 *Market Summary*\n\n{answer}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Sorry, something went wrong: {e}")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = load_data()
        best = max(data["overview"], key=lambda x: x["Avg_Star"])
        await update.message.reply_text(
            f"🏆 *Top Rated App*\n\n*{best['App'].replace('_',' ')}* leads with *{best['Avg_Star']:.2f}★* and sentiment *{best['Avg_Sentiment']:.3f}*.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"Sorry, something went wrong: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    await update.message.reply_text("🤔 Thinking...")
    try:
        data   = load_data()
        ctx    = build_context(data)
        answer = ask_claude(question, ctx)
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text(f"Sorry, something went wrong: {e}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("top",     top))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()

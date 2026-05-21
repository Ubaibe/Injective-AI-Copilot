import os
import requests
import logging
import asyncio
from portfolio_db import PortfolioDB
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory

from langchain_core.prompts import PromptTemplate

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= CONFIG =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("Please set TELEGRAM_TOKEN in .env file")

# LLM Setup
llm = ChatOpenAI(
    model="openrouter/free",
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
    temperature=0.0,
)


prompt = PromptTemplate.from_template(
    """You are Injective AI Copilot, a helpful and professional personal finance assistant on Injective.

You can:
- Show portfolio / balances
- Analyze risk & P&L
- Suggest yield strategies
- Help with trades (with user confirmation)
- General Injective questions

Current user wallet: {wallet_address}

Conversation history:
{history}

User: {input}
AI:"""
)


chain = prompt | llm
user_wallets = {}
portfolio_db = PortfolioDB()

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["📊 Analyze Portfolio", "📈 Portfolio History"],
        ["🧠 Improve My Score", "🔄 What Changed"],
        ["🔔 Set Alert", "⚖️ Rebalance"],
        ["📄 Strategy Report", "📋 Menu"]
    ],
    resize_keyboard=True
)


# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome to **Injective AI Copilot**!\n\n"
        "Send your Injective wallet address to get started.\n"
        "Example: `inj1abc...xyz`"
        "At any time, type /menu to see available actions.",
        reply_markup=MAIN_MENU
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = """
📋 Available Commands

• Send your Injective wallet address
• Analyze my portfolio
• Portfolio history
• How can I improve my score?
• What changed in my portfolio?

Type any of the above to continue.
"""
    await update.message.reply_text(menu_text)

def get_wallet_balances(wallet_address: str):
    try:
        # Public LCD endpoint
        url = f"https://lcd.injective.network/cosmos/bank/v1beta1/balances/{wallet_address}"
        res = requests.get(url, timeout=10)
        data = res.json()

        balances = data.get("balances", [])
        if not balances:
            return "No balances found for this wallet."

        formatted = []
        for coin in balances[:3]:  # show top 5 for now
            denom = coin.get("denom", "")
            amount = coin.get("amount", "0")

            # clean denom names
            if denom == "inj":
                symbol = "INJ"
            elif "usdt" in denom.lower():
                symbol = "USDT"
            elif "atom" in denom.lower():
                symbol = "ATOM"
            else:
                symbol = denom[:8].upper()

            human_amount = round(float(amount) / 1_000_000, 2)
            formatted.append(f"{symbol}: {human_amount}")
        return "\n".join(formatted)

    except Exception as e:
        return f"Unable to fetch wallet balances: {str(e)}"

def calculate_health_score(wallet_address: str):
    try:

        url = f"https://lcd.injective.network/cosmos/bank/v1beta1/balances/{wallet_address}"
        res = requests.get(url, timeout=10)
        data = res.json()
        print("RAW API RESPONSE:", data)
        balances = data.get("balances", [])

        if not balances:
            return 20, "Low", []

        parsed = []
        total_value = 0.0

        for coin in balances[:10]:
            amount = coin.get("amount", "0")
            denom = coin.get("denom", "")

            try:
                human_amount = float(amount) / 1_000_000
            except:
                human_amount = 0.0

            if human_amount <= 0:
                continue

            # simple symbol cleanup
            if denom == "inj":
                symbol = "INJ"
            elif "usdt" in denom.lower():
                symbol = "USDT"
            elif "atom" in denom.lower():
                symbol = "ATOM"
            else:
                symbol = denom[:8].upper()

            parsed.append({"symbol": symbol, "amount": human_amount})
            total_value += human_amount

        if not parsed:
            return 20, "Low", []

        # diversification score
        asset_count = len(parsed)
        diversification_score = min(asset_count * 15, 45)

        # concentration penalty
        largest = max(parsed, key=lambda x: x["amount"])
        concentration_ratio = largest["amount"] / total_value if total_value else 1

        if concentration_ratio > 0.75:
            concentration_penalty = 25
        elif concentration_ratio > 0.5:
            concentration_penalty = 15
        else:
            concentration_penalty = 5

        score = max(10, min(100, diversification_score + 60 - concentration_penalty))

        if score >= 80:
            risk = "Healthy"
        elif score >= 55:
            risk = "Moderate"
        else:
            risk = "Risky"

        return score, risk, parsed[:3]

    except Exception:
        return 0, "Unavailable", []

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_input = update.message.text.strip()

    # ================= MENU =================
    if user_input.lower() in ["📋 menu", "/menu"]:
        await update.message.reply_text(
            "Choose an action below:",
            reply_markup=MAIN_MENU
        )
        return

    # ================= ALERT HELP =================
    if user_input.lower() == "🤖 ai alerts":
        await update.message.reply_text(
            "Send:\nnotify me if my score drops below 60"
        )
        return

    # ================= SET ALERT =================
    if "notify me if my score drops below" in user_input.lower():
        try:
            threshold = int(user_input.lower().split("below")[-1].strip())
            portfolio_db.save_alert(user_id, threshold)

            await update.message.reply_text(
                f"🔔 Alert enabled.\nI’ll notify you if your portfolio score drops below {threshold}/100."
            )
        except:
            await update.message.reply_text(
                "Please use format:\nnotify me if my score drops below 60"
            )
        return

    # ================= PORTFOLIO HISTORY =================
    if user_input.lower() in ["portfolio history", "📈 portfolio history"]:
        history = portfolio_db.get_history(user_id)

        if not history:
            await update.message.reply_text(
                "No portfolio history yet. Run 'Analyze my portfolio' first."
            )
            return

        lines = []
        for score, risk, assets, ts in history:
            lines.append(f"{ts} → Score: {score}/100 ({risk})")

        message = "📈 Portfolio Performance History\n\n" + "\n".join(lines)
        await update.message.reply_text(message)
        return

    # ================= CONNECT WALLET =================
    if user_input.startswith("inj1") and len(user_input) > 40:
        user_wallets[user_id] = user_input
        await update.message.reply_text(
            f"✅ Wallet connected successfully!\n`{user_input}`\nChoose an action below",
            reply_markup=MAIN_MENU,
            parse_mode='Markdown'
        )
        return

    wallet = user_wallets.get(user_id, "Not connected yet")

    # ================= ANALYZE PORTFOLIO =================
    if user_input.lower() in ["analyze my portfolio", "📊 analyze portfolio"]:
        if wallet == "Not connected yet":
            await update.message.reply_text(
                "Please send your Injective wallet address first."
            )
            return

        score, risk, assets = calculate_health_score(wallet)
        portfolio_db.save_snapshot(user_id, wallet, score, risk, assets)

        # ----- AI Actionable Alert -----
        threshold = portfolio_db.get_alert(user_id)

        if threshold and score < threshold:
            history = portfolio_db.get_history(user_id)

            previous_score = history[1][0] if len(history) > 1 else score
            previous_assets = history[1][2] if len(history) > 1 else []

            current_symbols = {a["symbol"] for a in assets}
            previous_symbols = {a["symbol"] for a in previous_assets}

            added = current_symbols - previous_symbols
            removed = previous_symbols - current_symbols

            alert_prompt = f"""
You are an Injective AI portfolio monitoring assistant.

Current score: {score}/100
Previous score: {previous_score}/100
Risk level: {risk}

Assets added: {', '.join(added) if added else 'None'}
Assets removed: {', '.join(removed) if removed else 'None'}

Respond ONLY in this format:

⚠️ Portfolio Alert

Reason:
1 short sentence explaining why the score dropped.

Suggested Action:
1 practical recommendation for improving portfolio health on Injective.

Keep under 500 characters.
"""

            response = llm.invoke(alert_prompt)
            alert_reply = response.content[:3500]
            await update.message.reply_text(alert_reply)

        if not assets:
            await update.message.reply_text(
                "This wallet appears to have no on-chain balances on Injective yet. "
                "Try connecting a funded wallet to get a real portfolio analysis."
            )
            return

        asset_lines = "\n".join(
            [f"• {a['symbol']}: {a['amount']:.2f}" for a in assets]
        )

        analysis_prompt = f"""
You are an expert crypto portfolio assistant for Injective.

Portfolio Health Score: {score}/100
Risk Level: {risk}

Assets:
{asset_lines}

Respond ONLY in this format:

Portfolio Health Score: [repeat score]/100
Risk Level: [repeat risk]

Portfolio Summary
• token: amount
• token: amount
• token: amount

AI Insight:
2 concise sentences only. Mention diversification and one practical suggestion.
Keep under 700 characters.
"""

        response = llm.invoke(analysis_prompt)
        reply = response.content[:3500]
        await update.message.reply_text(reply)
        return

    # ================= REBALANCE =================
    if user_input.lower() in ["how can i rebalance?", "⚖️ rebalance"]:
        if wallet == "Not connected yet":
            await update.message.reply_text("Please connect your wallet first.")
            return

        score, risk, assets = calculate_health_score(wallet)

        if not assets:
            await update.message.reply_text("No portfolio found.")
            return

        asset_lines = "\n".join(
            [f"{a['symbol']}: {a['amount']:.2f}" for a in assets]
        )

        diversity_bonus = min(len(assets) * 4, 15)
        projected_score = min(score + diversity_bonus, 100)

        rebalance_prompt = f"""
You are an Injective portfolio optimizer.

Current portfolio score: {score}/100
Risk: {risk}

Assets:
{asset_lines}

Projected improved score after rebalancing: {projected_score}/100

Respond ONLY in this format:

Rebalance Plan
• Current score: X/100
• Projected score: X/100

Suggested Changes:
2 bullet points suggesting realistic portfolio shifts.

AI Recommendation:
1 concise sentence.
Keep under 650 characters.
"""

        response = llm.invoke(rebalance_prompt)
        reply = response.content[:3500]
        await update.message.reply_text(reply)
        return

    # ================= STRATEGY REPORT =================
    if user_input.lower() in ["📄 strategy report", "generate strategy report"]:
        if wallet == "Not connected yet":
            await update.message.reply_text("Please connect your wallet first.")
            return

        score, risk, assets = calculate_health_score(wallet)

        if not assets:
            await update.message.reply_text("No portfolio data available.")
            return

        filename = generate_report(user_id, wallet, score, risk, assets)

        with open(filename, "rb") as pdf:
            await update.message.reply_document(
                document=pdf,
                filename="injective_strategy_report.pdf",
                caption="📄 Your AI-generated strategy report"
            )
        return

    # ================= IMPROVE SCORE =================
    if user_input.lower() in ["how can i improve my score?", "🧠 improve my score"]:
        history = portfolio_db.get_history(user_id)

        if not history:
            await update.message.reply_text(
                "No portfolio history yet. Run 'Analyze my portfolio' first."
            )
            return

        latest_score = history[0][0]
        previous_score = history[1][0] if len(history) > 1 else latest_score

        trend = (
            "improved" if latest_score > previous_score
            else "declined" if latest_score < previous_score
            else "stayed the same"
        )

        history_text = "\n".join(
            [f"{ts}: {score}/100 ({risk})" for score, risk, assets, ts in history]
        )

        coach_prompt = f"""
You are an Injective portfolio coach.

User portfolio history:
{history_text}

Latest score: {latest_score}/100
Previous score: {previous_score}/100
Trend: {trend}

Respond ONLY in this format:

Portfolio Coach
• Current score: X/100
• Trend: improved/declined/stable

Advice:
Write 2 short personalized sentences explaining how the user can improve their score.
Keep under 600 characters.
"""

        response = llm.invoke(coach_prompt)
        reply = response.content[:3500]
        await update.message.reply_text(reply)
        return

    # ================= WHAT CHANGED =================
    if user_input.lower() in ["what changed in my portfolio?", "🔄 what changed"]:
        history = portfolio_db.get_history(user_id)

        if len(history) < 2:
            await update.message.reply_text(
                "Not enough portfolio history yet. Run 'Analyze my portfolio' at least twice."
            )
            return

        latest_score, latest_risk, latest_assets, latest_time = history[0]
        prev_score, prev_risk, prev_assets, prev_time = history[1]

        latest_asset_names = {a["symbol"] for a in latest_assets}
        prev_asset_names = {a["symbol"] for a in prev_assets}

        new_assets = latest_asset_names - prev_asset_names
        removed_assets = prev_asset_names - latest_asset_names

        change_prompt = f"""
You are an Injective AI portfolio analyst.

Previous score: {prev_score}/100
Current score: {latest_score}/100

New assets added: {', '.join(new_assets) if new_assets else 'None'}
Assets removed: {', '.join(removed_assets) if removed_assets else 'None'}

Respond ONLY in this format:

Portfolio Change Report
• Previous score: X/100
• Current score: X/100
• New assets: ...
• Removed assets: ...

Insight:
2 concise sentences explaining what changed and one suggestion.
Keep under 650 characters.
"""

        response = llm.invoke(change_prompt)
        reply = response.content[:3500]
        await update.message.reply_text(reply)
        return

    # ================= GENERIC CHAT =================
    try:
        response = chain.invoke(
            {
                "input": user_input,
                "wallet_address": wallet,
                "history": ""
            }
        )

        reply = response.content

        if len(reply) > 3500:
            reply = reply[:3500] + "\n\n... (truncated)"

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Error: {e}")
        print("FULL ERROR:", e)
        await update.message.reply_text(f"Error: {str(e)}")

async def daily_check_job(app):
    users = portfolio_db.get_all_users()

    for user_id, wallet in users:
        try:
            score, risk, assets = calculate_health_score(wallet)

            portfolio_db.save_snapshot(user_id, wallet, score, risk, assets)

            message = f"""
    📅 Daily Portfolio Check
    
    Score: {score}/100
    Risk: {risk}
    
    Use /menu to view full analysis.
    """

            await app.bot.send_message(chat_id=user_id, text=message)

        except Exception as e:
            print("Daily check failed:", e)

def run_daily_check(app):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(daily_check_job(app))
    loop.close()

def generate_report(user_id, wallet, score, risk, assets):
    filename = f"report_{user_id}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Injective AI Strategy Report", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Wallet: {wallet}", styles["BodyText"]))
    story.append(Paragraph(f"Portfolio Health Score: {score}/100", styles["BodyText"]))
    story.append(Paragraph(f"Risk Level: {risk}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Assets", styles["Heading2"]))

    for asset in assets:
        story.append(
            Paragraph(
                f"{asset['symbol']}: {asset['amount']:.2f}",
                styles["BodyText"]
            )
        )

    story.append(Spacer(1, 12))
    story.append(Paragraph("AI Recommendation", styles["Heading2"]))
    story.append(
        Paragraph(
            "Diversify across stable and ecosystem assets to improve portfolio resilience.",
            styles["BodyText"]
        )
    )

    doc.build(story)
    return filename

# ====================== MAIN ======================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: run_daily_check(app),
        trigger="interval",
        hours=24
    )
    scheduler.start()

    print("🤖 Injective AI Copilot Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()

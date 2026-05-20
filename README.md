# Injective AI Copilot Bot

Injective AI Copilot Bot is an AI-powered Telegram assistant that helps users monitor, analyze and optimize their on-chain portfolios within the Injective ecosystem.

It combines real wallet analysis, AI insights, proactive alerts and autonomous portfolio monitoring into one conversational assistant.

---

## Features

### Wallet Connection
- Connect any Injective wallet address directly through Telegram.
- Supports real-time balance retrieval from Injective public API.

### Real Portfolio Analysis
- Fetches live wallet balances.
- Calculates a Portfolio Health Score.
- Assigns a risk level based on portfolio concentration.
- Provides AI-generated portfolio insights.

### Portfolio History Tracking
- Saves snapshots of portfolio score over time.
- Tracks historical health performance.
- Shows previous analyses through Telegram commands or menu buttons.

### AI Portfolio Coach
- Reviews score history.
- Provides personalized suggestions for improving portfolio health.
- Uses AI to explain diversification opportunities.

### What Changed in My Portfolio
- Compares latest and previous snapshots.
- Detects:
  - new assets added
  - removed assets
  - score changes
- Generates AI commentary on changes.

### Auto Alert Mode
Users can set threshold-based alerts:

Example:
notify me if my score drops below 60

The bot automatically warns when the portfolio health score falls below the chosen threshold.

### Daily Auto Portfolio Check
- Runs autonomous scheduled checks every 24 hours.
- Sends proactive Telegram updates to users.
- Stores all daily snapshots in SQLite.

### AI Actionable Alerts
Instead of simple warnings, the bot explains:
- why the score dropped
- what likely changed
- practical actions to improve

### Simulated Rebalance Planner
Users can ask how to rebalance their portfolio.

The bot:
- analyzes current holdings
- simulates an improved allocation
- estimates projected portfolio score after rebalancing

### One-Click AI Strategy Report
Generates downloadable PDF reports containing:
- wallet summary
- portfolio score
- asset holdings
- AI recommendations

---

## Tech Stack

- Python
- Telegram Bot API
- SQLite
- APScheduler
- OpenRouter
- LangChain
- Injective API
- ReportLab

---

## Project Structure

```text
app.py                # Telegram bot main logic
portfolio_utils.py    # Wallet analysis and scoring
portfolio_db.py       # SQLite storage
requirements.txt      # Dependencies
.env                  # Secrets
```

---

## Telegram Commands

| Command           | Description              |
| ----------------- | ------------------------ |
| /start            | Start bot                |
| /menu             | Show menu                |
| Analyze Portfolio | Analyze connected wallet |
| Portfolio History | Show past scores         |
| Improve My Score  | AI coaching              |
| What Changed      | Compare snapshots        |
| Set Alert         | Configure alerts         |
| Rebalance         | AI rebalance simulation  |
| Strategy Report   | Export PDF               |

---

## Future Improvements
- Real trade execution
- Injective staking integration
- Yield optimization engine
- Multi-wallet monitoring
- Web dashboard
- Voice assistant
- DeFi opportunity scanner

---

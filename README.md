# 🛡️ Financial Guardian

Financial Guardian is a zero-g space-themed personal finance and portfolio tracking dashboard. Built with Streamlit, it provides real-time market data, AI-driven insights, advanced portfolio analytics, Telegram price alerts, and secure authentication.

## ✨ Features

### 📊 Portfolio Dashboard
- Track investments across **Stocks, ETFs, and Mutual Funds**
- **Invested Amount** column — Qty × Avg Price per holding
- **XIRR** (annualised return) per holding based on individual buy history
- **NIFTY 50 benchmark overlay** on the 1-month trend chart (indexed to 100)
- **Sector Mix donut chart** — see your portfolio's sector concentration
- **Animated metric cards** (Current Value, Invested, Overall P&L)
- **HTML holdings table** — dark-themed, color-coded P&L, type badges
- **Export Holdings CSV** — download your full portfolio as a spreadsheet
- **Asset type filter** (All / Stock / ETF / MF)

### 🛒 Smart Purchase Tracking
- Every buy is stored individually in the `purchases` collection (source of truth)
- Re-adding the same stock **calculates a weighted average price** — no duplicates
- Aggregated holdings recalculate automatically on every add/edit/delete

### 📋 Past Buys Tab
- Full history of every individual purchase, per holding
- **Inline edit** (price, quantity, date) with per-row Edit button on the left
- **Delete** any individual purchase — holding recalculates instantly
- Color-coded rows: 🟢 green if current price > buy price, 🔴 red if underwater

### ⭐ Watchlist
- Create multiple named watchlists
- Live prices with day-change for all watchlist stocks
- Add/remove stocks via symbol search

### 🔔 Telegram Price Alerts
- Set a target price per stock (above or below)
- Receive a Telegram message the moment the price is hit
- Each user stores their own Telegram Chat ID (private, MongoDB-persisted)
- Powered by a Render **cron job** that checks prices every 15 minutes
- One shared bot: [@Ashwik_finance_tracker_bot](https://t.me/Ashwik_finance_tracker_bot)

### 🤖 AI Guardian Chat
- Integrated AI assistant (Groq API) aware of your portfolio
- Answers financial queries, portfolio analysis, and market questions

### 📰 Market Intelligence
- Aggregated financial news from NewsAPI and RSS feeds
- Filtered for your portfolio holdings and general market

### 🔐 Secure Authentication
- Clerk + Google OAuth for session-based user auth
- All data is isolated per user in MongoDB

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend / Framework | [Streamlit](https://streamlit.io/) ≥ 1.37 |
| Market Data | `yfinance` + Yahoo Finance REST API |
| MF NAV | [mfapi.in](https://www.mfapi.in/) |
| News | NewsAPI + `feedparser` |
| Database | [MongoDB Atlas](https://www.mongodb.com/) |
| AI/LLM | [Groq](https://groq.com/) API |
| Alerts | Telegram Bot API |
| Auth | Clerk + Google OAuth |
| Deployment | [Render](https://render.com/) (Web + Cron Job) |

---

## 🚀 Local Development Setup

### 1. Prerequisites
Python 3.11+ required.

### 2. Clone & Install
```bash
git clone https://github.com/your-username/financial-guardian.git
cd financial-guardian
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root:
```env
MONGODB_URI=your_mongodb_connection_string
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
CLERK_SECRET_KEY=your_clerk_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8501
GROQ_API_KEY=your_groq_api_key
NEWS_API_KEY=your_news_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Set to true to skip login page during local development
LOCAL_DEV=false
```

### 4. Run
```bash
streamlit run app.py
```

---

## 🔔 Telegram Alert Setup (for users)

1. Open Telegram → [start the bot](https://t.me/Ashwik_finance_tracker_bot) → tap **Start**
2. Visit `https://api.telegram.org/bot{TOKEN}/getUpdates` → copy your `"id"` number
3. In the app → **🔔 Alerts** tab → paste your Chat ID → set a target price

---

## 📦 Deployment on Render

- `render.yaml` configures both a **web service** (Streamlit app) and a **cron job** (`alert_checker.py` every 15 min)
- Set all environment variables in Render → Service → Environment
- **Do not set `LOCAL_DEV`** on Render — login is enforced automatically

---

## 📄 License
Open-source and free to use.

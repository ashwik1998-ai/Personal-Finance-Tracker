# 🛡️ Financial Guardian

Financial Guardian is a zero-g space-themed personal finance and portfolio tracking dashboard. Built with Streamlit, it provides real-time market data, AI-driven insights, portfolio analytics, and secure authentication.

## ✨ Features

- **Portfolio Dashboard:** Track your investments across stocks and mutual funds (MFs). Automatically calculates current value, P&L, asset allocation, and the total **amount invested** per holding.
- **Smart Purchase Tracking:** Every buy you make is stored individually. Re-adding the same stock automatically **calculates a weighted average price** — no duplicate rows.
- **Past Buys Tab:** View the full history of every individual purchase. Edit the price, quantity, or date of any past buy, or delete it entirely — the aggregated holding is recalculated automatically.
- **Real-Time Market Data:** Leverages the Yahoo Finance REST API to fetch live stock prices and historical data for portfolio trending.
- **AI Guardian Chat:** An integrated AI assistant (powered by Groq/OpenAI) that understands your portfolio holdings and can answer financial queries.
- **Market Intelligence:** Aggregated news feeds for both your portfolio holdings and general market watchlists using NewsAPI and RSS Feeds.
- **Zero-G Space UI:** A completely custom, dark-mode glassmorphism design with particle-like gradients and neon accents built entirely over Streamlit.
- **Secure Authentication:** Integrated with Clerk and Google OAuth for safe, session-based user authentication.

## 🛠️ Tech Stack

- **Frontend & Framework:** [Streamlit](https://streamlit.io/)
- **Data APIs:**
  - `yfinance` & Yahoo Finance REST API (Market data)
  - `NewsAPI` & `feedparser` (Financial news)
  - `mfapi.in` (Mutual Fund NAV data)
- **Database:** [MongoDB](https://www.mongodb.com/) (Stores user holdings and watchlists)
- **AI/LLM:** [Groq](https://groq.com/) API / OpenAI SDK wrapper
- **Authentication:** Clerk Backend API & requests-oauthlib
- **Deployment:** Render (Docker / Python Runtime)

## 🚀 Local Development Setup

### 1. Prerequisites
Ensure you have Python 3.11+ installed.

### 2. Clone and Install dependencies
```bash
git clone https://github.com/your-username/Personal-Finance-Tracker.git
cd Personal-Finance-Tracker
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory and add the necessary API keys (refer to `.env.template` if available):
```env
MONGODB_URI=your_mongodb_connection_string
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
CLERK_SECRET_KEY=your_clerk_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_redirect_uri
GROQ_API_KEY=your_groq_api_key
NEWS_API_KEY=your_news_api_key
```

### 4. Run the Application
Start the Streamlit development server:
```bash
streamlit run app.py
```
The app will open automatically in your browser at `http://localhost:8501`.

## 📦 Deployment

This project is configured for easy deployment on **Render**:
- A `Dockerfile` is included specifying the build steps.
- A `render.yaml` file is provided for infrastructure-as-code deployment on Render using the native Python environment. Ensure you configure your environment variables securely in the Render dashboard.

## 📄 License
This project is open-source and free to use.

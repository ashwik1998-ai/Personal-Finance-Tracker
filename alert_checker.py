"""
alert_checker.py — Standalone cron script for Telegram price alerts.

Run manually for local testing:
    python alert_checker.py

On Render: configured as a cron job in render.yaml (every 15 minutes).
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MONGODB_URI    = os.environ.get("MONGODB_URI", "")


# ── MongoDB (direct connection — no Streamlit here) ───────────────────────────
def _get_db():
    if not MONGODB_URI:
        print("ERROR: MONGODB_URI not set.")
        sys.exit(1)
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    return client["guardian"]


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(chat_id: str, message: str) -> bool:
    """Send a message via the Telegram Bot API. Returns True on success."""
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code == 200:
            print(f"  ✅ Telegram sent to {chat_id}")
            return True
        else:
            print(f"  ❌ Telegram error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ Telegram exception: {e}")
        return False


# ── Price fetch (direct REST — no Streamlit cache) ────────────────────────────
def fetch_price(symbol: str) -> float:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            result = r.json().get("chart", {}).get("result", [])
            if result:
                closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                closes = [c for c in closes if c is not None]
                if closes:
                    return float(closes[-1])
    except Exception as e:
        print(f"  Price fetch error for {symbol}: {e}")
    return 0.0


# ── Main checker ──────────────────────────────────────────────────────────────
def check_alerts():
    db = _get_db()
    alerts = list(db.price_alerts.find({"active": True}))

    if not alerts:
        print("No active alerts.")
        return

    # Batch all unique symbols
    symbols = list({a["symbol"] for a in alerts})
    print(f"Checking {len(alerts)} alert(s) across {len(symbols)} symbol(s)…")

    prices = {}
    for sym in symbols:
        p = fetch_price(sym)
        prices[sym] = p
        print(f"  {sym}: ₹{p:,.2f}")

    triggered = 0
    for alert in alerts:
        sym      = alert["symbol"]
        target   = alert["target_price"]
        cond     = alert["condition"]    # 'above' | 'below'
        chat_id  = alert["telegram_chat_id"]
        price    = prices.get(sym, 0.0)

        if price <= 0:
            continue

        fired = (cond == "above" and price >= target) or \
                (cond == "below" and price <= target)

        if fired:
            arrow = "📈" if cond == "above" else "📉"
            msg = (
                f"🚨 <b>Price Alert Triggered!</b>\n\n"
                f"{arrow} <b>{sym}</b> is now at <b>₹{price:,.2f}</b>\n"
                f"Your target: ₹{target:,.2f} ({cond})\n\n"
                f"<i>— Financial Guardian</i>"
            )
            ok = send_telegram(chat_id, msg)
            if ok:
                db.price_alerts.update_one(
                    {"_id": alert["_id"]},
                    {"$set": {"active": False, "triggered_at": datetime.utcnow()}}
                )
                triggered += 1

    print(f"\nDone. {triggered}/{len(alerts)} alert(s) triggered.")


if __name__ == "__main__":
    print(f"=== Financial Guardian Alert Checker — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    check_alerts()

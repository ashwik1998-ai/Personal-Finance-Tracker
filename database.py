"""
database.py – MongoDB data layer.
Auth is handled by Clerk. We use the Clerk user_id as the primary key for all
records in our MongoDB collections (holdings, purchases, watchlists).

Holdings collection:   Aggregated view — one doc per symbol per user (weighted avg)
Purchases collection:  Every individual buy transaction — source of truth
"""

import pandas as pd
from datetime import datetime
import os
import streamlit as st
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()


# ── Connection ────────────────────────────────────────────────────────────────

@st.cache_resource
def _get_client() -> MongoClient | None:
    """Return a cached MongoDB client."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        try:
            uri = st.secrets["MONGODB_URI"]
        except Exception:
            pass
    if not uri:
        st.error("MongoDB not configured. Set MONGODB_URI in .env")
        return None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client
    except Exception as e:
        st.error(f"MongoDB connection error: {e}")
        return None


def _db():
    """Return the 'guardian' database."""
    c = _get_client()
    return c["guardian"] if c else None


# ── Session helpers ───────────────────────────────────────────────────────────

def get_current_user_id() -> str | None:
    """Return the logged-in Clerk user_id."""
    user = st.session_state.get("user")
    return user.get("id") if user else None


def get_current_user_email() -> str | None:
    user = st.session_state.get("user")
    return user.get("email") if user else None


# ── Internal: Rebuild aggregated holding from purchases ───────────────────────

def _rebuild_holding(user_id: str, symbol: str, asset_type: str):
    """
    Recalculate the aggregated holding for a symbol from all its purchases.
    Upserts a single doc into `holdings`. Removes the holding if no purchases remain.
    """
    database = _db()
    if database is None:
        return

    purchases = list(database.purchases.find(
        {"user_id": user_id, "symbol": symbol}
    ))

    if not purchases:
        # No purchases left — remove the holding entirely
        database.holdings.delete_one({"user_id": user_id, "symbol": symbol})
    else:
        total_qty = sum(p["quantity"] for p in purchases)
        total_cost = sum(p["buy_price"] * p["quantity"] for p in purchases)
        weighted_avg = total_cost / total_qty if total_qty > 0 else 0.0
        earliest_date = min(p.get("purchase_date", "") for p in purchases)

        database.holdings.update_one(
            {"user_id": user_id, "symbol": symbol},
            {"$set": {
                "user_id":       user_id,
                "symbol":        symbol,
                "asset_type":    asset_type,
                "avg_price":     round(weighted_avg, 4),
                "quantity":      round(total_qty, 4),
                "purchase_date": earliest_date,
                "updated_at":    datetime.utcnow(),
            }},
            upsert=True,
        )

    # Bust caches
    get_all_holdings.clear()
    get_all_purchases.clear()


# ── Purchases (individual buy transactions) ───────────────────────────────────

def add_purchase(symbol: str, asset_type: str, buy_price: float,
                 quantity: float, purchase_date: str):
    """
    Add an individual purchase record and update the aggregated holding.
    If a holding already exists for this symbol, the weighted average is recalculated.
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return

    sym = symbol.upper()
    atype = asset_type.upper()

    database.purchases.insert_one({
        "user_id":       user_id,
        "symbol":        sym,
        "asset_type":    atype,
        "buy_price":     float(buy_price),
        "quantity":      float(quantity),
        "purchase_date": purchase_date,
        "created_at":    datetime.utcnow(),
    })

    _rebuild_holding(user_id, sym, atype)


@st.cache_data(ttl=30)
def get_all_purchases() -> pd.DataFrame:
    """Return all individual purchase records for the current user."""
    user_id = get_current_user_id()
    if not user_id:
        return pd.DataFrame()
    database = _db()
    if database is None:
        return pd.DataFrame()
    docs = list(database.purchases.find(
        {"user_id": user_id},
        sort=[("purchase_date", -1), ("created_at", -1)]
    ))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    df["id"] = df["_id"].astype(str)
    return df.drop(columns=["_id"])


def update_purchase(purchase_id: str, buy_price: float, quantity: float,
                    purchase_date: str):
    """
    Edit an existing purchase and recalculate the parent holding's weighted average.
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return

    doc = database.purchases.find_one(
        {"_id": ObjectId(purchase_id), "user_id": user_id}
    )
    if not doc:
        return

    database.purchases.update_one(
        {"_id": ObjectId(purchase_id), "user_id": user_id},
        {"$set": {
            "buy_price":     float(buy_price),
            "quantity":      float(quantity),
            "purchase_date": purchase_date,
            "updated_at":    datetime.utcnow(),
        }},
    )

    _rebuild_holding(user_id, doc["symbol"], doc["asset_type"])


def delete_purchase(purchase_id: str):
    """
    Delete a purchase and recalculate (or remove) the parent holding.
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return

    doc = database.purchases.find_one(
        {"_id": ObjectId(purchase_id), "user_id": user_id}
    )
    if not doc:
        return

    database.purchases.delete_one({"_id": ObjectId(purchase_id), "user_id": user_id})
    _rebuild_holding(user_id, doc["symbol"], doc["asset_type"])


# ── Holdings (aggregated, auto-calculated) ────────────────────────────────────

@st.cache_data(ttl=30)
def get_all_holdings() -> pd.DataFrame:
    user_id = get_current_user_id()
    if not user_id:
        return pd.DataFrame()
    database = _db()
    if database is None:
        return pd.DataFrame()
    docs = list(database.holdings.find({"user_id": user_id}))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    df["id"] = df["_id"].astype(str)
    return df.drop(columns=["_id"])


def delete_holding(holding_id: str):
    """
    Delete a holding and ALL its underlying purchases.
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return

    doc = database.holdings.find_one(
        {"_id": ObjectId(holding_id), "user_id": user_id}
    )
    if doc:
        # Remove all purchases for this symbol too
        database.purchases.delete_many(
            {"user_id": user_id, "symbol": doc["symbol"]}
        )
        database.holdings.delete_one(
            {"_id": ObjectId(holding_id), "user_id": user_id}
        )

    get_all_holdings.clear()
    get_all_purchases.clear()


# ── Price Alerts ─────────────────────────────────────────────────────────────────────────

def add_alert(symbol: str, target_price: float, condition: str,
              telegram_chat_id: str):
    """
    Create a new price alert for the current user.
    condition: 'above' | 'below'
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return
    database.price_alerts.insert_one({
        "user_id":          user_id,
        "symbol":           symbol.upper(),
        "target_price":     float(target_price),
        "condition":        condition,
        "telegram_chat_id": str(telegram_chat_id).strip(),
        "active":           True,
        "triggered_at":     None,
        "created_at":       datetime.utcnow(),
    })
    get_all_alerts.clear()


@st.cache_data(ttl=30)
def get_all_alerts(user_id: str) -> pd.DataFrame:
    """Return all alerts (active + triggered) for the given user_id.
    user_id passed as argument so each user gets their own cache slot.
    """
    if not user_id:
        return pd.DataFrame()
    database = _db()
    if database is None:
        return pd.DataFrame()
    docs = list(database.price_alerts.find(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    ))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    df["id"] = df["_id"].astype(str)
    return df.drop(columns=["_id"])


def delete_alert(alert_id: str):
    """Delete a price alert."""
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return
    database.price_alerts.delete_one(
        {"_id": ObjectId(alert_id), "user_id": user_id}
    )
    get_all_alerts.clear()


# ── User Settings (persistent per-user preferences) ───────────────────────────

def save_user_setting(key: str, value: str):
    """Persist a user-level setting (e.g. telegram_chat_id) in MongoDB."""
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return
    database.user_settings.update_one(
        {"user_id": user_id},
        {"$set": {key: value, "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    _get_user_setting_cached.clear()


@st.cache_data(ttl=300)
def _get_user_setting_cached(user_id: str, key: str) -> str:
    """Cached helper — user_id in signature so each user gets own slot."""
    database = _db()
    if database is None:
        return ""
    doc = database.user_settings.find_one({"user_id": user_id}) or {}
    return doc.get(key, "")


def get_user_setting(key: str) -> str:
    """Return a saved user setting from MongoDB."""
    user_id = get_current_user_id()
    if not user_id:
        return ""
    return _get_user_setting_cached(user_id, key)


def get_all_alerts_for_checker() -> list:
    """
    Return ALL active alerts across all users.
    Called by the alert_checker.py cron script (not user-scoped).
    """
    database = _db()
    if database is None:
        return []
    return list(database.price_alerts.find({"active": True}))


def mark_alert_triggered(alert_id: str):
    """Deactivate an alert after it fires."""
    database = _db()
    if database is None:
        return
    database.price_alerts.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"active": False, "triggered_at": datetime.utcnow()}}
    )


# ── Watchlists ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def get_watchlists() -> list[dict]:
    user_id = get_current_user_id()
    if not user_id:
        return []
    database = _db()
    if database is None:
        return []
    docs = list(database.watchlists.find({"user_id": user_id}))
    for doc in docs:
        doc["id"] = str(doc["_id"])
    return docs


def create_watchlist(name: str):
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return
    database.watchlists.insert_one({
        "user_id":    user_id,
        "name":       name,
        "symbols":    [],
        "created_at": datetime.utcnow(),
    })
    get_watchlists.clear()


def update_watchlist_symbols(watchlist_id: str, symbols: list[str]):
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return
    database.watchlists.update_one(
        {"_id": ObjectId(watchlist_id), "user_id": user_id},
        {"$set": {"symbols": symbols}},
    )
    get_watchlists.clear()


def delete_watchlist(watchlist_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return
    database = _db()
    if database is None:
        return
    database.watchlists.delete_one(
        {"_id": ObjectId(watchlist_id), "user_id": user_id}
    )
    get_watchlists.clear()

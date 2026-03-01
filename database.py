"""
database.py – MongoDB data layer.
Auth is handled by Clerk. We use the Clerk user_id as the primary key for all
records in our MongoDB collections (holdings, watchlists).
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


# ── Holdings ─────────────────────────────────────────────────────────────────

def add_holding(symbol: str, asset_type: str, avg_price: float,
                quantity: float, purchase_date: str):
    user_id = get_current_user_id()
    if not user_id:
        return
    db = _db()
    if db is None:
        return
    db.holdings.insert_one({
        "user_id":       user_id,
        "symbol":        symbol.upper(),
        "asset_type":    asset_type.upper(),
        "avg_price":     float(avg_price),
        "quantity":      float(quantity),
        "purchase_date": purchase_date,
        "created_at":    datetime.utcnow(),
    })
    get_all_holdings.clear()  # invalidate cache


@st.cache_data(ttl=30)
def get_all_holdings() -> pd.DataFrame:
    user_id = get_current_user_id()
    if not user_id:
        return pd.DataFrame()
    db = _db()
    if db is None:
        return pd.DataFrame()
    docs = list(db.holdings.find({"user_id": user_id}))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    df["id"] = df["_id"].astype(str)
    return df.drop(columns=["_id"])


def delete_holding(holding_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return
    db = _db()
    if db is None:
        return
    db.holdings.delete_one({"_id": ObjectId(holding_id), "user_id": user_id})
    get_all_holdings.clear()  # invalidate cache


# ── Watchlists ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def get_watchlists() -> list[dict]:
    user_id = get_current_user_id()
    if not user_id:
        return []
    db = _db()
    if db is None:
        return []
    docs = list(db.watchlists.find({"user_id": user_id}))
    for doc in docs:
        doc["id"] = str(doc["_id"])
    return docs


def create_watchlist(name: str):
    user_id = get_current_user_id()
    if not user_id:
        return
    db = _db()
    if db is None:
        return
    db.watchlists.insert_one({
        "user_id":    user_id,
        "name":       name,
        "symbols":    [],
        "created_at": datetime.utcnow(),
    })
    get_watchlists.clear()  # invalidate cache


def update_watchlist_symbols(watchlist_id: str, symbols: list[str]):
    user_id = get_current_user_id()
    if not user_id:
        return
    db = _db()
    if db is None:
        return
    db.watchlists.update_one(
        {"_id": ObjectId(watchlist_id), "user_id": user_id},
        {"$set": {"symbols": symbols}},
    )
    get_watchlists.clear()  # invalidate cache


def delete_watchlist(watchlist_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return
    db = _db()
    if db is None:
        return
    db.watchlists.delete_one({"_id": ObjectId(watchlist_id), "user_id": user_id})
    get_watchlists.clear()  # invalidate cache

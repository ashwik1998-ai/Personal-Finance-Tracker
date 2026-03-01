import yfinance as yf
import requests
import pandas as pd
import streamlit as st

# ── Price fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_stock_price(symbol: str) -> float:
    """Single symbol price — uses batch fetcher internally."""
    prices = _batch_fetch_prices((symbol,))
    return prices.get(symbol, 0.0)


@st.cache_data(ttl=300)
def _batch_fetch_prices(symbols: tuple) -> dict:
    """Batch-download latest close prices for many symbols in one yfinance call.
    Falls back to per-symbol Ticker.history() if batch returns 0.0 for any symbol."""
    if not symbols:
        return {}

    # Deduplicate: yfinance returns unexpected formats with duplicate tickers
    unique_syms = list(dict.fromkeys(symbols))

    def _ticker_fallback(sym: str) -> float:
        """Per-symbol fallback using Ticker.history() — works without threading."""
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if not hist.empty and "Close" in hist.columns:
                val = hist["Close"].dropna()
                return float(val.iloc[-1]) if not val.empty else 0.0
        except Exception:
            pass
        return 0.0

    try:
        # Use threads=False for Linux server compatibility (Render/Docker)
        data = yf.download(unique_syms, period="5d", progress=False, threads=False)
        if data.empty:
            # Full fallback to individual fetches
            price_lookup = {sym: _ticker_fallback(sym) for sym in unique_syms}
            return {s: price_lookup.get(s, 0.0) for s in symbols}

        try:
            closes = data["Close"]
        except KeyError:
            price_lookup = {sym: _ticker_fallback(sym) for sym in unique_syms}
            return {s: price_lookup.get(s, 0.0) for s in symbols}

        # If only 1 unique symbol, result may be a Series not a DataFrame
        if isinstance(closes, pd.Series):
            sym = unique_syms[0]
            val = float(closes.dropna().iloc[-1]) if not closes.dropna().empty else 0.0
            if val == 0.0:
                val = _ticker_fallback(sym)
            return {s: val for s in symbols}

        # Multiple symbols → DataFrame with symbol columns
        price_lookup = {}
        for sym in unique_syms:
            try:
                col = closes[sym].dropna()
                price = float(col.iloc[-1]) if not col.empty else 0.0
            except Exception:
                price = 0.0
            # If still 0, try individual fallback
            if price == 0.0:
                price = _ticker_fallback(sym)
            price_lookup[sym] = price
        return {s: price_lookup.get(s, 0.0) for s in symbols}

    except Exception as e:
        print(f"Batch price fetch error: {e}")
        # Full fallback
        price_lookup = {sym: _ticker_fallback(sym) for sym in unique_syms}
        return {s: price_lookup.get(s, 0.0) for s in symbols}



@st.cache_data(ttl=120)
def fetch_watchlist_prices(symbols: tuple) -> list[dict]:
    """Batch-fetch live price + day-change for watchlist symbols (one yfinance call)."""
    fallback = [{"symbol": s, "name": s, "price": None, "chg": None, "chg_pct": None} for s in symbols]
    if not symbols:
        return []
    try:
        # Use 5d to ensure we have at least 2 trading days to calculate daily change, even on weekends
        data = yf.download(list(symbols), period="5d", progress=False, threads=True)
        if data.empty:
            return fallback
        try:
            closes = data["Close"]
        except KeyError:
            return fallback

        name_map = _get_names_fast(symbols)
        results = []
        for sym in symbols:
            try:
                series = closes if isinstance(closes, pd.Series) else closes[sym]
                series = series.dropna()
                if len(series) >= 2:
                    prev, price = float(series.iloc[-2]), float(series.iloc[-1])
                    chg   = price - prev
                    chg_p = (chg / prev * 100) if prev else 0.0
                elif len(series) == 1:
                    price = float(series.iloc[-1])
                    chg, chg_p = 0.0, 0.0
                else:
                    price, chg, chg_p = None, None, None
            except Exception:
                price, chg, chg_p = None, None, None
            results.append({"symbol": sym, "name": name_map.get(sym, sym),
                             "price": price, "chg": chg, "chg_pct": chg_p})
        return results
    except Exception as e:
        print(f"Watchlist price fetch error: {e}")
        return fallback



# ── Company name resolution ────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def _get_names_fast(symbols: tuple) -> dict:
    """
    Fast company-name lookup using Yahoo Finance search API (no full ticker.info call).
    Falls back to stripping suffix if search fails.
    """
    names = {}
    for sym in symbols:
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={sym}"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                quotes = r.json().get("quotes", [])
                match = next((q for q in quotes if q.get("symbol") == sym), None)
                long = (match or {}).get("shortname") or (match or {}).get("longname")
                if long:
                    for s in [" Limited", " Ltd", " Ltd.", " Inc.", " Inc", " Corp.", " Corp"]:
                        long = long.replace(s, "")
                    names[sym] = long.strip()
                    continue
        except Exception:
            pass
        names[sym] = sym.replace(".NS", "").replace(".BO", "").replace("-USD", "")
    return names


@st.cache_data(ttl=86400)
def get_company_names(symbols: tuple) -> dict:
    """Public wrapper — returns {symbol: 'Company Name'}."""
    return _get_names_fast(symbols)


# ── Portfolio metrics (batched) ────────────────────────────────────────────────

def get_portfolio_metrics(holdings_df: pd.DataFrame):
    """Calculate portfolio metrics using a SINGLE batch price fetch."""
    if holdings_df.empty:
        return 0.0, 0.0, 0.0, 0.0, holdings_df

    stocks_etf = holdings_df[holdings_df["asset_type"].isin(["STOCK", "ETF"])]["symbol"].tolist()
    mf_rows    = holdings_df[holdings_df["asset_type"] == "MF"]

    # One batch call for all stocks/ETFs
    price_map = _batch_fetch_prices(tuple(stocks_etf)) if stocks_etf else {}

    # MF NAVs (still individual but cached)
    for _, row in mf_rows.iterrows():
        price_map[row["symbol"]] = fetch_mf_nav(row["symbol"])

    total_investment = 0.0
    current_value    = 0.0
    current_prices, current_values, unrealized_pls, unrealized_pl_pcts = [], [], [], []

    for _, row in holdings_df.iterrows():
        price    = price_map.get(row["symbol"], 0.0)
        invested = row["avg_price"] * row["quantity"]
        c_val    = price * row["quantity"]
        pl       = c_val - invested
        pl_pct   = (pl / invested * 100) if invested > 0 else 0.0

        total_investment += invested
        current_value    += c_val
        current_prices.append(price)
        current_values.append(c_val)
        unrealized_pls.append(pl)
        unrealized_pl_pcts.append(pl_pct)

    holdings_df = holdings_df.copy()
    holdings_df["current_price"]    = current_prices
    holdings_df["current_value"]    = current_values
    holdings_df["unrealized_pl"]    = unrealized_pls
    holdings_df["unrealized_pl_pct"] = unrealized_pl_pcts

    total_pl     = current_value - total_investment
    total_pl_pct = (total_pl / total_investment * 100) if total_investment > 0 else 0.0
    return total_investment, current_value, total_pl, total_pl_pct, holdings_df


# ── Historical data ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_historical_data(symbol: str, period: str = "1mo") -> pd.Series:
    """Single symbol historical close — uses ticker.history() to avoid MultiIndex issues."""
    try:
        hist = yf.Ticker(symbol).history(period=period)
        return hist["Close"] if not hist.empty else pd.Series()
    except Exception:
        return pd.Series()


@st.cache_data(ttl=600)
def fetch_portfolio_trend(symbols_qty: tuple) -> "pd.Series":
    """
    Batch-fetch 1M history for all portfolio symbols in ONE call.
    symbols_qty: tuple of (symbol, quantity) pairs
    Returns a daily total portfolio value Series.
    Handles duplicate symbols by summing their quantities.
    """
    if not symbols_qty:
        return pd.Series(dtype=float)

    # Aggregate quantities for duplicate symbols
    qty_map: dict = {}
    for s, q in symbols_qty:
        qty_map[s] = qty_map.get(s, 0) + q
    unique_symbols = list(qty_map.keys())

    try:
        data = yf.download(unique_symbols, period="1mo", progress=False, threads=True)
        try:
            closes = data["Close"]
        except KeyError:
            return pd.Series(dtype=float)

        if isinstance(closes, pd.Series):
            # Single symbol returned as Series
            sym = unique_symbols[0]
            qty = qty_map.get(sym, 1)
            return (closes.dropna() * qty).rename("Value")

        total = None
        for sym in unique_symbols:
            if sym in closes.columns:
                try:
                    series = closes[sym].dropna() * qty_map.get(sym, 1)
                    total = series if total is None else total.add(series, fill_value=0)
                except Exception:
                    continue
        return total if total is not None else pd.Series(dtype=float)
    except Exception as e:
        print(f"Portfolio trend fetch error: {e}")
        return pd.Series(dtype=float)


# ── MF NAV ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_mf_nav(amfi_code) -> float:
    try:
        r = requests.get(f"https://api.mfapi.in/mf/{amfi_code}", timeout=8)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                return float(data[0]["nav"])
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=86400)
def get_mf_name(amfi_code) -> str:
    """Fetch the name of a Mutual Fund using its AMFI code."""
    try:
        r = requests.get(f"https://api.mfapi.in/mf/{amfi_code}", timeout=8)
        if r.status_code == 200:
            return r.json().get("meta", {}).get("scheme_name", str(amfi_code))
    except Exception:
        pass
    return str(amfi_code)


def search_mf(query: str) -> list:
    try:
        r = requests.get(f"https://api.mfapi.in/mf/search?q={query}", timeout=8)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


# ── Symbol search ──────────────────────────────────────────────────────────────

def search_symbols(query: str) -> list:
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            return [
                {
                    "symbol":    q.get("symbol"),
                    "shortname": q.get("shortname") or q.get("symbol"),
                    "exchange":  q.get("exchDisp"),
                }
                for q in r.json().get("quotes", [])
                if q.get("quoteType") in ("EQUITY", "ETF")
            ]
    except Exception as e:
        print(f"Symbol search error: {e}")
    return []

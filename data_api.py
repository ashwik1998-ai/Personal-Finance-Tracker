import yfinance as yf
import requests
import pandas as pd
import streamlit as st
from datetime import date as _date, datetime

# ── Price fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_stock_price(symbol: str) -> float:
    """Single symbol price — uses batch fetcher internally."""
    prices = _batch_fetch_prices((symbol,))
    return prices.get(symbol, 0.0)


def _fetch_price_via_api(symbol: str) -> float:
    """
    Fetch latest close price directly from Yahoo Finance REST API using requests.
    This is the primary method — works on any server where requests works.
    """
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
        print(f"Yahoo REST API error for {symbol}: {e}")
    return 0.0


@st.cache_data(ttl=300)
def _batch_fetch_prices(symbols: tuple) -> dict:
    """Fetch latest close prices using Yahoo Finance REST API (via requests).
    Falls back to yfinance as a last resort."""
    if not symbols:
        return {}

    # Deduplicate while preserving order
    unique_syms = list(dict.fromkeys(symbols))
    price_lookup = {}

    for sym in unique_syms:
        price = _fetch_price_via_api(sym)
        if price == 0.0:
            # Last-resort: try yfinance Ticker (in case REST API is blocked)
            try:
                hist = yf.Ticker(sym).history(period="5d")
                if not hist.empty and "Close" in hist.columns:
                    col = hist["Close"].dropna()
                    price = float(col.iloc[-1]) if not col.empty else 0.0
            except Exception:
                price = 0.0
        price_lookup[sym] = price

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
        
        # Drop columns (symbols) that returned entirely NaN
        closes = closes.dropna(axis=1, how='all')
        if closes.empty:
            return pd.Series(dtype=float)

        total = None
        for sym in unique_symbols:
            if sym in closes.columns:
                try:
                    series = closes[sym].dropna() * qty_map.get(sym, 1)
                    if total is None:
                        total = series
                    else:
                        # Forward fill then fillna(0) to handle missing days between symbols cleanly
                        total = total.add(series, fill_value=0)
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


# ── XIRR ─────────────────────────────────────────────────────────────────────

def _compute_xirr(cashflows: list) -> float:
    """
    XIRR via bisection — no scipy needed.
    cashflows: list of (date_obj, amount) where negative=paid, positive=received.
    Returns decimal rate (0.45 = 45 % p.a.).
    """
    if not cashflows or len(cashflows) < 2:
        return 0.0
    dates   = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    t0      = min(dates)
    years   = [(d - t0).days / 365.25 for d in dates]

    def npv(rate: float) -> float:
        if rate <= -1:
            return float("inf")
        return sum(a / ((1.0 + rate) ** t) for a, t in zip(amounts, years))

    try:
        if npv(-0.9999) * npv(100.0) > 0:
            return 0.0
        lo, hi = -0.9999, 100.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            v   = npv(mid)
            if abs(v) < 1e-7:
                return mid
            if npv(lo) * v < 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2.0
    except Exception:
        return 0.0


def get_xirr_per_symbol(purchases_df: "pd.DataFrame", price_dict: dict) -> dict:
    """
    Compute XIRR per symbol from purchase history + current price.
    Returns {symbol: xirr_pct} e.g. {"TATAPOWER.NS": 45.2}.
    None means insufficient data.
    """
    today  = _date.today()
    result = {}
    if purchases_df is None or purchases_df.empty:
        return result

    for symbol, group in purchases_df.groupby("symbol"):
        current_price = price_dict.get(symbol, 0.0)
        if current_price <= 0:
            result[symbol] = None
            continue

        cashflows = []
        for _, row in group.iterrows():
            try:
                d = datetime.strptime(str(row["purchase_date"]), "%Y-%m-%d").date()
            except Exception:
                d = today
            cashflows.append((d, -(float(row["buy_price"]) * float(row["quantity"]))))

        total_qty = float(group["quantity"].sum())
        cashflows.append((today, current_price * total_qty))

        xirr = _compute_xirr(cashflows)
        result[symbol] = round(xirr * 100, 2)

    return result


# ── Benchmark (NIFTY 50) ──────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def fetch_benchmark_trend() -> "pd.Series":
    """
    Fetch NIFTY 50 (^NSEI) 1-month daily close prices via Yahoo Finance REST API.
    Returns a pd.Series indexed by DatetimeIndex, named 'NIFTY 50'.
    """
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=1mo"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            res = r.json().get("chart", {}).get("result", [])
            if res:
                ts     = res[0].get("timestamp", [])
                closes = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                pairs  = [
                    (pd.Timestamp(t, unit="s").normalize(), c)
                    for t, c in zip(ts, closes) if c is not None
                ]
                if pairs:
                    idx, vals = zip(*pairs)
                    return pd.Series(list(vals), index=pd.DatetimeIndex(idx), name="NIFTY 50")
    except Exception as e:
        print(f"Benchmark fetch error: {e}")
    return pd.Series(dtype=float, name="NIFTY 50")


# ── Sector data ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def fetch_sector(symbol: str) -> str:
    """
    Return the GICS sector for a stock/ETF symbol via Yahoo Finance quoteSummary.
    Returns 'Other' for mutual funds or on any failure.
    """
    try:
        url = (
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
            f"?modules=assetProfile"
        )
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            profile = (
                r.json()
                .get("quoteSummary", {})
                .get("result", [{}])[0]
                .get("assetProfile", {})
            )
            return profile.get("sector", "") or "Other"
    except Exception:
        pass
    return "Other"

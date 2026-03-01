import yfinance as yf
import requests
import pandas as pd
from datetime import datetime
import streamlit as st

@st.cache_data(ttl=300) # Cache for 5 minutes
def fetch_stock_price(symbol):
    """Fetch latest price for a stock/ETF using yfinance."""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return 0.0
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return 0.0


@st.cache_data(ttl=86400)  # cache for 24 hours — company names rarely change
def get_company_names(symbols: tuple) -> dict:
    """Return {symbol: 'Company Name'} for news search queries."""
    names = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info
            long = info.get("longName") or info.get("shortName")
            if long:
                for suffix in [" Limited", " Ltd", " Ltd.", " Inc.", " Inc", " Corp.", " Corp"]:
                    long = long.replace(suffix, "")
                names[sym] = long.strip()
            else:
                names[sym] = sym.replace(".NS", "").replace(".BO", "").replace("-USD", "")
        except Exception:
            names[sym] = sym.replace(".NS", "").replace(".BO", "")
    return names


@st.cache_data(ttl=3600)
def fetch_historical_data(symbol, period="1mo"):
    """Fetch historical prices for a stock/ETF."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if not df.empty:
            return df['Close']
        return pd.Series()
    except Exception as e:
        print(f"Error fetching historical for {symbol}: {e}")
        return pd.Series()

@st.cache_data(ttl=3600) # Cache for 1 hour as NAV updates once daily
def fetch_mf_nav(amfi_code):
    """Fetch latest NAV for an Indian Mutual Fund using mfapi.in."""
    try:
        url = f"https://api.mfapi.in/mf/{amfi_code}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and "data" in data and len(data["data"]) > 0:
                # Get the latest entry
                latest_nav = data["data"][0]["nav"]
                return float(latest_nav)
        return 0.0
    except Exception as e:
        print(f"Error fetching NAV for {amfi_code}: {e}")
        return 0.0

def search_mf(query):
    """Search for Mutual Funds to get their AMFI code."""
    try:
         url = f"https://api.mfapi.in/mf/search?q={query}"
         response = requests.get(url, timeout=10)
         if response.status_code == 200:
             return response.json()
         return []
    except Exception as e:
         print(f"Error searching MF {query}: {e}")
         return []

@st.cache_data(ttl=120)   # refresh every 2 minutes
def fetch_watchlist_prices(symbols: tuple) -> list[dict]:
    """Batch-fetch live price + day-change for watchlist symbols."""
    results = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev  = float(hist['Close'].iloc[-2])
                price = float(hist['Close'].iloc[-1])
                chg   = price - prev
                chg_p = (chg / prev * 100) if prev else 0.0
            elif len(hist) == 1:
                price = float(hist['Close'].iloc[-1])
                chg, chg_p = 0.0, 0.0
            else:
                price, chg, chg_p = None, None, None
            info = t.fast_info
            name = getattr(info, "longName", None) or sym
        except Exception:
            price, chg, chg_p, name = None, None, None, sym
        results.append({"symbol": sym, "name": name,
                         "price": price, "chg": chg, "chg_pct": chg_p})
    return results

def search_symbols(query):
    """Search for Stocks/ETFs by name/symbol using yfinance query engine."""
    try:
        # yfinance internal search endpoint
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = []
            for quote in data.get('quotes', []):
                # Filter for useful types
                if quote.get('quoteType') in ['EQUITY', 'ETF']:
                    results.append({
                        'symbol': quote.get('symbol'),
                        'shortname': quote.get('shortname') or quote.get('symbol'),
                        'exchange': quote.get('exchDisp')
                    })
            return results
        return []
    except Exception as e:
        print(f"Error searching symbols {query}: {e}")
        return []

def get_portfolio_metrics(holdings_df):
    """Calculate real-time portfolio metrics."""
    if holdings_df.empty:
        return 0.0, 0.0, 0.0, 0.0, holdings_df

    total_investment = 0.0
    current_value = 0.0

    current_prices = []
    current_values = []
    unrealized_pls = []
    unrealized_pl_pcts = []

    for index, row in holdings_df.iterrows():
        symbol = row['symbol']
        asset_type = row['asset_type']
        avg_price = row['avg_price']
        qty = row['quantity']

        invested = avg_price * qty
        total_investment += invested

        price = 0.0
        if asset_type in ['STOCK', 'ETF']:
            price = fetch_stock_price(symbol)
        elif asset_type == 'MF':
             price = fetch_mf_nav(symbol)

        c_val = price * qty
        current_value += c_val

        pl = c_val - invested
        pl_pct = (pl / invested * 100) if invested > 0 else 0

        current_prices.append(price)
        current_values.append(c_val)
        unrealized_pls.append(pl)
        unrealized_pl_pcts.append(pl_pct)

    holdings_df['current_price'] = current_prices
    holdings_df['current_value'] = current_values
    holdings_df['unrealized_pl'] = unrealized_pls
    holdings_df['unrealized_pl_pct'] = unrealized_pl_pcts

    total_pl = current_value - total_investment
    total_pl_pct = (total_pl / total_investment * 100) if total_investment > 0 else 0

    return total_investment, current_value, total_pl, total_pl_pct, holdings_df

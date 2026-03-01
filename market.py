import streamlit as st
import requests
import feedparser
import database as db
import data_api as api
import os


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _get_news_key() -> str | None:
    key = os.environ.get("NEWS_API_KEY")
    if not key:
        try:
            key = st.secrets["NEWS_API_KEY"]
        except Exception:
            pass
    return key


def _clean_symbol(symbol: str) -> str:
    """Strip exchange suffixes to get a clean name for news search."""
    return (symbol
            .replace(".NS", "").replace(".BO", "")
            .replace("-USD", "").replace("-INR", "")
            .strip())


def _fetch_newsapi(symbols: list[str], max_results: int = 15) -> list[dict]:
    """
    Fetch news using company names (resolved via yfinance) so that
    'TATAPOWER.NS' becomes 'Tata Power' for the search query.
    """
    news_key = _get_news_key()
    if not news_key or not symbols:
        return []

    # Resolve symbols → company names for much better news matching
    name_map   = api.get_company_names(tuple(symbols))
    search_terms = list(name_map.values())

    query = " OR ".join(f'"{t}"' for t in search_terms)

    url = (
        f"https://newsapi.org/v2/everything"
        f"?qInTitle={requests.utils.quote(query)}"
        f"&sortBy=relevancy"
        f"&language=en"
        f"&pageSize=40"
        f"&apiKey={news_key}"
    )

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            st.warning(f"NewsAPI: {response.json().get('message', 'Unknown error')}")
            return []

        articles = response.json().get("articles", [])
        # Post-filter: title must contain at least one company name
        relevant = [
            art for art in articles
            if art.get("title") and any(
                t.lower() in art["title"].lower() for t in search_terms
            )
        ]
        return relevant[:max_results]

    except Exception as e:
        st.warning(f"News fetch error: {e}")
        return []


def _fetch_rss(sources: list[str]) -> list[dict]:
    """Fetch RSS feeds from selected financial sources."""
    source_map = {
        "LiveMint Markets": "https://www.livemint.com/rss/markets",
        "MoneyControl": "https://www.moneycontrol.com/rss/latestnews.xml",
        "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "NDTV Profit": "https://www.ndtv.com/rss/profit",
        "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    }

    all_news = []
    for source in sources:
        url = source_map.get(source)
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                all_news.append({
                    "title": entry.title,
                    "url": entry.link,
                    "source": {"name": source},
                    "publishedAt": entry.get("published", ""),
                    "description": entry.get("summary", ""),
                })
        except Exception as e:
            print(f"RSS error {source}: {e}")

    return all_news


# ──────────────────────────────────────────────
#  Renderers
# ──────────────────────────────────────────────

def _render_article_card(article: dict):
    title = article.get("title", "No Title")
    url = article.get("url") or article.get("link", "#")
    source = article.get("source", {})
    if isinstance(source, dict):
        source_name = source.get("name", "Unknown")
    else:
        source_name = str(source)
    pub_date = article.get("publishedAt", article.get("published", ""))[:10]
    description = article.get("description") or ""

    st.markdown(f"""
    <div style="
        background: rgba(15,23,42,0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(56,189,248,0.12);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    ">
        <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;
                    letter-spacing:0.06em;margin-bottom:0.35rem;">
            {source_name} &nbsp;·&nbsp; {pub_date}
        </div>
        <a href="{url}" target="_blank" style="
            font-size:0.95rem; font-weight:600; color:#e2e8f0;
            text-decoration:none; line-height:1.45; display:block; margin-bottom:0.4rem;
        ">{title}</a>
        <div style="font-size:0.82rem;color:#64748b;line-height:1.5;">
            {description[:200]}{"..." if len(description) > 200 else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_news_list(articles: list[dict], empty_msg: str):
    if not articles:
        st.info(empty_msg)
        return
    for art in articles:
        _render_article_card(art)


# ──────────────────────────────────────────────
#  Main Render Function
# ──────────────────────────────────────────────

def render_market_intelligence():
    # Header row with watchlist selector on the right
    # ── Full-width header ────────────────────────────────────────────────────
    st.markdown("""
    <div style="
        padding: 1.5rem 2rem;
        background: rgba(15,23,42,0.7);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(56,189,248,0.15);
        border-radius: 16px;
        margin-bottom: 1.2rem;
    ">
        <div style="
            font-size: 1.5rem; font-weight: 700;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        ">📰 Market Intelligence</div>
        <div style="font-size: 0.85rem; color: #475569; margin-top: 0.3rem;">
            News filtered by your portfolio &amp; watchlists
        </div>
    </div>
    """, unsafe_allow_html=True)

    watchlists = db.get_watchlists()

    # ── TABS ──────────────────────────────────────────────────────────────────
    tab_port, tab_wl, tab_global = st.tabs([
        "📈 My Portfolio News",
        "⭐ Watchlist News",
        "🌍 Global Pulse",
    ])

    # ── Tab 1: Portfolio News ─────────────────────────────────────────────────
    with tab_port:
        holdings_df = db.get_all_holdings()
        if holdings_df.empty:
            st.info("Add holdings to your portfolio to see relevant news here.")
        else:
            # Filter out MF and ETF, only fetch news for purely STOCK assets
            stock_only_df = holdings_df[holdings_df['asset_type'] == 'STOCK']
            if stock_only_df.empty:
                st.info("Add stock holdings to your portfolio to see relevant news here.")
            else:
                port_syms = stock_only_df["symbol"].unique().tolist()
                name_map  = api.get_company_names(tuple(port_syms))

                # Portfolio stock filter (ALL + individual)
                sym_options = ["🌐 ALL"] + port_syms
                pf_filter = st.selectbox(
                    "Filter by Stock", sym_options, key="port_stock_filter"
                )

                filtered = port_syms if pf_filter == "🌐 ALL" else [pf_filter]

                filt_names = api.get_company_names(tuple(filtered))
                names_str  = ", ".join(filt_names.values())
                st.caption(f"Fetching news for: {names_str}")
                articles = _fetch_newsapi(filtered)
                _render_news_list(
                    articles,
                    f"No recent news found for {names_str}. Your NewsAPI key may need the Developer plan."
                )

    # ── Tab 2: Watchlist News ─────────────────────────────────────────────────
    with tab_wl:
        if not watchlists:
            st.info("Create a watchlist first to see stock news here.")
        else:
            # Watchlist selector + stock filter — only visible in this tab
            wl_col1, wl_col2 = st.columns(2)
            with wl_col1:
                wl_names = {w["name"]: w["id"] for w in watchlists}
                current_id = st.session_state.get("active_watchlist_id")
                default_ix = 0
                if current_id in wl_names.values():
                    default_ix = list(wl_names.values()).index(current_id)
                sel = st.selectbox(
                    "Watchlist", list(wl_names.keys()),
                    index=default_ix, key="market_wl_selector"
                )
                st.session_state.active_watchlist_id = wl_names[sel]

            active_wl = next((w for w in watchlists if w["id"] == wl_names[sel]), None)
            wl_syms   = active_wl.get("symbols", []) if active_wl else []

            with wl_col2:
                wl_stock_opts = ["🌐 ALL"] + wl_syms
                wl_filter = st.selectbox(
                    "Filter by Stock", wl_stock_opts, key="wl_stock_filter"
                )

            if not wl_syms:
                st.info(f"Watchlist **{sel}** has no stocks yet.")
            else:
                filtered_syms = wl_syms if wl_filter == "🌐 ALL" else (
                    [wl_filter] if wl_filter in wl_syms else wl_syms
                )
                filt_names = api.get_company_names(tuple(filtered_syms))
                names_str  = ", ".join(filt_names.values())
                label = wl_filter if wl_filter != "🌐 ALL" else sel
                st.markdown(f"#### 📰 News for **{label}**")
                st.caption(f"Searching for: {names_str}")
                articles = _fetch_newsapi(filtered_syms)
                _render_news_list(articles, f"No relevant news found for {names_str}.")

    # ── Tab 3: Global Pulse ───────────────────
    with tab_global:
        col_src, col_feed = st.columns([1, 2])
        with col_src:
            st.markdown("#### Sources")
            selected_sources = st.multiselect(
                "Pick channels",
                ["LiveMint Markets", "MoneyControl", "Economic Times", "NDTV Profit", "Business Standard"],
                default=["LiveMint Markets", "Economic Times"]
            )

        with col_feed:
            st.markdown("#### Live Feed")
            rss = _fetch_rss(selected_sources)
            _render_news_list(rss, "No news found. Try selecting different sources.")

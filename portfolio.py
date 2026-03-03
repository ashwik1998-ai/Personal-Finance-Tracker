import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

import database as db
import data_api as api


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def render_score_bar(label, score, max_score=100):
    if score < 33: color = "#ef4444"
    elif score < 66: color = "#f59e0b"
    else: color = "#10b981"
    st.markdown(f"""
        <div style="margin-bottom:1rem;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:0.85rem;font-weight:500;color:#6b7280;">{label}</span>
                <span style="font-size:0.85rem;font-weight:600;color:#1f2937;">{score}/{max_score}</span>
            </div>
            <div style="background-color:#e5e7eb;border-radius:999px;height:8px;">
                <div style="background-color:{color};height:8px;border-radius:999px;width:{min(100,(score/max_score)*100)}%;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Shared CSS (injected once per render)
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
<style>
/* ── Animated metric cards ────────────────────────────────────────────── */
@keyframes fadeUp {
    from { opacity:0; transform:translateY(14px); }
    to   { opacity:1; transform:translateY(0);    }
}
.metric-card {
    background: rgba(15,23,42,0.75);
    border: 1px solid rgba(56,189,248,0.15);
    border-radius: 14px;
    padding: 1.1rem 1.4rem;
    animation: fadeUp 0.45s ease both;
}
.metric-card:nth-child(1){ animation-delay:0.00s; }
.metric-card:nth-child(2){ animation-delay:0.08s; }
.metric-card:nth-child(3){ animation-delay:0.16s; }
.metric-label {
    font-size:0.68rem;font-weight:700;letter-spacing:0.1em;
    color:#64748b;text-transform:uppercase;margin-bottom:0.35rem;
}
.metric-value { font-size:1.35rem;font-weight:800;color:#f1f5f9; }
.metric-value.profit { color:#10b981; }
.metric-value.loss   { color:#ef4444; }

/* ── Holdings HTML table ──────────────────────────────────────────────── */
.h-tbl { width:100%;border-collapse:collapse;margin-top:0.5rem; }
.h-tbl th {
    color:#64748b;font-size:0.68rem;font-weight:700;
    text-transform:uppercase;letter-spacing:0.07em;
    padding:0.55rem 0.7rem;text-align:right;
    border-bottom:1px solid rgba(56,189,248,0.14);
}
.h-tbl th:first-child { text-align:left; }
.h-tbl td {
    padding:0.55rem 0.7rem;color:#cbd5e1;font-size:0.8rem;
    text-align:right;border-bottom:1px solid rgba(56,189,248,0.05);
}
.h-tbl td:first-child { text-align:left; }
.h-tbl tr:hover td { background:rgba(56,189,248,0.04); transition:background 0.2s; }
.sym-name   { font-weight:700;color:#e2e8f0;font-size:0.83rem; }
.badge {
    display:inline-block;padding:0.1rem 0.4rem;border-radius:4px;
    font-size:0.6rem;font-weight:800;letter-spacing:0.08em;
    vertical-align:middle;margin-left:4px;
}
.b-stock { background:rgba(56,189,248,0.18);color:#38bdf8; }
.b-etf   { background:rgba(129,140,248,0.18);color:#818cf8; }
.b-mf    { background:rgba(16,185,129,0.18);color:#10b981;  }
.b-other { background:rgba(100,116,139,0.18);color:#94a3b8; }
.profit  { color:#10b981;font-weight:600; }
.loss    { color:#ef4444;font-weight:600; }
.xirr-na { color:#475569;font-size:0.72rem; }
.xirr-ok { color:#38bdf8;font-weight:600; }
</style>
"""


def _badge(atype: str) -> str:
    cls = {"STOCK": "b-stock", "ETF": "b-etf", "MF": "b-mf"}.get(atype, "b-other")
    return f'<span class="badge {cls}">{atype}</span>'


def _pl_cls(v: float) -> str:
    return "profit" if v > 0 else "loss" if v < 0 else ""


# ─────────────────────────────────────────────────────────────────────────────
# Watchlist panel
# ─────────────────────────────────────────────────────────────────────────────

@st.fragment
def _render_watchlist_panel():
    st.markdown("""
    <div style="
        background:linear-gradient(135deg,rgba(56,189,248,0.08),rgba(129,140,248,0.08));
        border:1px solid rgba(56,189,248,0.2);border-radius:14px;
        padding:0.85rem 1.1rem 0.6rem;margin-bottom:0.75rem;">
        <span style="font-size:0.7rem;font-weight:700;color:#38bdf8;
        text-transform:uppercase;letter-spacing:0.12em;">⭐ Watchlists</span>
    </div>
    """, unsafe_allow_html=True)

    watchlists = db.get_watchlists()
    if "wl_name_counter" not in st.session_state:
        st.session_state["wl_name_counter"] = 0

    with st.expander("➕ New Watchlist", expanded=not watchlists):
        new_name = st.text_input("Name", label_visibility="collapsed",
            key=f"wl_new_{st.session_state['wl_name_counter']}",
            placeholder="Watchlist name, e.g. Tech Picks")
        if st.button("✅ Create", use_container_width=True, key="wl_create_btn", type="primary"):
            if new_name.strip():
                db.create_watchlist(new_name.strip())
                st.session_state["wl_name_counter"] += 1
                st.rerun(scope="fragment")

    if not watchlists:
        st.caption("No watchlists yet.")
        return

    wl_names = [w["name"] for w in watchlists]
    wl_map   = {w["name"]: w for w in watchlists}
    sel_name = st.selectbox("Watchlist", wl_names, key="wl_sel", label_visibility="collapsed")
    active_wl = wl_map[sel_name]
    syms = active_wl.get("symbols", [])

    if st.button("🗑️ Delete this list", use_container_width=True, key="wl_del_list"):
        db.delete_watchlist(active_wl["id"])
        st.rerun(scope="fragment")

    st.divider()
    st.markdown('<p style="font-size:0.72rem;color:#64748b;font-weight:600;margin-bottom:4px;">ADD STOCK TO WATCHLIST</p>', unsafe_allow_html=True)
    search_q = st.text_input("Search stock name", label_visibility="collapsed",
        key="wl_search_q", placeholder="🔍 Search e.g. Tata Power, Infosys…")

    if search_q:
        with st.spinner("Searching…"):
            results = api.search_symbols(search_q)
        if results:
            opts = {f"{r['shortname']}  ({r['symbol']})": r["symbol"] for r in results[:8]}
            chosen_label = st.selectbox("Select stock", list(opts.keys()),
                key="wl_search_result", label_visibility="collapsed")
            selected_sym = opts[chosen_label]
            if st.button(f"➕ Add  {selected_sym}", use_container_width=True,
                key="wl_add_btn", type="primary"):
                if selected_sym not in syms:
                    syms.append(selected_sym)
                    db.update_watchlist_symbols(active_wl["id"], syms)
                    st.rerun(scope="fragment")
        else:
            st.caption("No results. Try a different name.")

    if not syms:
        st.caption("No stocks yet. Add one above.")
        return

    st.markdown('<p style="font-size:0.72rem;color:#64748b;font-weight:600;margin:0.75rem 0 0.3rem;">LIVE PRICES</p>', unsafe_allow_html=True)
    with st.spinner("Fetching prices…"):
        price_data = api.fetch_watchlist_prices(tuple(syms))

    for row in price_data:
        price = row["price"]; chg_p = row["chg_pct"]
        color = "#10b981" if (chg_p or 0) >= 0 else "#ef4444"
        arrow = "▲" if (chg_p or 0) >= 0 else "▼"
        price_str = f"₹{price:,.2f}" if price else "—"
        chg_str   = f"{arrow} {abs(chg_p):.2f}%" if chg_p is not None else "—"
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;
            background:rgba(15,23,42,0.6);border:1px solid rgba(56,189,248,0.1);
            border-radius:10px;padding:0.5rem 0.8rem;margin-bottom:6px;">
            <div style="font-size:0.8rem;font-weight:700;color:#e2e8f0;">{row['symbol']}</div>
            <div style="text-align:right;">
                <div style="font-size:0.82rem;font-weight:700;color:#f1f5f9;">{price_str}</div>
                <div style="font-size:0.7rem;color:{color};font-weight:600;">{chg_str}</div>
            </div>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown('<p style="font-size:0.72rem;color:#64748b;font-weight:600;margin-bottom:4px;">REMOVE STOCK</p>', unsafe_allow_html=True)
    r1, r2 = st.columns([3, 1])
    with r1:
        rm_sym = st.selectbox("remove", ["— select —"] + syms, key="wl_rm_sel", label_visibility="collapsed")
    with r2:
        if st.button("✕", use_container_width=True, key="wl_rm_btn"):
            if rm_sym != "— select —":
                syms.remove(rm_sym)
                db.update_watchlist_symbols(active_wl["id"], syms)
                st.rerun(scope="fragment")


# ─────────────────────────────────────────────────────────────────────────────
# Past Buys tab — per-row Edit/Delete with color coding
# ─────────────────────────────────────────────────────────────────────────────

@st.fragment
def _render_past_buys():
    purchases_df = db.get_all_purchases()

    if purchases_df.empty:
        st.info("No purchase history yet. Add your first holding below.")
        return

    cols_needed = ["id", "symbol", "asset_type", "buy_price", "quantity", "purchase_date"]
    missing = [c for c in cols_needed if c not in purchases_df.columns]
    if missing:
        st.warning(f"Unexpected data format. Missing: {missing}")
        return

    disp = purchases_df[cols_needed].copy()
    disp["invested"] = (disp["buy_price"] * disp["quantity"]).round(2)

    # Fetch current prices for P&L coloring
    all_syms = tuple(disp["symbol"].unique())
    with st.spinner("Fetching live prices…"):
        price_dict = api._batch_fetch_prices(all_syms)

    st.markdown("### 📋 Purchase History")
    st.caption("Edit or delete any buy — the aggregated holding recalculates automatically.")

    if "editing_purchase_id" not in st.session_state:
        st.session_state["editing_purchase_id"] = None

    for idx, row in disp.iterrows():
        pid       = row["id"]
        invested  = row["invested"]
        cur_price = price_dict.get(row["symbol"], 0.0)
        is_editing = st.session_state["editing_purchase_id"] == pid

        # Color the card based on current price vs buy price
        if cur_price > 0:
            if cur_price >= row["buy_price"]:
                card_border = "rgba(16,185,129,0.3)"
                card_bg     = "rgba(16,185,129,0.05)"
            else:
                card_border = "rgba(239,68,68,0.3)"
                card_bg     = "rgba(239,68,68,0.05)"
        else:
            card_border = "rgba(56,189,248,0.12)"
            card_bg     = "rgba(15,23,42,0.6)"

        btn_col, info_col, del_col = st.columns([1.2, 6, 1])

        with btn_col:
            edit_label = "✏️ Close" if is_editing else "✏️ Edit"
            if st.button(edit_label, key=f"edit_btn_{pid}", use_container_width=True):
                st.session_state["editing_purchase_id"] = None if is_editing else pid
                st.rerun(scope="fragment")

        with info_col:
            cur_str = f"LTP ₹{cur_price:,.2f}" if cur_price > 0 else ""
            st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_border};
                border-radius:10px;padding:0.45rem 0.8rem;
                display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap;">
                <span style="font-weight:700;color:#e2e8f0;font-size:0.85rem;min-width:100px;">{row['symbol']}</span>
                <span style="color:#94a3b8;font-size:0.75rem;">{row['asset_type']}</span>
                <span style="color:#f1f5f9;font-size:0.78rem;">Qty: <b>{row['quantity']}</b></span>
                <span style="color:#f1f5f9;font-size:0.78rem;">@ ₹<b>{row['buy_price']:.2f}</b></span>
                <span style="color:#38bdf8;font-size:0.78rem;">= ₹<b>{invested:,.2f}</b></span>
                <span style="color:#64748b;font-size:0.73rem;">{row['purchase_date']}</span>
                <span style="color:#94a3b8;font-size:0.73rem;">{cur_str}</span>
            </div>""", unsafe_allow_html=True)

        with del_col:
            if st.button("🗑️", key=f"del_btn_{pid}", use_container_width=True, help="Delete purchase"):
                db.delete_purchase(pid)
                if st.session_state.get("editing_purchase_id") == pid:
                    st.session_state["editing_purchase_id"] = None
                st.rerun(scope="fragment")

        if is_editing:
            with st.form(f"edit_form_{pid}"):
                ec1, ec2, ec3 = st.columns([2, 2, 2])
                with ec1:
                    new_price = st.number_input("Buy Price (₹)", min_value=0.01,
                        value=float(row["buy_price"]), format="%.2f", step=0.01)
                with ec2:
                    new_qty = st.number_input("Quantity", min_value=0.0001,
                        value=float(row["quantity"]), format="%.4f", step=0.0001)
                with ec3:
                    try:
                        default_date = datetime.strptime(str(row["purchase_date"]), "%Y-%m-%d").date()
                    except Exception:
                        default_date = datetime.now().date()
                    new_date = st.date_input("Purchase Date", value=default_date)
                if st.form_submit_button("💾 Save Changes", use_container_width=True, type="primary"):
                    db.update_purchase(pid, float(new_price), float(new_qty),
                                       new_date.strftime("%Y-%m-%d"))
                    st.session_state["editing_purchase_id"] = None
                    st.success(f"Updated {row['symbol']} ✅")
                    st.rerun(scope="fragment")


# ─────────────────────────────────────────────────────────────────────────────
# Holdings HTML card table
# ─────────────────────────────────────────────────────────────────────────────

def _render_holdings_table(enriched_df: pd.DataFrame, xirr_dict: dict):
    rows_html = ""
    for _, row in enriched_df.iterrows():
        sym      = row["symbol"]
        atype    = row["asset_type"]
        invested = row["avg_price"] * row["quantity"]
        pl       = row["unrealized_pl"]
        pl_pct   = row["unrealized_pl_pct"]
        pl_cls   = _pl_cls(pl)

        xirr_val = xirr_dict.get(sym)
        if xirr_val is None:
            xirr_html = '<span class="xirr-na">N/A</span>'
        else:
            xirr_cls  = "profit" if xirr_val >= 0 else "loss"
            xirr_html = f'<span class="{xirr_cls}">{xirr_val:+.1f}%</span>'

        rows_html += f"""
        <tr>
            <td>
                <span class="sym-name">{sym}</span>{_badge(atype)}
            </td>
            <td>₹{row['avg_price']:,.2f}</td>
            <td>{row['quantity']:,.2f}</td>
            <td>₹{invested:,.2f}</td>
            <td>₹{row['current_price']:,.2f}</td>
            <td>₹{row['current_value']:,.2f}</td>
            <td class="{pl_cls}">₹{pl:+,.2f}</td>
            <td class="{pl_cls}">{pl_pct:+.2f}%</td>
            <td>{xirr_html}</td>
        </tr>"""

    st.markdown(f"""
    <table class="h-tbl">
        <thead><tr>
            <th>Symbol</th>
            <th>Avg Price</th><th>Qty</th><th>Invested</th>
            <th>LTP/NAV</th><th>Curr Value</th>
            <th>P&L</th><th>P&L %</th><th>XIRR p.a.</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Alerts Tab
# ─────────────────────────────────────────────────────────────────────────────

@st.fragment
def render_alerts_tab():
    """Render the Price Alerts management tab."""
    st.markdown("### 🔔 Price Alerts")
    st.caption("Get a Telegram message when any stock hits your target price.")

    # ── Step 1: Telegram setup ────────────────────────────────────────────────
    import os
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    
    with st.expander("⚙️ How to get your Telegram Chat ID — click to expand", expanded=True):
        st.markdown(f"""
**2 quick steps (takes ~1 minute):**

**Step 1 — Start the bot:**
👉 [Click here to open the bot on Telegram](https://t.me/Ashwik_finance_tracker_bot) → tap **Start**

**Step 2 — Find your Chat ID:**
👉 [Click here to get your Chat ID](https://api.telegram.org/bot{token}/getUpdates) → look for `"id"` inside `"from"` → copy that number

Paste the number below. That's it — alerts will be sent to your Telegram. ✅
        """)
        st.info("💡 The same bot works for everyone. Each person uses their own Chat ID so alerts are fully private.")

    # Auto-load saved chat_id from MongoDB on first load
    if "telegram_chat_id" not in st.session_state:
        saved = db.get_user_setting("telegram_chat_id")
        st.session_state["telegram_chat_id"] = saved

    chat_id_input = st.text_input(
        "Your Telegram Chat ID",
        value=st.session_state["telegram_chat_id"],
        placeholder="e.g. 123456789",
        key="tg_chat_id_input"
    )
    if chat_id_input and chat_id_input.strip() != st.session_state["telegram_chat_id"]:
        st.session_state["telegram_chat_id"] = chat_id_input.strip()
        db.save_user_setting("telegram_chat_id", chat_id_input.strip())
        st.success("✅ Chat ID saved — you won't need to enter it again.")

    st.divider()

    # ── Step 2: Create Alert ──────────────────────────────────────────────────
    st.markdown("#### ➕ Set New Alert")

    alert_search = st.text_input("🔍 Search stock", key="alert_search",
                                  placeholder="e.g. Tata Power, Infosys…")
    alert_symbol = ""
    if alert_search:
        with st.spinner("Searching…"):
            results = api.search_symbols(alert_search)
        if results:
            opts = {f"{r['shortname']} ({r['symbol']})": r["symbol"] for r in results[:8]}
            chosen = st.selectbox("Select stock", list(opts.keys()),
                                   key="alert_sym_sel", label_visibility="collapsed")
            alert_symbol = opts[chosen]

    if alert_symbol:
        with st.form("create_alert_form"):
            ac1, ac2 = st.columns(2)
            with ac1:
                target_price = st.number_input("Target Price (₹)", min_value=0.01,
                    value=100.0, format="%.2f", step=0.5)
            with ac2:
                condition = st.selectbox("Alert when price is",
                    ["above", "below"], key="alert_cond")

            st.markdown(
                f'<p style="font-size:0.83rem;color:#38bdf8;">📲 Alert will be sent to Chat ID: '
                f'<b>{st.session_state.get("telegram_chat_id") or "—"}</b></p>',
                unsafe_allow_html=True
            )

            if st.form_submit_button("🔔 Set Alert", use_container_width=True, type="primary"):
                chat_id = st.session_state.get("telegram_chat_id", "").strip()
                if not chat_id:
                    st.error("Please enter your Telegram Chat ID first.")
                elif not alert_symbol:
                    st.error("Please select a stock.")
                else:
                    db.add_alert(alert_symbol, target_price, condition, chat_id)
                    st.success(
                        f"✅ Alert set! You'll get a Telegram message when "
                        f"**{alert_symbol}** goes **{condition}** ₹{target_price:,.2f}"
                    )
                    st.rerun(scope="fragment")

    st.divider()

    # ── Step 3: View / Delete Alerts ─────────────────────────────────────────
    st.markdown("#### 📋 Your Alerts")
    alerts_df = db.get_all_alerts(db.get_current_user_id() or "")

    if alerts_df.empty:
        st.info("No alerts set yet. Search for a stock above to create one.")
        return

    cols_needed = ["id", "symbol", "target_price", "condition",
                   "telegram_chat_id", "active", "triggered_at"]
    missing = [c for c in cols_needed if c not in alerts_df.columns]
    if missing:
        st.warning(f"Unexpected data format: {missing}")
        return

    for _, row in alerts_df[cols_needed].iterrows():
        status_icon  = "🟢 Active" if row["active"] else "✅ Triggered"
        cond_icon    = "📈" if row["condition"] == "above" else "📉"
        triggered_str = ""
        if not row["active"] and row.get("triggered_at"):
            triggered_str = f" · fired {str(row['triggered_at'])[:10]}"

        col_info, col_del = st.columns([6, 1])
        with col_info:
            st.markdown(f"""
            <div style="background:rgba(15,23,42,0.65);border:1px solid rgba(56,189,248,0.12);
                border-radius:10px;padding:0.5rem 0.9rem;display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap;">
                <span style="font-weight:700;color:#e2e8f0;font-size:0.85rem;">{row['symbol']}</span>
                <span style="color:#38bdf8;font-size:0.78rem;">{cond_icon} {row['condition']} ₹{row['target_price']:,.2f}</span>
                <span style="color:#64748b;font-size:0.72rem;">Chat ID: {row['telegram_chat_id']}</span>
                <span style="color:{'#10b981' if row['active'] else '#94a3b8'};font-size:0.72rem;">{status_icon}{triggered_str}</span>
            </div>""", unsafe_allow_html=True)
        with col_del:
            if st.button("🗑️", key=f"del_alert_{row['id']}", use_container_width=True,
                          help="Delete this alert"):
                db.delete_alert(row["id"])
                st.rerun(scope="fragment")


# ─────────────────────────────────────────────────────────────────────────────
# Watchlist Tab (public entry point)
# ─────────────────────────────────────────────────────────────────────────────

def render_watchlist_tab():
    """Public entry point for the standalone Watchlist tab."""
    _render_watchlist_panel()

def render_portfolio_dashboard():
    # Inject shared CSS once
        st.markdown(_CSS, unsafe_allow_html=True)

        st.markdown("""
        <div style="padding:1.5rem 2rem;background:rgba(15,23,42,0.7);
            backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
            border:1px solid rgba(56,189,248,0.15);border-radius:16px;margin-bottom:1.5rem;">
            <div style="font-size:1.5rem;font-weight:700;
                background:linear-gradient(90deg,#38bdf8,#818cf8);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
                📊 Portfolio Dashboard</div>
            <div style="font-size:0.85rem;color:#475569;margin-top:0.3rem;">
                Track your investments in real-time</div>
        </div>
        """, unsafe_allow_html=True)

        tab_holdings, tab_past_buys, tab_add = st.tabs([
            "📦 Holdings", "📋 Past Buys", "➕ Add Holding"
        ])

        # ── Holdings Tab ──────────────────────────────────────────────────────
        with tab_holdings:
            holdings_df = db.get_all_holdings()

            if not holdings_df.empty:
                asset_filter = st.segmented_control(
                    "Filter by Asset Type",
                    options=["All", "Stock", "ETF", "MF"], default="All"
                )
                if asset_filter != "All":
                    holdings_df = holdings_df[holdings_df['asset_type'] == asset_filter.upper()]

            total_inv, curr_val, total_pl, total_pl_pct, enriched_df = api.get_portfolio_metrics(holdings_df)

            # ── Trend chart with NIFTY 50 benchmark ──────────────────────────
            if not enriched_df.empty:
                st.subheader("📈 Portfolio vs NIFTY 50 (1M)")
                with st.spinner("Calculating trend…"):
                    stock_etf = enriched_df[enriched_df["asset_type"].isin(["STOCK", "ETF"])]
                    if not stock_etf.empty:
                        symbols_qty = tuple(
                            (row["symbol"], float(row["quantity"]))
                            for _, row in stock_etf.iterrows()
                        )
                        trend   = api.fetch_portfolio_trend(symbols_qty)
                        nifty   = api.fetch_benchmark_trend()

                        if trend is not None and not trend.empty:
                            # Index both to 100 at first common date
                            trend.index = pd.to_datetime(trend.index).normalize()
                            common = trend.index.intersection(nifty.index) if not nifty.empty else trend.index

                            trend_i = trend.loc[common] / trend.loc[common].iloc[0] * 100 if len(common) > 0 else trend / trend.iloc[0] * 100
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=trend_i.index, y=trend_i.values,
                                name="My Portfolio", line=dict(color="#38bdf8", width=2.5),
                                fill="tozeroy", fillcolor="rgba(56,189,248,0.06)"
                            ))
                            if not nifty.empty:
                                nifty_i = nifty.loc[common] / nifty.loc[common].iloc[0] * 100 if len(common) > 0 else nifty / nifty.iloc[0] * 100
                                fig.add_trace(go.Scatter(
                                    x=nifty_i.index, y=nifty_i.values,
                                    name="NIFTY 50", line=dict(color="#818cf8", width=2, dash="dot")
                                ))
                            fig.update_layout(
                                margin={"t": 30, "b": 0, "l": 0, "r": 0},
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font={"color": "#94a3b8"},
                                xaxis_title="", yaxis_title="Indexed (Base = 100)",
                                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                            xanchor="right", x=1),
                                hovermode="x unified"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Trend data unavailable for current assets.")
                    else:
                        st.info("Trend data unavailable for current assets.")

            # Replace AMFI codes with MF names (AFTER trend chart)
            if not enriched_df.empty:
                mf_mask = enriched_df['asset_type'] == 'MF'
                if mf_mask.any():
                    enriched_df.loc[mf_mask, 'symbol'] = enriched_df.loc[mf_mask, 'symbol'].apply(api.get_mf_name)

            if not enriched_df.empty:
                # ── Animated Metrics ──────────────────────────────────────────
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">CURRENT VALUE</div>
                        <div class="metric-value">₹{curr_val:,.2f}</div>
                    </div>""", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">TOTAL INVESTED</div>
                        <div class="metric-value">₹{total_inv:,.2f}</div>
                    </div>""", unsafe_allow_html=True)
                with m3:
                    p_class = "profit" if total_pl >= 0 else "loss"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">OVERALL P&L</div>
                        <div class="metric-value {p_class}">₹{total_pl:,.2f} ({total_pl_pct:+.2f}%)</div>
                    </div>""", unsafe_allow_html=True)

                st.markdown("---")

                # ── Charts row: allocation + market perf + sector ─────────────
                col_chart1, col_chart2, col_chart3 = st.columns(3)

                with col_chart1:
                    st.subheader("Asset Allocation")
                    fig_pie = px.pie(enriched_df, values='current_value', names='symbol',
                        hole=0.6, color_discrete_sequence=px.colors.qualitative.Prism)
                    fig_pie.update_layout(
                        margin={"t": 30, "b": 0, "l": 0, "r": 0},
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font={"color": "#94a3b8", "size": 11}, showlegend=True,
                        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02,
                                "xanchor": "right", "x": 1}
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col_chart2:
                    st.subheader("Market Performance")
                    fig_bar = px.bar(enriched_df, x='symbol', y='unrealized_pl',
                        color='unrealized_pl',
                        color_continuous_scale=['#ef4444', '#10b981'],
                        labels={'unrealized_pl': 'P&L (₹)'})
                    fig_bar.update_layout(
                        margin={"t": 30, "b": 0, "l": 0, "r": 0},
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font={"color": "#94a3b8"}, coloraxis_showscale=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                with col_chart3:
                    st.subheader("Sector Mix")
                    # Fetch sectors for stocks/ETFs only
                    stock_etf_df = enriched_df[enriched_df["asset_type"].isin(["STOCK", "ETF"])]
                    mf_rows      = enriched_df[enriched_df["asset_type"] == "MF"]
                    sector_data  = []
                    for _, row in stock_etf_df.iterrows():
                        sec = api.fetch_sector(row["symbol"])
                        sector_data.append({"Sector": sec, "Value": row["current_value"]})
                    for _, row in mf_rows.iterrows():
                        sector_data.append({"Sector": "Mutual Fund", "Value": row["current_value"]})

                    if sector_data:
                        sec_df = pd.DataFrame(sector_data).groupby("Sector", as_index=False)["Value"].sum()
                        fig_sec = px.pie(sec_df, values="Value", names="Sector", hole=0.55,
                            color_discrete_sequence=px.colors.qualitative.Set3)
                        fig_sec.update_layout(
                            margin={"t": 30, "b": 0, "l": 0, "r": 0},
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font={"color": "#94a3b8", "size": 11}, showlegend=True,
                            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02,
                                    "xanchor": "right", "x": 1}
                        )
                        st.plotly_chart(fig_sec, use_container_width=True)
                    else:
                        st.info("No sector data")

                # ── Holdings Table ────────────────────────────────────────────
                st.subheader("Your Holdings")

                # Compute XIRR — needs price_dict and purchases
                purchases_df = db.get_all_purchases()
                price_dict   = {row["symbol"]: row["current_price"]
                                for _, row in enriched_df.iterrows()}
                xirr_dict    = api.get_xirr_per_symbol(purchases_df, price_dict)

                # CSV export
                if 'id' in enriched_df.columns:
                    export_df = enriched_df[[
                        'symbol', 'asset_type', 'avg_price', 'quantity',
                        'current_price', 'current_value', 'unrealized_pl', 'unrealized_pl_pct'
                    ]].copy()
                    export_df.insert(4, 'invested',
                        (export_df['avg_price'] * export_df['quantity']).round(2))
                    csv_bytes = export_df.to_csv(index=False).encode()
                    st.download_button(
                        label="⬇️ Export Holdings CSV",
                        data=csv_bytes,
                        file_name="holdings.csv",
                        mime="text/csv",
                        key="export_csv_btn"
                    )

                # Render HTML card table
                _render_holdings_table(enriched_df, xirr_dict)

                st.caption("💡 To remove a holding entirely, delete all its purchases in the **Past Buys** tab.")
            else:
                st.info("Your portfolio is empty. Go to ➕ Add Holding to get started.")

        with tab_past_buys:
            _render_past_buys()

        with tab_add:
            render_add_holding_form()


# ─────────────────────────────────────────────────────────────────────────────
# Add Holding form
# ─────────────────────────────────────────────────────────────────────────────

def render_add_holding_form():
    st.markdown("### ➕ Add New Holding")
    st.caption("Re-adding the same stock records a new buy and **updates the weighted average** automatically.")

    asset_type = st.selectbox("Select Asset Type", ["STOCK", "ETF", "MF"])
    search_query = st.text_input(f"🔍 Search {asset_type} (e.g. Reliance, HDFC)", key="holding_search_input")

    selected_symbol = ""
    if search_query:
        with st.spinner("Searching..."):
            if asset_type == "MF":
                mf_results = api.search_mf(search_query)
                if mf_results:
                    mf_options = {f"MATCH: {r['schemeName']}": str(r['schemeCode']) for r in mf_results[:10]}
                    selected_label = st.selectbox("Step 2: Confirm Selection",
                        options=list(mf_options.keys()), key="holding_search_results")
                    selected_symbol = mf_options[selected_label]
                else:
                    st.warning("No mutual funds found.")
            else:
                stock_results = api.search_symbols(search_query)
                if stock_results:
                    stock_options = {f"MATCH: {r['shortname']} ({r['symbol']})": r['symbol']
                                     for r in stock_results[:10]}
                    selected_label = st.selectbox("Step 2: Confirm Selection",
                        options=list(stock_options.keys()), key="holding_search_results")
                    selected_symbol = stock_options[selected_label]
                else:
                    st.warning("No stocks found.")
    else:
        st.caption("Enter name to see matches here.")

    if selected_symbol:
        st.info(f"Adding Details for: **{selected_symbol}**")
        with st.form("add_holding_details_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                avg_price = st.number_input("Buy Price (₹)", min_value=0.0, value=1.0,
                    format="%.2f", step=0.01)
            with col2:
                quantity = st.number_input("Quantity", min_value=0.0001, value=1.0,
                    format="%.4f", step=0.0001)
            purchase_date = st.date_input("Purchase Date", value=datetime.now())

            invested_preview = avg_price * quantity
            st.markdown(
                f'<p style="font-size:0.85rem;color:#38bdf8;">💰 This buy = <strong>₹{invested_preview:,.2f}</strong> invested</p>',
                unsafe_allow_html=True
            )
            submitted = st.form_submit_button("Finalize: Add to Portfolio", use_container_width=True, type="primary")
            if submitted:
                if avg_price > 0 and quantity > 0:
                    try:
                        date_str = purchase_date.strftime("%Y-%m-%d")
                        db.add_purchase(selected_symbol, asset_type, avg_price, quantity, date_str)
                        st.success(f"✅ Added {selected_symbol}! Holding updated with weighted average.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding holding: {e}")
                else:
                    st.error("Please ensure Price and Quantity are positive.")

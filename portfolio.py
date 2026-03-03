import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

import database as db
import data_api as api

def render_score_bar(label, score, max_score=100):
    """Trendlyne-style linear progress bar for scores."""
    if score < 33: color = "#ef4444"
    elif score < 66: color = "#f59e0b"
    else: color = "#10b981"
    
    st.markdown(f"""
        <div style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-size: 0.85rem; font-weight: 500; color: #6b7280;">{label}</span>
                <span style="font-size: 0.85rem; font-weight: 600; color: #1f2937;">{score}/{max_score}</span>
            </div>
            <div style="background-color: #e5e7eb; border-radius: 999px; height: 8px;">
                <div style="background-color: {color}; height: 8px; border-radius: 999px; width: {min(100, (score/max_score)*100)}%;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

@st.fragment
def _render_watchlist_panel():
    """Isolated watchlist panel (uses @st.fragment to avoid full-page re-renders)."""

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(56,189,248,0.08), rgba(129,140,248,0.08));
        border: 1px solid rgba(56,189,248,0.2);
        border-radius: 14px;
        padding: 0.85rem 1.1rem 0.6rem;
        margin-bottom: 0.75rem;
    ">
        <span style="font-size:0.7rem;font-weight:700;color:#38bdf8;
        text-transform:uppercase;letter-spacing:0.12em;">⭐ Watchlists</span>
    </div>
    """, unsafe_allow_html=True)

    watchlists = db.get_watchlists()

    # ── Create Watchlist ──────────────────────────────────────────────────────
    if "wl_name_counter" not in st.session_state:
        st.session_state["wl_name_counter"] = 0

    with st.expander("➕ New Watchlist", expanded=not watchlists):
        new_name = st.text_input(
            "Name", label_visibility="collapsed",
            key=f"wl_new_{st.session_state['wl_name_counter']}",
            placeholder="Watchlist name, e.g. Tech Picks"
        )
        if st.button("✅ Create", use_container_width=True, key="wl_create_btn", type="primary"):
            if new_name.strip():
                db.create_watchlist(new_name.strip())
                st.session_state["wl_name_counter"] += 1
                st.rerun(scope="fragment")

    if not watchlists:
        st.caption("No watchlists yet.")
        return

    # ── Watchlist Selector ────────────────────────────────────────────────────
    wl_names = [w["name"] for w in watchlists]
    wl_map   = {w["name"]: w for w in watchlists}

    sel_name = st.selectbox(
        "Watchlist", wl_names, key="wl_sel",
        label_visibility="collapsed"
    )
    active_wl = wl_map[sel_name]
    syms = active_wl.get("symbols", [])

    if st.button("🗑️ Delete this list", use_container_width=True, key="wl_del_list"):
        db.delete_watchlist(active_wl["id"])
        st.rerun(scope="fragment")

    st.divider()

    # ── Add Stock (search-then-select) ───────────────────────────────────────
    st.markdown('<p style="font-size:0.72rem;color:#64748b;font-weight:600;margin-bottom:4px;">ADD STOCK TO WATCHLIST</p>', unsafe_allow_html=True)

    search_q = st.text_input("Search stock name", label_visibility="collapsed",
                              key="wl_search_q", placeholder="🔍 Search e.g. Tata Power, Infosys…")

    selected_sym = None
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


    # ── Live Prices Table ─────────────────────────────────────────────────────
    if not syms:
        st.caption("No stocks yet. Add one above.")
        return

    st.markdown('<p style="font-size:0.72rem;color:#64748b;font-weight:600;margin:0.75rem 0 0.3rem;">LIVE PRICES</p>', unsafe_allow_html=True)

    with st.spinner("Fetching prices…"):
        price_data = api.fetch_watchlist_prices(tuple(syms))

    for row in price_data:
        price = row["price"]
        chg_p = row["chg_pct"]
        color = "#10b981" if (chg_p or 0) >= 0 else "#ef4444"
        arrow = "▲" if (chg_p or 0) >= 0 else "▼"
        price_str = f"₹{price:,.2f}" if price else "—"
        chg_str   = f"{arrow} {abs(chg_p):.2f}%" if chg_p is not None else "—"

        st.markdown(f"""
        <div style="
            display:flex; justify-content:space-between; align-items:center;
            background:rgba(15,23,42,0.6);
            border:1px solid rgba(56,189,248,0.1);
            border-radius:10px; padding:0.5rem 0.8rem; margin-bottom:6px;
        ">
            <div>
                <div style="font-size:0.8rem;font-weight:700;color:#e2e8f0;">{row['symbol']}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.82rem;font-weight:700;color:#f1f5f9;">{price_str}</div>
                <div style="font-size:0.7rem;color:{color};font-weight:600;">{chg_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Remove Stock ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown('<p style="font-size:0.72rem;color:#64748b;font-weight:600;margin-bottom:4px;">REMOVE STOCK</p>', unsafe_allow_html=True)
    r1, r2 = st.columns([3, 1])
    with r1:
        rm_sym = st.selectbox("remove", ["— select —"] + syms,
                               key="wl_rm_sel", label_visibility="collapsed")
    with r2:
        if st.button("✕", use_container_width=True, key="wl_rm_btn"):
            if rm_sym != "— select —":
                syms.remove(rm_sym)
                db.update_watchlist_symbols(active_wl["id"], syms)
                st.rerun(scope="fragment")


# ── Past Buys Tab ─────────────────────────────────────────────────────────────

@st.fragment
def _render_past_buys():
    """Render the Past Buys tab — shows every individual purchase with edit/delete."""
    purchases_df = db.get_all_purchases()

    if purchases_df.empty:
        st.info("No purchase history yet. Add your first holding below.")
        return

    # Display columns (keep id for operations)
    cols_needed = ["id", "symbol", "asset_type", "buy_price", "quantity", "purchase_date"]
    missing = [c for c in cols_needed if c not in purchases_df.columns]
    if missing:
        st.warning(f"Unexpected data format. Missing: {missing}")
        return

    disp = purchases_df[cols_needed].copy()
    disp["invested"] = (disp["buy_price"] * disp["quantity"]).round(2)

    st.markdown("### 📋 Purchase History")
    st.caption("Every individual buy you've made. Edit or delete any entry — the aggregated holding is updated automatically.")

    # ── Table view ────────────────────────────────────────────────────────────
    table_df = disp.drop(columns=["id"]).rename(columns={
        "symbol":        "Symbol",
        "asset_type":    "Type",
        "buy_price":     "Buy Price",
        "quantity":      "Qty",
        "purchase_date": "Date",
        "invested":      "Invested",
    })
    st.dataframe(
        table_df.style.format({
            "Buy Price": "₹{:.2f}",
            "Qty":       "{:.4f}",
            "Invested":  "₹{:.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # ── Edit / Delete panel ───────────────────────────────────────────────────
    st.markdown("#### ✏️ Edit or Delete a Purchase")

    # Build a nice label per purchase for the selectbox
    def _label(row):
        return f"{row['symbol']} — {row['quantity']} units @ ₹{row['buy_price']} ({row['purchase_date']})"

    options = {_label(row): row["id"] for _, row in disp.iterrows()}
    selected_label = st.selectbox("Select purchase", list(options.keys()),
                                  label_visibility="collapsed",
                                  key="past_buy_select")
    selected_id = options[selected_label]

    # Get current values for the selected purchase
    sel_row = disp[disp["id"] == selected_id].iloc[0]

    action = st.radio("Action", ["✏️ Edit", "🗑️ Delete"],
                      horizontal=True, key="past_buy_action")

    if action == "✏️ Edit":
        with st.form("edit_purchase_form"):
            ec1, ec2 = st.columns(2)
            with ec1:
                new_price = st.number_input(
                    "Buy Price (₹)", min_value=0.01,
                    value=float(sel_row["buy_price"]),
                    format="%.2f", step=0.01
                )
            with ec2:
                new_qty = st.number_input(
                    "Quantity", min_value=0.0001,
                    value=float(sel_row["quantity"]),
                    format="%.4f", step=0.0001
                )
            try:
                default_date = datetime.strptime(str(sel_row["purchase_date"]), "%Y-%m-%d").date()
            except Exception:
                default_date = datetime.now().date()
            new_date = st.date_input("Purchase Date", value=default_date)

            if st.form_submit_button("💾 Save Changes", use_container_width=True, type="primary"):
                db.update_purchase(
                    selected_id,
                    float(new_price),
                    float(new_qty),
                    new_date.strftime("%Y-%m-%d"),
                )
                st.success(f"Updated {sel_row['symbol']} purchase. Holding recalculated ✅")
                st.rerun(scope="fragment")

    else:  # Delete
        st.warning(
            f"This will permanently remove the purchase of **{sel_row['quantity']} units** "
            f"of **{sel_row['symbol']}** at ₹{sel_row['buy_price']}. "
            f"The aggregated holding will be recalculated (or removed if this was the only buy)."
        )
        if st.button("🗑️ Confirm Delete", type="primary", use_container_width=True,
                     key="confirm_del_purchase"):
            db.delete_purchase(selected_id)
            st.success("Purchase deleted. Holdings updated ✅")
            st.rerun(scope="fragment")


# ── Main Portfolio Dashboard ──────────────────────────────────────────────────

def render_portfolio_dashboard():
    # ── Two-column layout: portfolio left, watchlists right ──────────────────
    col_left, col_right = st.columns([7, 3], gap="large")

    with col_right:
        _render_watchlist_panel()

    with col_left:
        st.markdown("""
        <div style="
            padding: 1.5rem 2rem;
            background: rgba(15,23,42,0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(56,189,248,0.15);
            border-radius: 16px;
            margin-bottom: 1.5rem;
        ">
            <div style="
                font-size: 1.5rem; font-weight: 700;
                background: linear-gradient(90deg, #38bdf8, #818cf8);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
            ">📊 Portfolio Dashboard</div>
            <div style="font-size: 0.85rem; color: #475569; margin-top: 0.3rem;">Track your investments in real-time</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Tabs: Holdings / Past Buys / Add Holding ─────────────────────────
        tab_holdings, tab_past_buys, tab_add = st.tabs([
            "📦 Holdings", "📋 Past Buys", "➕ Add Holding"
        ])

        with tab_holdings:
            holdings_df = db.get_all_holdings()

            # Asset Filter
            if not holdings_df.empty:
                asset_filter = st.segmented_control(
                    "Filter by Asset Type",
                    options=["All", "Stock", "ETF", "MF"],
                    default="All"
                )
                if asset_filter != "All":
                    holdings_df = holdings_df[holdings_df['asset_type'] == asset_filter.upper()]

            total_inv, curr_val, total_pl, total_pl_pct, enriched_df = api.get_portfolio_metrics(holdings_df)

            # Historical Trend — must build symbols_qty BEFORE replacing MF names
            if not enriched_df.empty:
                st.subheader("📈 Portfolio Value Trend (1M)")
                with st.spinner("Calculating trend..."):
                    stock_etf = enriched_df[enriched_df["asset_type"].isin(["STOCK", "ETF"])]
                    if not stock_etf.empty:
                        symbols_qty = tuple(
                            (row["symbol"], float(row["quantity"]))
                            for _, row in stock_etf.iterrows()
                        )
                        trend = api.fetch_portfolio_trend(symbols_qty)
                        if trend is not None and not trend.empty:
                            trend_df = trend.reset_index()
                            trend_df.columns = ["Date", "Value"]
                            fig_trend = px.line(trend_df, x="Date", y="Value",
                                                color_discrete_sequence=["#38bdf8"])
                            fig_trend.update_layout(
                                margin={"t": 30, "b": 0, "l": 0, "r": 0},
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font={"color": "#94a3b8"},
                                xaxis_title="", yaxis_title="Value (₹)", showlegend=False
                            )
                            st.plotly_chart(fig_trend, use_container_width=True)
                        else:
                            st.info("Trend data unavailable for current assets.")
                    else:
                        st.info("Trend data unavailable for current assets.")

            # Replace AMFI codes with MF names (after trend chart)
            if not enriched_df.empty:
                mf_mask = enriched_df['asset_type'] == 'MF'
                if mf_mask.any():
                    enriched_df.loc[mf_mask, 'symbol'] = enriched_df.loc[mf_mask, 'symbol'].apply(api.get_mf_name)

            if not enriched_df.empty:
                # Metrics row
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">CURRENT VALUE</div>
                            <div class="metric-value">₹{curr_val:,.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)
                with m2:
                    st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">TOTAL INVESTMENT</div>
                            <div class="metric-value">₹{total_inv:,.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)
                with m3:
                    p_class = "profit" if total_pl >= 0 else "loss"
                    st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">OVERALL P&L</div>
                            <div class="metric-value {p_class}">₹{total_pl:,.2f} ({total_pl_pct:+.2f}%)</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")

                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.subheader("Asset Allocation")
                    fig_pie = px.pie(enriched_df, values='current_value', names='symbol', hole=0.6,
                                     color_discrete_sequence=px.colors.qualitative.Prism)
                    fig_pie.update_layout(
                        margin={"t": 30, "b": 0, "l": 0, "r": 0},
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font={"color": "#94a3b8", "size": 12}, showlegend=True,
                        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1}
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

                # ── Holdings Table ────────────────────────────────────────────
                st.subheader("Your Holdings")
                if 'id' in enriched_df.columns:
                    display_df = enriched_df[[
                        'id', 'symbol', 'asset_type', 'avg_price', 'quantity',
                        'current_price', 'current_value', 'unrealized_pl', 'unrealized_pl_pct'
                    ]].copy()

                    # ── NEW: Invested column ──────────────────────────────────
                    display_df.insert(
                        display_df.columns.get_loc('current_price'),
                        'invested',
                        (display_df['avg_price'] * display_df['quantity']).round(2)
                    )

                    display_df.columns = [
                        'ID', 'Symbol', 'Type', 'Avg Price', 'Qty',
                        'Invested', 'LTP/NAV', 'Current Value', 'P&L', 'P&L %'
                    ]
                    st.dataframe(
                        display_df.drop(columns=['ID']).style.format({
                            'Avg Price':     '₹{:.2f}',
                            'Qty':           '{:.2f}',
                            'Invested':      '₹{:.2f}',
                            'LTP/NAV':       '₹{:.2f}',
                            'Current Value': '₹{:.2f}',
                            'P&L':           '₹{:.2f}',
                            'P&L %':         '{:.2f}%',
                        }).map(
                            lambda v: 'color: #10b981;' if isinstance(v, (int, float)) and v > 0
                                      else 'color: #ef4444;' if isinstance(v, (int, float)) and v < 0
                                      else '',
                            subset=['P&L', 'P&L %']
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # Delete whole holding (removes all purchases too)
                    with st.expander("🗑️ Delete Entire Holding"):
                        to_delete = st.selectbox(
                            "Select holding to remove:",
                            display_df['ID'].astype(str) + " - " + display_df['Symbol'],
                            key="del_holding_sel"
                        )
                        st.caption("⚠️ This removes the holding AND all its purchase history.")
                        if st.button("Delete", key="del_holding_btn"):
                            holding_id = to_delete.split(" - ")[0]
                            db.delete_holding(holding_id)
                            st.success("Holding and all its purchases deleted!")
                            st.rerun()
            else:
                st.info("Your portfolio is empty. Go to ➕ Add Holding to get started.")

        with tab_past_buys:
            _render_past_buys()

        with tab_add:
            render_add_holding_form()


def render_add_holding_form():
    st.markdown("### ➕ Add New Holding")
    st.caption("If you already hold this stock, a new purchase is recorded and your **weighted average price** is automatically updated.")

    # 1. Search and Result Selection (OUTSIDE FORM for Reactivity)
    asset_type = st.selectbox("Select Asset Type", ["STOCK", "ETF", "MF"])
    search_query = st.text_input(f"🔍 Search {asset_type} (e.g. Reliance, HDFC)", key="holding_search_input")

    selected_symbol = ""
    if search_query:
        with st.spinner("Searching..."):
            if asset_type == "MF":
                mf_results = api.search_mf(search_query)
                if mf_results:
                    mf_options = {f"MATCH: {r['schemeName']}": str(r['schemeCode']) for r in mf_results[:10]}
                    selected_label = st.selectbox("Step 2: Confirm Selection", options=list(mf_options.keys()), key="holding_search_results")
                    selected_symbol = mf_options[selected_label]
                else:
                    st.warning("No mutual funds found.")
            else:
                stock_results = api.search_symbols(search_query)
                if stock_results:
                    stock_options = {f"MATCH: {r['shortname']} ({r['symbol']})": r['symbol'] for r in stock_results[:10]}
                    selected_label = st.selectbox("Step 2: Confirm Selection", options=list(stock_options.keys()), key="holding_search_results")
                    selected_symbol = stock_options[selected_label]
                else:
                    st.warning("No stocks found.")
    else:
        st.caption("Enter name to see matches here.")

    # 2. Add Details form
    if selected_symbol:
        st.info(f"Adding Details for: **{selected_symbol}**")
        with st.form("add_holding_details_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                avg_price = st.number_input("Buy Price (₹)", min_value=0.0, value=1.0, format="%.2f", step=0.01)
            with col2:
                quantity = st.number_input("Quantity", min_value=0.0001, value=1.0, format="%.4f", step=0.0001)

            purchase_date = st.date_input("Purchase Date", value=datetime.now())

            # Show preview of invested amount
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
                        # Use add_purchase — handles averaging automatically
                        db.add_purchase(selected_symbol, asset_type, avg_price, quantity, date_str)
                        st.success(f"✅ Added {selected_symbol}! Holding updated with weighted average.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding holding: {e}")
                else:
                    st.error("Please ensure Price and Quantity are positive.")

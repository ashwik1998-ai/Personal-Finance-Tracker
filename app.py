import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import database as db
import portfolio
import market
import agent
import auth

# --- Page Config ---
st.set_page_config(
    page_title="Financial Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────────────────
#  ZERO-G SPACE THEME  — deep space black  +  cyan/violet neon  +  glassmorphism
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── BASE ── */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif !important;
        color: #e2e8f0;
    }

    /* ── DEEP SPACE BACKGROUND with star dots ── */
    .stApp {
        background-color: #020617 !important;
        background-image:
            radial-gradient(1px 1px at 10% 20%, rgba(255,255,255,0.25) 0%, transparent 100%),
            radial-gradient(1px 1px at 30% 70%, rgba(255,255,255,0.15) 0%, transparent 100%),
            radial-gradient(1px 1px at 50% 30%, rgba(255,255,255,0.2)  0%, transparent 100%),
            radial-gradient(1px 1px at 70% 80%, rgba(255,255,255,0.15) 0%, transparent 100%),
            radial-gradient(1px 1px at 90% 10%, rgba(255,255,255,0.2)  0%, transparent 100%),
            radial-gradient(1px 1px at 15% 55%, rgba(255,255,255,0.1)  0%, transparent 100%),
            radial-gradient(1px 1px at 80% 45%, rgba(255,255,255,0.18) 0%, transparent 100%),
            radial-gradient(1px 1px at 60% 90%, rgba(255,255,255,0.12) 0%, transparent 100%),
            radial-gradient(ellipse 80% 80% at 50% -20%, rgba(56,189,248,0.08) 0%, transparent 60%),
            radial-gradient(ellipse 60% 60% at 80% 110%, rgba(129,140,248,0.06) 0%, transparent 60%) !important;
    }

    /* ── HIDE STREAMLIT CHROME ── */
    [data-testid="stHeader"]         { display: none !important; }
    [data-testid="stDeployButton"]   { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    button[data-testid="stSidebarCollapseButton"] { display: none !important; }
    #MainMenu, footer { visibility: hidden; }

    /* ── SIDEBAR: SPACE GLASS PANEL ── */
    [data-testid="stSidebar"] {
        background: rgba(2, 6, 23, 0.85) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(56, 189, 248, 0.12) !important;
        width: 300px !important;
        min-width: 300px !important;
        transform: none !important;
        visibility: visible !important;
    }
    [data-testid="stMainView"] { margin-left: 300px !important; }

    /* ── SIDEBAR: FORCE WHITE TEXT ── */
    [data-testid="stSidebar"] *:not(button *) { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div   { color: #e2e8f0 !important; }

    /* ── SIDEBAR: BUTTONS ── */
    [data-testid="stSidebar"] button[kind="secondary"] {
        background: rgba(56,189,248,0.08) !important;
        border: 1px solid rgba(56,189,248,0.25) !important;
        color: #e2e8f0 !important;
        border-radius: 9999px !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        background: rgba(56,189,248,0.18) !important;
        border-color: rgba(56,189,248,0.5) !important;
    }
    /* Logout button — red neon ← */
    .logout-btn button {
        background: rgba(239,68,68,0.1) !important;
        border: 1px solid rgba(239,68,68,0.35) !important;
        color: #fca5a5 !important;
        border-radius: 9999px !important;
        font-weight: 600 !important;
    }
    .logout-btn button:hover {
        background: rgba(239,68,68,0.25) !important;
    }

    /* ── SIDEBAR: USER BADGE ── */
    .user-badge {
        background: rgba(56,189,248,0.06);
        border: 1px solid rgba(56,189,248,0.18);
        border-radius: 14px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.8rem;
    }
    .badge-label { font-size:0.65rem; font-weight:700; color:#38bdf8 !important; text-transform:uppercase; letter-spacing:0.12em; }
    .badge-email { font-size:0.82rem; color:#94a3b8 !important; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

    /* ── SIDEBAR: AI CHAT ── */
    [data-testid="stSidebar"] [data-testid="stChatMessage"] {
        background: rgba(15,23,42,0.6) !important;
        border: 1px solid rgba(56,189,248,0.12) !important;
        border-radius: 12px !important;
        margin-bottom: 0.5rem !important;
    }
    [data-testid="stSidebar"] [data-testid="stChatMessage"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #cbd5e1 !important;
        font-size: 0.87rem !important;
        line-height: 1.65 !important;
    }

    /* ── SIDEBAR: INPUTS ── */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        background: rgba(56,189,248,0.05) !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        color: #f1f5f9 !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: rgba(56,189,248,0.05) !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        color: #f1f5f9 !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] hr { border-color: rgba(56,189,248,0.1) !important; margin: 0.75rem 0 !important; }

    /* ── MAIN AREA: GLOBAL TEXT ── */
    .stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp span,.stApp label {
        color: #e2e8f0 !important;
    }

    /* ── GLASSMORPHISM CARDS ── */
    .glass-card {
        background: rgba(15,23,42,0.7);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(56,189,248,0.15);
        border-radius: 16px;
        padding: 1.5rem;
        transition: border-color 0.3s, box-shadow 0.3s;
    }
    .glass-card:hover {
        border-color: rgba(56,189,248,0.35);
        box-shadow: 0 0 24px rgba(56,189,248,0.08);
    }

    /* ── METRIC CARDS ── */
    .metric-card {
        background: rgba(15,23,42,0.8);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(56,189,248,0.12);
        border-radius: 16px;
        padding: 1.4rem;
        margin-bottom: 1rem;
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    .metric-card:hover {
        border-color: rgba(56,189,248,0.35) !important;
        box-shadow: 0 0 30px rgba(56,189,248,0.07);
    }
    .metric-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #38bdf8 !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.4rem;
    }
    .metric-value { font-size: 1.7rem; font-weight: 700; color: #f8fafc !important; }
    .profit { color: #34d399 !important; }
    .loss   { color: #f87171 !important; }

    /* ── PAGE HEADER ── */
    .page-header {
        background: rgba(15,23,42,0.7);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(56,189,248,0.15);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
    }
    .page-header h1 { 
        font-size: 1.5rem !important; font-weight: 700 !important;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        margin: 0 !important;
    }
    .page-header p { color: #64748b !important; margin: 0.3rem 0 0 0 !important; font-size:0.88rem !important; }

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(15,23,42,0.5);
        border: 1px solid rgba(56,189,248,0.1);
        border-radius: 12px;
        padding: 0.25rem;
        gap: 0.2rem;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: #64748b !important;
        font-weight: 500;
        border-radius: 9px;
        padding: 0.5rem 1.2rem;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(56,189,248,0.15) !important;
        color: #38bdf8 !important;
        font-weight: 600 !important;
    }

    /* ── MAIN INPUT FIELDS ── */
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stDateInput"] input {
        background: rgba(15,23,42,0.7) !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        border-radius: 10px !important;
    }
    [data-baseweb="select"] { background: rgba(15,23,42,0.7) !important; }
    [data-baseweb="popover"] *, [role="listbox"] * {
        background: #0f172a !important;
        color: #e2e8f0 !important;
    }
    .stApp label { color: #94a3b8 !important; font-weight: 500 !important; }

    /* ── PRIMARY BUTTONS ── */
    .stButton button[kind="primary"] {
        background: linear-gradient(90deg, #38bdf8, #818cf8) !important;
        border: none !important;
        border-radius: 9999px !important;
        color: #020617 !important;
        font-weight: 700 !important;
        box-shadow: 0 0 20px rgba(56,189,248,0.3);
    }
    .stButton button[kind="primary"]:hover {
        box-shadow: 0 0 35px rgba(56,189,248,0.5) !important;
    }
    .stButton button[kind="secondary"] {
        background: rgba(56,189,248,0.08) !important;
        border: 1px solid rgba(56,189,248,0.3) !important;
        color: #38bdf8 !important;
        border-radius: 9999px !important;
        font-weight: 600 !important;
    }

    /* ── DATAFRAME ── */
    [data-testid="stDataFrame"] {
        background: rgba(15,23,42,0.7) !important;
        border: 1px solid rgba(56,189,248,0.12) !important;
        border-radius: 12px !important;
    }

    /* ── EXPANDER ── */
    [data-testid="stExpander"] {
        background: rgba(15,23,42,0.5) !important;
        border: 1px solid rgba(56,189,248,0.12) !important;
        border-radius: 12px !important;
    }
    [data-testid="stExpander"] summary { color: #94a3b8 !important; }

    /* ── INFO / ALERT BOXES ── */
    [data-testid="stAlert"] {
        background: rgba(56,189,248,0.06) !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        border-radius: 10px !important;
        color: #94a3b8 !important;
    }

    /* ── CHAT INPUT ── */
    [data-testid="stChatInput"] textarea {
        background: rgba(15,23,42,0.8) !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        color: #e2e8f0 !important;
        border-radius: 12px !important;
    }

    /* ── SCROLLBAR ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(2,6,23,0.5); }
    ::-webkit-scrollbar-thumb { background: rgba(56,189,248,0.3); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(56,189,248,0.5); }

    /* ── NO TRANSITION FLASH ── */
    * { transition: none !important; }
    .glass-card, .metric-card, [data-testid="stSidebar"] button,
    .stButton button { transition: border-color 0.25s, box-shadow 0.25s, background 0.25s !important; }
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_watchlist_id" not in st.session_state:
    st.session_state.active_watchlist_id = None

# ─── Auth Gate ────────────────────────────────────────────────────────────────
if "user" not in st.session_state:
    auth.render_login_page()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── Logo / Brand ──────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 0.5rem 0;">
        <div style="font-size:2rem;">🛡️</div>
        <div style="font-size:1rem; font-weight:700;
             background: linear-gradient(90deg, #38bdf8, #818cf8);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent;
             background-clip: text; letter-spacing:0.02em;">
            Financial Guardian
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Logout (top) ──────────────────────────────────
    st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
    if st.button("⏻  Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── User Badge ────────────────────────────────────
    email = db.get_current_user_email() or ""
    st.markdown(f"""
    <div class="user-badge">
        <div class="badge-label">⚡ COMMANDER</div>
        <div class="badge-email">{email}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── AI Guardian Chat ──────────────────────────────
    st.markdown("""
    <div style="font-size:0.8rem; font-weight:700; color:#38bdf8 !important;
         text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.5rem;">
        🤖 Guardian AI
    </div>
    """, unsafe_allow_html=True)

    chat_container = st.container(height=280)
    with chat_container:
        if not st.session_state.messages:
            st.markdown("""
            <div style="text-align:center; padding:1.5rem 0; color:#334155;">
                <div style="font-size:1.5rem; margin-bottom:0.4rem;">🤖</div>
                <div style="font-size:0.8rem;">Ask me anything about your portfolio</div>
            </div>
            """, unsafe_allow_html=True)
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Ask Guardian...", key="sidebar_chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("⟳ Thinking...")
                response = agent.generate_agent_response(prompt, st.session_state.messages[:-1])
                placeholder.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})



# ─────────────────────────────────────────────────────────────────────────────
#  MAIN TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊  Portfolio Dashboard", "📰  Market Intelligence"])

with tab1:
    portfolio.render_portfolio_dashboard()

with tab2:
    market.render_market_intelligence()

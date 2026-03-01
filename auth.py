"""
auth.py – Clerk + Google OAuth authentication with Zero-G space design.
"""

import os
import requests as _requests
import streamlit as st
from dotenv import load_dotenv, find_dotenv
from requests_oauthlib import OAuth2Session

load_dotenv(find_dotenv(), override=True)

# ── Clerk helpers ─────────────────────────────────────────────────────────────

def _sk() -> str:
    return os.environ.get("CLERK_SECRET_KEY", "")

def _clerk_headers() -> dict:
    return {"Authorization": f"Bearer {_sk()}", "Content-Type": "application/json"}

# ── Google OAuth helpers ───────────────────────────────────────────────────────

GOOGLE_AUTH_URL      = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL     = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPES               = ["openid", "https://www.googleapis.com/auth/userinfo.email",
                         "https://www.googleapis.com/auth/userinfo.profile"]

def _google_client_id():
    return os.environ.get("GOOGLE_CLIENT_ID", "")

def _google_client_secret():
    return os.environ.get("GOOGLE_CLIENT_SECRET", "")

def _redirect_uri():
    return os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8502")

def _google_login_url() -> str:
    oauth = OAuth2Session(_google_client_id(), redirect_uri=_redirect_uri(), scope=SCOPES)
    auth_url, state = oauth.authorization_url(GOOGLE_AUTH_URL, access_type="offline", prompt="select_account")
    st.session_state["oauth_state"] = state
    return auth_url

def _handle_google_callback(code: str) -> dict | None:
    try:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        oauth = OAuth2Session(_google_client_id(), redirect_uri=_redirect_uri(), scope=SCOPES)
        oauth.fetch_token(GOOGLE_TOKEN_URL, code=code, client_secret=_google_client_secret())
        info = oauth.get(GOOGLE_USERINFO_URL).json()
        return {"id": f"google_{info['sub']}", "email": info["email"],
                "name": info.get("name", ""), "provider": "google"}
    except Exception as e:
        st.error(f"Google sign-in error: {e}")
        return None

# ── Clerk FAPI helpers ────────────────────────────────────────────────────────

def _fapi_base() -> str:
    import base64
    pk = os.environ.get("CLERK_PUBLISHABLE_KEY", "")
    prefix = "pk_test_" if "test" in pk else "pk_live_"
    encoded = pk[len(prefix):]
    try:
        host = base64.b64decode(encoded.rstrip("$") + "==").decode().rstrip("$")
        return f"https://{host}"
    except Exception:
        return "https://clerk.accounts.dev"

def _sign_in(email: str, password: str) -> tuple[dict | None, str | None]:
    pk  = os.environ.get("CLERK_PUBLISHABLE_KEY", "")
    hdr = {"Content-Type": "application/json", "Authorization": f"Bearer {pk}"}
    base = _fapi_base()
    r1 = _requests.post(f"{base}/v1/client/sign_ins", json={"identifier": email}, headers=hdr, timeout=10)
    if r1.status_code not in (200, 201):
        return None, r1.json().get("errors", [{}])[0].get("long_message", "Sign-in failed.")
    sid = r1.json()["response"]["id"]
    r2  = _requests.post(f"{base}/v1/client/sign_ins/{sid}/attempt_first_factor",
                          json={"strategy": "password", "password": password}, headers=hdr, timeout=10)
    data = r2.json()
    if r2.status_code not in (200, 201):
        return None, data.get("errors", [{}])[0].get("long_message", "Invalid credentials.")
    resp = data.get("response", {})
    if resp.get("status") != "complete":
        return None, "Sign-in incomplete. Please verify your email first."
    return {"id": resp.get("created_user_id", ""), "email": email, "provider": "clerk"}, None

def _sign_up(email: str, password: str) -> tuple[dict | None, str | None]:
    r = _requests.post("https://api.clerk.com/v1/users",
                        json={"email_address": [email], "password": password, "skip_password_checks": False},
                        headers=_clerk_headers(), timeout=10)
    data = r.json()
    if r.status_code not in (200, 201):
        errs = data.get("errors", [])
        return None, errs[0].get("long_message", "Sign-up failed.") if errs else str(data)
    return {"id": data["id"],
            "email": data["email_addresses"][0]["email_address"] if data.get("email_addresses") else email,
            "provider": "clerk"}, None

# ── LOGIN PAGE ────────────────────────────────────────────────────────────────

def render_login_page():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

        /* ── DEEP SPACE BACKGROUND ── */
        .stApp {
            background-color: #020617 !important;
            background-image:
                radial-gradient(1px 1px at 10% 20%, rgba(255,255,255,0.2) 0%, transparent 100%),
                radial-gradient(1px 1px at 30% 70%, rgba(255,255,255,0.15) 0%, transparent 100%),
                radial-gradient(1px 1px at 55% 35%, rgba(255,255,255,0.18) 0%, transparent 100%),
                radial-gradient(1px 1px at 75% 85%, rgba(255,255,255,0.12) 0%, transparent 100%),
                radial-gradient(1px 1px at 90% 15%, rgba(255,255,255,0.2)  0%, transparent 100%),
                radial-gradient(1px 1px at 40% 60%, rgba(255,255,255,0.1)  0%, transparent 100%),
                radial-gradient(1px 1px at 65% 45%, rgba(255,255,255,0.15) 0%, transparent 100%),
                radial-gradient(ellipse 70% 70% at 50% -10%, rgba(56,189,248,0.1) 0%, transparent 60%),
                radial-gradient(ellipse 50% 50% at 90% 110%, rgba(129,140,248,0.07) 0%, transparent 60%) !important;
        }
        section[data-testid="stMain"] > div { padding-top: 2rem !important; }
        .stApp h1, .stApp h2, .stApp p, .stApp span, .stApp label { color: #e2e8f0 !important; }

        /* ── LOGIN CARD ── */
        .login-card {
            background: rgba(15,23,42,0.75);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(56,189,248,0.18);
            border-radius: 20px;
            padding: 2.5rem;
            box-shadow: 0 0 60px rgba(56,189,248,0.05), 0 0 120px rgba(129,140,248,0.03);
        }

        /* ── INPUTS ── */
        .stTextInput input {
            background: rgba(56,189,248,0.05) !important;
            border: 1px solid rgba(56,189,248,0.2) !important;
            color: #f1f5f9 !important;
            border-radius: 12px !important;
        }
        .stTextInput input:focus {
            border-color: rgba(56,189,248,0.5) !important;
            box-shadow: 0 0 0 3px rgba(56,189,248,0.08) !important;
        }
        .stTextInput label, .stRadio label { color: #64748b !important; font-size: 0.85rem !important; }
        .stForm { border: none !important; background: transparent !important; padding: 0 !important; }

        /* ── PRIMARY BUTTON ── */
        .stButton button[kind="primary"] {
            background: linear-gradient(90deg, #38bdf8, #818cf8) !important;
            border: none !important; border-radius: 9999px !important;
            color: #020617 !important; font-weight: 700 !important;
            box-shadow: 0 0 20px rgba(56,189,248,0.35) !important;
        }
        .stButton button[kind="primary"]:hover {
            box-shadow: 0 0 40px rgba(56,189,248,0.55) !important;
        }

        /* ── GOOGLE BUTTON ── */
        .google-btn {
            display: flex; align-items: center; justify-content: center; gap: 10px;
            background: rgba(255,255,255,0.08);
            color: #e2e8f0;
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 9999px;
            padding: 0.65rem 1.2rem;
            font-size: 0.9rem; font-weight: 600;
            text-decoration: none; width: 100%; cursor: pointer;
        }
        .google-btn:hover {
            background: rgba(255,255,255,0.14) !important;
            border-color: rgba(255,255,255,0.3) !important;
            color: #ffffff !important;
        }

        /* ── DIVIDER ── */
        .divider { display:flex; align-items:center; gap:0.8rem; margin:1rem 0; }
        .divider-line { flex:1; height:1px; background:rgba(56,189,248,0.12); }
        .divider-text { font-size:0.75rem; color:#334155; white-space:nowrap; }

        /* ── RADIO ── */
        [data-testid="stRadio"] > div > label { color: #64748b !important; }
        [data-testid="stRadio"] [data-checked="true"] label { color: #38bdf8 !important; }

        /* ── ALERT BOXES ── */
        [data-testid="stAlert"] {
            background: rgba(56,189,248,0.05) !important;
            border: 1px solid rgba(56,189,248,0.2) !important;
            border-radius: 10px !important; color: #94a3b8 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Handle Google OAuth callback
    params = st.query_params
    if "code" in params and "user" not in st.session_state:
        code = params["code"]
        with st.spinner("Completing Google sign-in..."):
            user = _handle_google_callback(code)
        if user:
            st.session_state["user"] = user
            st.query_params.clear()
            st.rerun()
        else:
            st.query_params.clear()

    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        # Brand hero
        st.markdown("""
        <div style="text-align:center; margin-bottom:2rem;">
            <div style="font-size:3rem; margin-bottom:0.5rem; filter: drop-shadow(0 0 20px rgba(56,189,248,0.5));">🛡️</div>
            <div style="font-size:1.8rem; font-weight:800; letter-spacing:-0.02em;
                 background:linear-gradient(90deg,#38bdf8,#818cf8);
                 -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">
                Financial Guardian
            </div>
            <div style="font-size:0.85rem; color:#475569; margin-top:0.4rem;">
                Your personal AI investment dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Google Sign-in button
        if _google_client_id():
            google_url = _google_login_url()
            st.markdown(f"""
            <a href="{google_url}" class="google-btn" target="_self">
                <svg width="18" height="18" viewBox="0 0 48 48">
                    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                </svg>
                Continue with Google
            </a>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="text-align:center; font-size:0.75rem; color:#334155; padding: 0.5rem 0;">
                ⚙️ Add GOOGLE_CLIENT_ID to .env to enable Google sign-in
            </div>
            """, unsafe_allow_html=True)

        # OR divider
        st.markdown("""
        <div class="divider">
            <div class="divider-line"></div>
            <div class="divider-text">or continue with email</div>
            <div class="divider-line"></div>
        </div>
        """, unsafe_allow_html=True)

        mode = st.radio("", ["Login", "Sign Up"], horizontal=True, label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)

        if mode == "Login":
            with st.form("login_form"):
                email    = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign In →", use_container_width=True, type="primary")
                if submitted:
                    if email and password:
                        with st.spinner("Signing in..."):
                            user, err = _sign_in(email, password)
                        if user:
                            st.session_state["user"] = user
                            st.rerun()
                        else:
                            st.error(f"❌ {err}")
                    else:
                        st.warning("Please enter both fields.")
        else:
            with st.form("signup_form"):
                email    = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password (min 8 chars)", type="password", placeholder="••••••••")
                confirm  = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Create Account →", use_container_width=True, type="primary")
                if submitted:
                    if not email or not password:
                        st.warning("Please fill in all fields.")
                    elif password != confirm:
                        st.error("❌ Passwords do not match.")
                    elif len(password) < 8:
                        st.error("❌ Minimum 8 characters required.")
                    else:
                        with st.spinner("Creating your account..."):
                            user, err = _sign_up(email, password)
                        if user:
                            st.session_state["user"] = user
                            st.rerun()
                        else:
                            st.error(f"❌ {err}")

        st.markdown("""
        <p style="text-align:center; font-size:0.7rem; color:#1e293b; margin-top:1.5rem;">
            Secured by Clerk Authentication · Powered by MongoDB
        </p>
        """, unsafe_allow_html=True)

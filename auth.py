"""Accounts for HVTracker: GitHub/Google OAuth + signed-cookie sessions,
a server-side tracked-projects list, and in-app notifications.

Self-contained APIRouter; app.py does `import auth; app.include_router(auth.router)`.
Design notes:
- Sessions are stateless signed cookies (stdlib hmac — no extra dependency).
- The whole site stays public; these endpoints are purely additive.
- Minimal OAuth scopes only: GitHub `read:user user:email`, Google `openid email profile`.
- A dev-login stub (HVT_DEV_AUTH=1, non-production only) lets you click through the
  full flow locally without registering OAuth apps. It is hard-disabled in prod.
- Everything degrades gracefully: no DATABASE_URL -> 503; no OAuth client id ->
  a clear message (or dev-login when enabled).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
from html import escape

import requests
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import db

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", BASE_DIR)

SESSION_COOKIE = "hvt_session"
STATE_COOKIE = "hvt_oauth_state"
SESSION_TTL = 60 * 60 * 24 * 30  # 30 days
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

SECRET = (os.environ.get("HVT_SESSION_SECRET")
          or os.environ.get("SECRET_KEY")
          or "dev-insecure-secret-change-me")
IS_PROD = (os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"
           or os.environ.get("HVT_ENV", "").lower() == "production")
# Dev-login is double-gated: explicit opt-in AND never in production.
DEV_AUTH = os.environ.get("HVT_DEV_AUTH") == "1" and not IS_PROD

GITHUB_CLIENT_ID = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
BASE_URL = os.environ.get("HVT_BASE_URL", "")  # e.g. https://hvtracker.net


# ---------------------------------------------------------------- signing ---

def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def _unsign(token: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    expected = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        return None


def _set_session(resp: Response, user_id: int) -> None:
    token = _sign({"uid": int(user_id), "exp": int(time.time()) + SESSION_TTL})
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL, httponly=True,
                    samesite="lax", secure=IS_PROD, path="/")


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    data = _unsign(token) if token else None
    if not data or int(data.get("exp", 0)) < time.time():
        return None
    if not db.enabled():
        return None
    return db.get_user(int(data["uid"]))


def _base_url(request: Request) -> str:
    if BASE_URL:
        return BASE_URL.rstrip("/")
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (request.headers.get("x-forwarded-host")
            or request.headers.get("host") or request.url.netloc)
    return f"{scheme}://{host}"


def _safe_next(raw: str | None) -> str:
    """Only allow same-site relative redirects."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return "/"


# --------------------------------------------------- email/password auth ----

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LOGIN_ERRORS = {
    "email": "Enter a valid email address.",
    "weak": "Password must be at least 8 characters.",
    "exists": "An account with that email already exists — try signing in.",
    "badcreds": "Email or password is incorrect.",
    "unavailable": "Accounts aren't available right now.",
}


def _hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return "pbkdf2$200000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def _verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = (stored or "").split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


# -------------------------------------------------------- agents index -----

def _agents_index() -> dict:
    """slug -> agent row, from the rendered latest.json on the volume."""
    path = os.path.join(OUTPUT_DIR, "data", "latest.json")
    try:
        with open(path) as f:
            agents = json.load(f).get("agents", [])
    except (OSError, json.JSONDecodeError):
        return {}
    return {a.get("slug"): a for a in agents if a.get("slug")}


# ------------------------------------------------------------- providers ---

_PROVIDERS = {
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "scope": "read:user user:email",
    },
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "openid email profile",
    },
}


def _client(provider: str) -> tuple[str, str]:
    if provider == "github":
        return GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
    if provider == "google":
        return GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    return "", ""


@router.get("/auth/{provider}/login")
def oauth_login(provider: str, request: Request, next: str = "/"):
    if provider not in _PROVIDERS:
        return JSONResponse({"error": "unknown_provider"}, status_code=404)
    client_id, _ = _client(provider)
    nxt = _safe_next(next)
    if not client_id:
        if DEV_AUTH:
            return RedirectResponse(f"/auth/dev-login?next={urllib.parse.quote(nxt)}", status_code=302)
        return HTMLResponse(
            f"<p>{provider.title()} sign-in isn't configured yet "
            f"(missing OAuth client id). Set the {provider.upper()}_OAUTH_CLIENT_ID / "
            f"_SECRET env vars, or run locally with HVT_DEV_AUTH=1 for the dev stub.</p>",
            status_code=503,
        )
    state = secrets.token_urlsafe(24)
    redirect_uri = f"{_base_url(request)}/auth/{provider}/callback"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": _PROVIDERS[provider]["scope"],
        "state": state,
    }
    if provider == "google":
        params["response_type"] = "code"
        params["access_type"] = "online"
    url = _PROVIDERS[provider]["authorize"] + "?" + urllib.parse.urlencode(params)
    resp = RedirectResponse(url, status_code=302)
    # Sign the state + the post-login destination into a short-lived cookie (CSRF).
    resp.set_cookie(STATE_COOKIE, _sign({"s": state, "n": nxt, "p": provider,
                                         "exp": int(time.time()) + 600}),
                    max_age=600, httponly=True, samesite="lax", secure=IS_PROD, path="/")
    return resp


@router.get("/auth/{provider}/callback")
def oauth_callback(provider: str, request: Request, code: str = "", state: str = ""):
    if provider not in _PROVIDERS:
        return JSONResponse({"error": "unknown_provider"}, status_code=404)
    saved = _unsign(request.cookies.get(STATE_COOKIE) or "")
    if (not saved or saved.get("p") != provider or not state
            or not hmac.compare_digest(saved.get("s", ""), state)
            or int(saved.get("exp", 0)) < time.time()):
        return HTMLResponse("<p>Sign-in state mismatch — please try again.</p>", status_code=400)
    client_id, client_secret = _client(provider)
    redirect_uri = f"{_base_url(request)}/auth/{provider}/callback"
    try:
        tok = requests.post(
            _PROVIDERS[provider]["token"],
            data={"client_id": client_id, "client_secret": client_secret, "code": code,
                  "redirect_uri": redirect_uri, "grant_type": "authorization_code"},
            headers={"Accept": "application/json"}, timeout=15,
        ).json()
        access = tok.get("access_token")
        if not access:
            return HTMLResponse("<p>Could not complete sign-in (no token).</p>", status_code=400)
        profile = _fetch_profile(provider, access)
    except Exception:
        return HTMLResponse("<p>Sign-in failed talking to the provider. Try again.</p>", status_code=502)
    if not profile:
        return HTMLResponse("<p>Could not read your profile from the provider.</p>", status_code=400)
    user = db.upsert_user(**profile)
    nxt = _safe_next(saved.get("n"))
    resp = RedirectResponse(nxt, status_code=302)
    resp.delete_cookie(STATE_COOKIE, path="/")
    if user:
        _set_session(resp, user["id"])
    return resp


def _fetch_profile(provider: str, access: str) -> dict | None:
    h = {"Authorization": f"Bearer {access}", "Accept": "application/json"}
    if provider == "github":
        u = requests.get("https://api.github.com/user", headers=h, timeout=15).json()
        if not u.get("id"):
            return None
        email = u.get("email")
        if not email:
            try:
                emails = requests.get("https://api.github.com/user/emails", headers=h, timeout=15).json()
                primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
                email = (primary or {}).get("email") if primary else None
            except Exception:
                email = None
        return {"provider": "github", "provider_id": str(u["id"]), "login": u.get("login"),
                "name": u.get("name") or u.get("login"), "email": email, "avatar_url": u.get("avatar_url")}
    if provider == "google":
        u = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=h, timeout=15).json()
        if not u.get("sub"):
            return None
        return {"provider": "google", "provider_id": str(u["sub"]),
                "login": (u.get("email") or "").split("@")[0] or None,
                "name": u.get("name"), "email": u.get("email"), "avatar_url": u.get("picture")}
    return None


@router.get("/auth/dev-login")
def dev_login(request: Request, login: str = "devuser", next: str = "/"):
    """Local-only stub so the flow is previewable without OAuth apps."""
    if not DEV_AUTH:
        return JSONResponse({"error": "dev_login_disabled"}, status_code=404)
    if not db.enabled():
        return JSONResponse({"error": "database_required"}, status_code=503)
    safe = "".join(c for c in login if c.isalnum() or c in "-_")[:39] or "devuser"
    user = db.upsert_user(provider="dev", provider_id=safe, login=safe,
                          name=f"{safe} (dev)", email=f"{safe}@dev.local",
                          avatar_url=f"https://avatars.githubusercontent.com/{safe}")
    resp = RedirectResponse(_safe_next(next), status_code=302)
    if user:
        _set_session(resp, user["id"])
    return resp


@router.post("/auth/logout")
def logout(next: str = Form("/")):
    # 303 so a form POST (account page) and a fetch (header menu) both end on a GET.
    resp = RedirectResponse(_safe_next(next), status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.post("/auth/signup")
def signup(email: str = Form(""), password: str = Form(""), next: str = Form("/")):
    if not db.enabled():
        return RedirectResponse("/login?error=unavailable", status_code=303)
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return RedirectResponse(f"/login?error=email&next={urllib.parse.quote(_safe_next(next))}", status_code=303)
    if len(password) < 8:
        return RedirectResponse(f"/login?error=weak&next={urllib.parse.quote(_safe_next(next))}", status_code=303)
    if db.get_password_user(email):
        return RedirectResponse(f"/login?error=exists&next={urllib.parse.quote(_safe_next(next))}", status_code=303)
    user = db.create_password_user(email, _hash_password(password))
    if not user:
        return RedirectResponse("/login?error=exists", status_code=303)
    resp = RedirectResponse(_safe_next(next), status_code=303)
    _set_session(resp, user["id"])
    return resp


@router.post("/auth/login")
def password_login(email: str = Form(""), password: str = Form(""), next: str = Form("/")):
    if not db.enabled():
        return RedirectResponse("/login?error=unavailable", status_code=303)
    email = (email or "").strip().lower()
    user = db.get_password_user(email)
    if not user or not _verify_password(password, user.get("password_hash") or ""):
        return RedirectResponse(f"/login?error=badcreds&next={urllib.parse.quote(_safe_next(next))}", status_code=303)
    resp = RedirectResponse(_safe_next(next), status_code=303)
    _set_session(resp, user["id"])
    return resp


# ----------------------------------------------------------- auth pages ----

_GH_ICON = ('<svg class="auth-ic" width="18" height="18" viewBox="0 0 16 16" fill="currentColor" '
            'aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 '
            '0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63'
            '-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 '
            '0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 2-.27c.68 0 1.36.09 '
            '2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 '
            '3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8z">'
            '</path></svg>')
_GOOGLE_ICON = ('<svg class="auth-ic" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">'
                '<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 '
                '2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/><path fill="#34A853" d="M9 18c2.43 0 4.47-.8 '
                '5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>'
                '<path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 '
                '9c0 1.45.35 2.82.96 4.05l3.01-2.33z"/><path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 '
                '1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/></svg>')


def _provider_buttons(next_path: str) -> str:
    nxt = urllib.parse.quote(_safe_next(next_path))
    out = []
    if GITHUB_CLIENT_ID:
        out.append(f'<a class="auth-btn auth-btn--github" href="/auth/github/login?next={nxt}">{_GH_ICON}Continue with GitHub</a>')
    if GOOGLE_CLIENT_ID:
        out.append(f'<a class="auth-btn auth-btn--google" href="/auth/google/login?next={nxt}">{_GOOGLE_ICON}Continue with Google</a>')
    if DEV_AUTH:
        out.append(f'<a class="auth-btn auth-btn--dev" href="/auth/dev-login?next={nxt}">Dev login (local)</a>')
    if not out:
        return '<p class="auth-note">Sign-in isn\'t configured on this instance yet.</p>'
    return '<div class="auth-providers">' + "".join(out) + "</div>"


@router.get("/login", response_class=HTMLResponse)
@router.get("/login/", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, next: str = "/", error: str = ""):
    from app import _marketing_page  # lazy: avoids circular import at module load
    if current_user(request):
        return RedirectResponse(_safe_next(next) if next != "/" else "/account/", status_code=302)
    nxt = escape(_safe_next(next))
    err_html = (f'<p class="auth-error">{escape(_LOGIN_ERRORS[error])}</p>'
                if error in _LOGIN_ERRORS else "")
    email_form = (
        '<div class="auth-divider"><span>or with email</span></div>'
        '<form class="auth-form" method="post" action="/auth/login">'
        f'<input type="hidden" name="next" value="{nxt}">'
        '<label class="auth-field">Email'
        '<input type="email" name="email" required autocomplete="email" placeholder="you@example.com"></label>'
        '<label class="auth-field">Password'
        '<input type="password" name="password" required minlength="8" autocomplete="current-password" placeholder="at least 8 characters"></label>'
        '<div class="auth-form-actions">'
        '<button class="auth-btn auth-btn--primary" type="submit" formaction="/auth/login">Sign in</button>'
        '<button class="auth-btn auth-btn--ghost" type="submit" formaction="/auth/signup">Create account</button>'
        '</div></form>'
    )
    body = (
        '<div class="auth-card">'
        '<p class="auth-lede">Create a free account to track agents and get notified '
        'when their trust signals move.</p>'
        + err_html
        + _provider_buttons(next)
        + email_form +
        '<p class="auth-fineprint">We only use your email to sign you in and (if you opt in) send '
        'trust alerts. The registry stays free and fully public either way.</p>'
        "</div>"
    )
    return HTMLResponse(_marketing_page(
        "Sign in — HVTracker", "Account", "Sign in or create an account", body,
        description="Sign in to HVTracker to track agents and get trust-change alerts.",
        path="/login/", noindex=True))


def _watch_view(slug: str, agent: dict | None) -> dict:
    """Normalize one tracked slug into the fields the account page renders.

    A slug with no row in latest.json is a delisted/retired project the user is
    still tracking — it stays in the list (their record of it is real) but is
    marked so the missing numbers read as "gone", not as zeros.
    """
    a = agent or {}
    listed = bool(a)
    delta = a.get("rank_delta")
    return {
        "slug": slug,
        "name": a.get("name") or slug,
        "listed": listed,
        "category": a.get("category") or "",
        "trust_score": a.get("trust_score"),
        "grade": a.get("evidence_grade"),
        "coverage_grade": a.get("coverage_grade"),
        "rank": a.get("rank"),
        # rank_delta is `previous_rank - rank`, so positive means moved UP.
        "rank_delta": delta,
        # days_ago is 999 for rows whose first signal fetch hasn't run yet;
        # rendering that as "pushed 999d ago" beside a 0.0 score reads as a
        # dead project rather than an unscored one.
        "days_ago": a.get("days_ago"),
        "pending": bool(a.get("pending_signals")),
        "needs_review": bool(a.get("has_warning")),
    }


def watchlist_summary_html(watch: list[str], index: dict) -> str:
    """Portfolio strip: size, average trust, movement, and anything flagged."""
    if not watch:
        return ""
    views = [_watch_view(s, index.get(s)) for s in watch]
    # Pending rows carry a placeholder 0.0 until their first scan — averaging
    # that in would understate the portfolio.
    listed = [v for v in views if v["listed"] and not v["pending"]]
    scores = [v["trust_score"] for v in listed if v["trust_score"] is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    up = sum(1 for v in listed if (v["rank_delta"] or 0) > 0)
    down = sum(1 for v in listed if (v["rank_delta"] or 0) < 0)
    flagged = sum(1 for v in listed if v["needs_review"])

    if up or down:
        moved = f'<span class="wl-up">&#9650;{up}</span> <span class="wl-down">&#9660;{down}</span>'
        moved_label = "moved since yesterday"
    else:
        moved = '<span class="wl-flat">&mdash;</span>'
        moved_label = "no rank moves"

    cells = [
        (str(len(watch)), "tracked"),
        (f"{avg}" if avg is not None else "&mdash;", "average trust"),
        (moved, moved_label),
        (str(flagged) if flagged else "0", "need review"),
    ]
    return ('<div class="wl-summary">' + "".join(
        f'<div class="wl-cell"><div class="wl-val">{v}</div><div class="wl-lab">{escape(lab)}</div></div>'
        for v, lab in cells) + "</div>")


def watchlist_html(watch: list[str], index: dict) -> str:
    """The tracked-projects list, richest-first by rank."""
    if not watch:
        return ('<p class="auth-note">No projects yet &mdash; open any agent and choose '
                "<em>Track</em> to follow its score, rank and supply-chain signals here.</p>")

    views = [_watch_view(s, index.get(s)) for s in watch]
    # Listed agents first, best rank first; delisted sink to the bottom.
    views.sort(key=lambda v: (not v["listed"], v["rank"] if v["rank"] is not None else 10**6))

    items = []
    for v in views:
        slug = escape(v["slug"])
        name = escape(v["name"])
        if not v["listed"]:
            items.append(
                f'<li class="wl-row is-gone" data-watch-slug="{slug}">'
                f'<div class="wl-main"><span class="wl-name">{name}</span>'
                f'<span class="wl-sub">No longer listed</span></div>'
                f'<button type="button" class="account-remove" data-remove-slug="{slug}">Remove</button></li>')
            continue

        if v["pending"]:
            items.append(
                f'<li class="wl-row is-pending" data-watch-slug="{slug}">'
                f'<div class="wl-main"><a class="wl-name" href="/agents/{slug}/">{name}</a>'
                f'<span class="wl-sub">Awaiting first signal scan</span></div>'
                f'<div class="wl-score">&mdash;</div><div class="wl-rank">&mdash;</div>'
                f'<button type="button" class="account-remove" data-remove-slug="{slug}">Remove</button></li>')
            continue

        grade = v["grade"]
        chip = (f'<span class="evidence-badge grade-{escape(str(grade))}" '
                f'title="Evidence grade {escape(str(grade))}">{escape(str(grade))}</span>') if grade else ""
        score = f'{v["trust_score"]}' if v["trust_score"] is not None else "&mdash;"

        d = v["rank_delta"]
        if d is None:
            trend = '<span class="wl-trend wl-new">new</span>'
        elif d > 0:
            trend = f'<span class="wl-trend wl-up" title="Up {d} since yesterday">&#9650;{d}</span>'
        elif d < 0:
            trend = f'<span class="wl-trend wl-down" title="Down {abs(d)} since yesterday">&#9660;{abs(d)}</span>'
        else:
            trend = '<span class="wl-trend wl-flat" title="No rank change">&mdash;</span>'

        rank = f'#{v["rank"]}' if v["rank"] is not None else "&mdash;"
        bits = []
        if v["category"]:
            bits.append(escape(v["category"]))
        if v["coverage_grade"]:
            bits.append(f'coverage {escape(str(v["coverage_grade"]))}')
        if v["days_ago"] is not None:
            bits.append(f'pushed {v["days_ago"]}d ago')
        sub = " &middot; ".join(bits)
        flag = '<span class="wl-flag" title="Listed, but flagged for review">needs review</span>' if v["needs_review"] else ""

        items.append(
            f'<li class="wl-row" data-watch-slug="{slug}">'
            f'<div class="wl-main">'
            f'<a class="wl-name" href="/agents/{slug}/">{name}</a>'
            f'<span class="wl-sub">{sub}</span></div>'
            f'<div class="wl-score">{score}{chip}</div>'
            f'<div class="wl-rank">{rank} {trend}</div>'
            f'{flag}'
            f'<button type="button" class="account-remove" data-remove-slug="{slug}">Remove</button></li>')

    return '<ul class="account-list wl-list">' + "".join(items) + "</ul>"


@router.get("/account", response_class=HTMLResponse)
@router.get("/account/", response_class=HTMLResponse, include_in_schema=False)
def account_page(request: Request):
    from app import _marketing_page
    user = current_user(request)
    if not user:
        return RedirectResponse("/login?next=/account/", status_code=302)
    index = _agents_index()

    watch = db.list_watch(user["id"])
    watch_html = watchlist_html(watch, index)
    summary_html = watchlist_summary_html(watch, index)

    avatar = f'<img class="account-avatar" src="{escape(user.get("avatar_url") or "")}" alt="">' if user.get("avatar_url") else ""
    ident = escape(user.get("name") or user.get("login") or "Account")
    sub = " · ".join(filter(None, [
        ("@" + user["login"]) if user.get("login") else None,
        user.get("email"),
        f"via {escape(user.get('provider',''))}" if user.get("provider") else None,
    ]))
    body = (
        '<div class="account">'
        f'<div class="account-head">{avatar}<div class="account-id"><strong>{ident}</strong>'
        f'<span class="account-muted">{escape(sub)}</span></div>'
        '<form method="post" action="/auth/logout" class="account-signout">'
        '<input type="hidden" name="next" value="/"><button class="auth-btn auth-btn--ghost" type="submit">Sign out</button></form>'
        "</div>"
        f'<h3 id="watchlist">Tracked projects <span class="account-count">{len(watch)}</span></h3>'
        f'{summary_html}{watch_html}'
        "</div>"
    )
    return HTMLResponse(_marketing_page(
        "Your account — HVTracker", "Account", "Your account", body,
        description="Your HVTracker account: tracked projects and settings.",
        path="/account/"))


# ------------------------------------------------------------------- api ---

@router.get("/api/me")
def api_me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({
            "logged_in": False,
            "providers": [p for p, ok in (("github", GITHUB_CLIENT_ID), ("google", GOOGLE_CLIENT_ID)) if ok],
            "dev_login": DEV_AUTH,
        })
    return JSONResponse({"logged_in": True, "user": {
        "login": user.get("login"), "name": user.get("name"), "avatar_url": user.get("avatar_url"),
    }})


@router.get("/api/watchlist")
def api_watchlist(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    return JSONResponse({"slugs": db.list_watch(user["id"])})


@router.post("/api/watchlist")
async def api_watchlist_post(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    body = await request.json()
    action = body.get("action")
    if action == "add" and body.get("slug"):
        db.add_watch(user["id"], str(body["slug"])[:160])
    elif action == "remove" and body.get("slug"):
        db.remove_watch(user["id"], str(body["slug"])[:160])
    elif action == "sync" and isinstance(body.get("slugs"), list):
        # One-time merge of an anonymous localStorage watchlist into the account.
        for slug in body["slugs"][:500]:
            db.add_watch(user["id"], str(slug)[:160])
    return JSONResponse({"slugs": db.list_watch(user["id"])})


@router.get("/api/notifications")
def api_notifications(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    slugs = set(db.list_watch(user["id"]))
    index = _agents_index()
    last_read = db.get_last_read(user["id"]) or "0000-00-00"
    items, unread = [], 0
    for slug in slugs:
        row = index.get(slug)
        if not row:
            continue
        for ev in (row.get("recent_events") or []):
            date = ev.get("date") or ""
            is_unread = date > last_read[:10]
            unread += 1 if is_unread else 0
            items.append({
                "slug": slug, "name": row.get("name", slug), "date": date,
                "label": ev.get("label"), "detail": ev.get("detail"),
                "tone": ev.get("tone", "neutral"), "unread": is_unread,
            })
    items.sort(key=lambda x: x["date"], reverse=True)
    return JSONResponse({"unread": unread, "items": items[:50],
                         "watching": len(slugs)})


@router.post("/api/notifications/read")
def api_notifications_read(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "auth_required"}, status_code=401)
    db.set_last_read(user["id"])
    return JSONResponse({"ok": True})

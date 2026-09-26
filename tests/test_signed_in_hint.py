"""auth.js only asks /api/me when the browser has a session.

Every page view used to call /api/me: an uncached origin request (1,077 in
48 h) for a site where nearly every visitor is anonymous. A readable
`hvt_signed_in` hint now travels with the HttpOnly session, so everyone else
gets the Sign in link with no round trip."""
import os

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

import auth

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER = {"id": 7, "login": "maintainer", "name": "M", "avatar_url": None}


def _client(monkeypatch, user):
    monkeypatch.setattr(auth, "current_user", lambda request: user)
    a = FastAPI()
    a.include_router(auth.router)
    return TestClient(a)


def _cookies(resp):
    h = resp.headers  # starlette: getlist; httpx (TestClient): get_list
    return list(h.getlist("set-cookie") if hasattr(h, "getlist") else h.get_list("set-cookie"))


def test_session_and_hint_are_set_together_and_only_the_session_is_httponly():
    resp = Response()
    auth._set_session(resp, 7)
    session = next(c for c in _cookies(resp) if c.startswith(auth.SESSION_COOKIE + "="))
    hint = next(c for c in _cookies(resp) if c.startswith("hvt_signed_in=1"))
    assert "httponly" in session.lower() and "httponly" not in hint.lower()


def test_me_refreshes_the_hint_for_a_session_and_clears_a_stale_one(monkeypatch):
    signed_in = _client(monkeypatch, USER).get("/api/me")
    assert signed_in.json()["logged_in"] is True
    assert any(c.startswith("hvt_signed_in=1") for c in _cookies(signed_in))
    expired = _client(monkeypatch, None).get("/api/me", cookies={"hvt_signed_in": "1"})
    assert expired.json()["logged_in"] is False
    assert any(c.startswith("hvt_signed_in=") and "max-age=0" in c.lower() for c in _cookies(expired))


def test_logout_clears_both(monkeypatch):
    r = _client(monkeypatch, USER).post("/auth/logout", data={"next": "/"}, follow_redirects=False)
    cleared = " ".join(_cookies(r)).lower()
    assert r.status_code == 303 and auth.SESSION_COOKIE in cleared and "hvt_signed_in" in cleared


def test_existing_sessions_pick_up_the_hint_from_sign_in(monkeypatch):
    r = _client(monkeypatch, USER).get("/login?next=/agents/haystack/", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/agents/haystack/"
    assert any(c.startswith("hvt_signed_in=1") for c in _cookies(r))


def test_auth_js_asks_only_with_the_hint():
    js = open(os.path.join(ROOT, "auth.js"), encoding="utf-8").read()
    gate = js.index("hvt_signed_in=1")
    first_me = js.index('api("/api/me")')
    assert gate < first_me and js.count('api("/api/me")') == 1

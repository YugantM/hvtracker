"""Watchlist alert emails (alerts.py, mailer.py, the /account opt-in).

No Postgres: the db accessors and the mail provider are stubbed. The SQL
itself was exercised against a real Postgres when this landed (see the PR).
"""
import time
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import alerts
import auth
import mailer

TODAY = "2026-10-08"


def _ev(day, kind, detail):
    return {"date": day, "type": kind, "detail": detail, "label": kind}


ROWS = [{"repo": "org/x", "slug": "x", "name": "X"}, {"repo": "org/y", "slug": "y", "name": "Y"}]


# ---- which changes are emailed --------------------------------------------

def test_only_finished_days_in_the_lookback_window():
    events = {"org/x": [
        _ev("2026-10-08", "grade_changed", "Trust grade B → C"),   # today: can still be rewritten
        _ev("2026-10-07", "grade_changed", "Trust grade A → B"),
        _ev("2026-10-05", "trust_score_changed", "HVTrust down 4.0pts (70.0 → 66.0)"),
        _ev("2026-10-04", "grade_changed", "Trust grade B → A"),   # older than the lookback
    ]}
    got = alerts.finalized_changes(events, ROWS, TODAY)
    assert [c["date"] for c in got["x"]] == ["2026-10-07", "2026-10-05"]


def test_rank_and_churn_events_stay_in_the_bell():
    events = {"org/x": [_ev("2026-10-07", k, k) for k in
                        ("rank_changed", "score_changed", "license_changed", "scorecard_added")]}
    assert alerts.finalized_changes(events, ROWS, TODAY) == {}


def test_delisted_project_resolves_through_history_rows():
    events = {"org/gone": [_ev("2026-10-07", "delisted", "Removed from active tracking")]}
    rows = ROWS + [{"repo": "Org/Gone", "slug": "gone", "name": "Gone"}]
    got = alerts.finalized_changes(events, rows, TODAY)
    assert got["gone"][0]["kind"] == "delisted" and got["gone"][0]["name"] == "Gone"


def test_change_sig_is_stable_and_specific():
    a = {"slug": "x", "kind": "grade_changed", "date": "2026-10-07", "detail": "Trust grade A → B"}
    assert alerts.change_sig(a) == alerts.change_sig(dict(a))
    assert alerts.change_sig(a) != alerts.change_sig({**a, "date": "2026-10-06"})


def test_queue_skips_changes_from_before_watching_or_opting_in(monkeypatch):
    changes = {"x": [{"slug": "x", "name": "X", "kind": "grade_changed", "date": d, "detail": d}
                     for d in ("2026-10-05", "2026-10-07")]}
    monkeypatch.setattr(alerts.db, "alert_subscribers_for",
                        lambda slugs: [{"user_id": 1, "slug": "x", "since": date(2026, 10, 6)}])
    queued = []
    monkeypatch.setattr(alerts.db, "add_alert_events", lambda rows: queued.extend(rows) or len(rows))
    assert alerts.queue_alerts(changes) == 1
    assert queued[0]["date"] == "2026-10-07" and queued[0]["user_id"] == 1 and queued[0]["change_sig"]


# ---- cadence ---------------------------------------------------------------

NOW = datetime(2026, 10, 8, 0, 5, tzinfo=timezone.utc)


def test_daily_sends_at_most_about_once_a_day():
    assert alerts.is_due({"cadence": "daily", "last_sent_at": None}, NOW)
    assert not alerts.is_due({"cadence": "daily", "last_sent_at": NOW - timedelta(hours=8)}, NOW)
    assert alerts.is_due({"cadence": "daily", "last_sent_at": NOW - timedelta(hours=23, minutes=58)}, NOW)


def test_weekly_counts_from_the_last_digest_or_opt_in():
    fresh = {"cadence": "weekly", "last_sent_at": None, "verified_at": NOW - timedelta(days=2)}
    assert not alerts.is_due(fresh, NOW)
    assert alerts.is_due({**fresh, "verified_at": NOW - timedelta(days=7)}, NOW)
    assert not alerts.is_due({**fresh, "last_sent_at": NOW - timedelta(days=3)}, NOW)


# ---- digest ----------------------------------------------------------------

def _events(*specs):
    return [{"id": i + 1, "slug": s, "name": n, "kind": k, "date": "2026-10-07", "detail": d}
            for i, (s, n, k, d) in enumerate(specs)]


def test_digest_subject_and_links():
    one = _events(("x", "X", "grade_changed", "Trust grade A → B"))
    subject, text, html = alerts.render_digest(one, "https://hvtracker.net/unsub/T")
    assert subject == "X: Trust grade A → B"
    assert "https://hvtracker.net/agents/x/?utm_source=hvtracker" in text
    assert "Unsubscribe: https://hvtracker.net/unsub/T" in text and "/unsub/T" in html
    two = _events(("x", "X", "grade_changed", "a"), ("gone", "Gone", "delisted", "Removed"))
    subject, text, _ = alerts.render_digest(two, "u")
    assert subject == "2 projects you track changed"
    assert "https://hvtracker.net/account/?utm" in text   # a delisted profile 410s


def test_digest_escapes_html():
    evs = _events(("x", "<b>X</b>", "grade_changed", "<script>alert(1)</script>"))
    _, _, html = alerts.render_digest(evs, "u")
    assert "<script>" not in html and "&lt;script&gt;" in html and "<b>X</b>" not in html


def test_send_marks_rows_only_when_the_provider_accepts(monkeypatch):
    digest = {"user_id": 3, "email": "a@example.com", "cadence": "daily", "last_sent_at": None,
              "verified_at": None, "events": _events(("x", "X", "grade_changed", "A → B"),
                                                      ("x", "X", "provenance_removed", "gone"))}
    monkeypatch.setattr(alerts.db, "pending_alert_digests", lambda: [digest])
    marked, sends = [], []
    monkeypatch.setattr(alerts.db, "mark_alerts_emailed", lambda uid, ids: marked.append((uid, ids)))

    def fake_send(to, subject, text, html, **kw):
        sends.append((to, kw))
        return accept

    monkeypatch.setattr(alerts.mailer, "send", fake_send)
    accept = False
    assert alerts.send_pending(NOW) == 0 and marked == []
    accept = True
    assert alerts.send_pending(NOW) == 1 and marked == [(3, [1, 2])]
    # The same rows retried after a failure share an idempotency key.
    assert sends[0][1]["idempotency_key"] == sends[1][1]["idempotency_key"] == "hvt-digest-3-2"
    assert "/unsub/" in sends[1][1]["unsub_url"]


def test_disabled_pipeline_touches_nothing(monkeypatch):
    monkeypatch.delenv("ALERTS_ENABLED", raising=False)
    monkeypatch.setattr(alerts.db, "alert_subscribers_for", lambda s: pytest.fail("db touched"))
    assert alerts.run({"org/x": [_ev("2026-10-07", "grade_changed", "A → B")]}, ROWS, TODAY) is None


# ---- tokens ------------------------------------------------------------------

def test_tokens_are_signed_and_purpose_bound():
    unsub = alerts.make_token(7, "unsub")
    assert alerts.read_token(unsub, "unsub")["u"] == 7
    assert alerts.read_token(unsub, "verify") is None
    raw, sig = unsub.rsplit(".", 1)
    assert alerts.read_token(raw + "." + ("0" * len(sig)), "unsub") is None


def test_verify_token_is_bound_to_the_address_and_expires(monkeypatch):
    payload = alerts.read_token(alerts.make_token(7, "verify", "Dev@Example.com"), "verify")
    assert alerts.email_matches(payload, "dev@example.com")
    assert not alerts.email_matches(payload, "other@example.com")
    later = time.time() + alerts.VERIFY_TTL + 5
    token = alerts.make_token(7, "verify", "dev@example.com")
    monkeypatch.setattr(alerts.time, "time", lambda: later)
    assert alerts.read_token(token, "verify") is None


# ---- mailer ------------------------------------------------------------------

def test_mailer_sends_nothing_without_a_key(monkeypatch):
    monkeypatch.setattr(mailer, "API_KEY", "")
    monkeypatch.setattr(mailer, "DEV_OUTBOX", False)
    monkeypatch.setattr(mailer.requests, "post", lambda *a, **k: pytest.fail("network"))
    assert not mailer.configured()
    assert mailer.send("a@example.com", "s", "t", "<p>t</p>") is False


def test_mailer_sets_one_click_unsubscribe_and_idempotency(monkeypatch):
    seen = {}

    class R:
        status_code = 200
        text = '{"id":"x"}'

    def post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, body=json)
        return R()

    monkeypatch.setattr(mailer, "API_KEY", "re_test")
    monkeypatch.setattr(mailer.requests, "post", post)
    assert mailer.send("a@example.com", "s", "t", "h", unsub_url="https://h/unsub/T", idempotency_key="k1")
    assert seen["headers"]["Idempotency-Key"] == "k1"
    assert seen["body"]["headers"] == {"List-Unsubscribe": "<https://h/unsub/T>",
                                       "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


# ---- web: /account opt-in, verify, unsubscribe ------------------------------

USER = {"id": 5, "login": "u", "email": "u@example.com", "alert_email": None, "alert_cadence": "daily"}


@pytest.fixture
def web(monkeypatch):
    calls = []
    state = {"user": dict(USER), "claim": True, "send": True}
    monkeypatch.setattr(auth, "current_user", lambda request: state["user"])
    monkeypatch.setattr(auth, "_agents_index", lambda: {})
    monkeypatch.setattr(alerts, "enabled", lambda: True)
    monkeypatch.setattr(auth.db, "list_watch", lambda uid: [])
    monkeypatch.setattr(auth.db, "get_last_read", lambda uid: None)
    monkeypatch.setattr(auth.db, "set_last_read", lambda uid: None)
    monkeypatch.setattr(auth.db, "get_user", lambda uid: state["user"] if uid == 5 else None)
    monkeypatch.setattr(auth.db, "claim_alert_verify_send", lambda uid: state["claim"])
    monkeypatch.setattr(auth.db, "set_alert_cadence", lambda uid, c: calls.append(("cadence", uid, c)))
    monkeypatch.setattr(auth.db, "confirm_alert_email", lambda uid, e: calls.append(("confirm", uid, e)))
    monkeypatch.setattr(alerts, "send_verification", lambda uid, e: calls.append(("verify", uid, e)) or state["send"])
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app), calls, state


def test_account_offers_opt_in_only_while_enabled(web, monkeypatch):
    client, _, _ = web
    assert "Email me at u@example.com" in client.get("/account/").text
    monkeypatch.setattr(alerts, "enabled", lambda: False)
    assert 'id="alerts"' not in client.get("/account/").text


def test_opt_in_sends_a_confirmation_and_is_throttled(web):
    client, calls, state = web
    r = client.post("/account/alerts", data={"action": "enable"}, follow_redirects=False)
    assert r.headers["location"] == "/account/?alerts=sent#alerts"
    assert calls == [("verify", 5, "u@example.com")]
    state["claim"] = False
    r = client.post("/account/alerts", data={"action": "enable"}, follow_redirects=False)
    assert r.headers["location"] == "/account/?alerts=wait#alerts" and len(calls) == 1


def test_cadence_needs_a_confirmed_address_and_a_known_value(web):
    client, calls, state = web
    client.post("/account/alerts", data={"action": "cadence", "cadence": "weekly"})
    assert calls == []                                  # not opted in yet
    state["user"] = {**USER, "alert_email": "u@example.com"}
    client.post("/account/alerts", data={"action": "cadence", "cadence": "hourly"})
    client.post("/account/alerts", data={"action": "cadence", "cadence": "weekly"})
    assert calls == [("cadence", 5, "weekly")]
    assert 'value="weekly"' in client.get("/account/").text


def test_verify_link_shows_a_button_and_confirms_on_post(web):
    client, calls, state = web
    token = alerts.make_token(5, "verify", "u@example.com")
    page = client.get(f"/verify-email/{token}")
    assert page.status_code == 200 and "<form method='post'>" in page.text and calls == []
    assert client.post(f"/verify-email/{token}").status_code == 200
    assert calls == [("confirm", 5, "u@example.com")]
    # The account's email changed since the link was sent: no.
    state["user"] = {**USER, "email": "new@example.com"}
    assert client.post(f"/verify-email/{token}").status_code == 400
    assert client.get("/verify-email/garbage").status_code == 400


def test_unsubscribe_needs_a_post_and_turns_alerts_off(web):
    client, calls, _ = web
    token = alerts.make_token(5, "unsub")
    assert "Unsubscribe</button>" in client.get(f"/unsub/{token}").text and calls == []
    # Gmail/Yahoo one-click sends exactly this body.
    r = client.post(f"/unsub/{token}", content="List-Unsubscribe=One-Click",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200 and calls == [("cadence", 5, "off")]
    assert client.post("/unsub/nope.0000").status_code == 400

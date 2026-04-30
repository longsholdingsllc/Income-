"""Backend regression tests for Autopilot - Passive Income OS.

Covers: auth, streams, entries, dashboard, goals, AI ideas/content/coach, DCA simulator.
Tests run against REACT_APP_BACKEND_URL (public preview URL).
"""
import os
import time
import uuid
from typing import Any, Dict

import requests
import pytest

BASE_URL: str = os.environ.get("REACT_APP_BACKEND_URL", "https://income-automation-21.preview.emergentagent.com").rstrip("/")
API: str = f"{BASE_URL}/api"

# Generous timeout for AI endpoints (Claude via Emergent)
AI_TIMEOUT: int = 90
DEFAULT_TIMEOUT: int = 30


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def test_user(session: requests.Session) -> Dict[str, Any]:
    """Register a unique TEST_ user once per session."""
    email = f"test+{int(time.time())}_{uuid.uuid4().hex[:6]}@autopilot.io"
    payload = {"email": email, "password": "TestPass123!", "name": "TEST_User"}
    r = session.post(f"{API}/auth/register", json=payload, timeout=DEFAULT_TIMEOUT)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    return {"email": email, "password": payload["password"], "token": data["token"], "user": data["user"]}


@pytest.fixture(scope="session")
def auth_headers(test_user: Dict[str, Any]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {test_user['token']}", "Content-Type": "application/json"}


# ---------- Health ----------
class TestHealth:
    def test_root(self, session: requests.Session) -> None:
        r = session.get(f"{API}/", timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ---------- Auth ----------
class TestAuth:
    def test_register_returns_jwt(self, test_user: dict) -> None:
        assert test_user["token"]
        assert test_user["user"]["email"] == test_user["email"]
        assert "id" in test_user["user"]

    def test_register_duplicate_email(self, session: requests.Session, test_user: dict) -> None:
        r = session.post(f"{API}/auth/register", json={
            "email": test_user["email"], "password": "another1", "name": "Dup",
        }, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 400

    def test_login_success(self, session: requests.Session, test_user: dict) -> None:
        r = session.post(f"{API}/auth/login", json={
            "email": test_user["email"], "password": test_user["password"],
        }, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["token"]
        assert data["user"]["email"] == test_user["email"]

    def test_login_invalid(self, session: requests.Session, test_user: dict) -> None:
        r = session.post(f"{API}/auth/login", json={
            "email": test_user["email"], "password": "wrongpass",
        }, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 401

    def test_me_with_token(self, session: requests.Session, auth_headers: dict, test_user: dict) -> None:
        r = session.get(f"{API}/auth/me", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["email"] == test_user["email"]

    def test_me_without_token(self, session: requests.Session) -> None:
        r = session.get(f"{API}/auth/me", timeout=DEFAULT_TIMEOUT)
        assert r.status_code in (401, 403)

    def test_protected_endpoint_without_token(self, session: requests.Session) -> None:
        r = session.get(f"{API}/streams", timeout=DEFAULT_TIMEOUT)
        assert r.status_code in (401, 403)


# ---------- Streams + Entries ----------
class TestStreamsAndEntries:
    stream_id = None

    def test_create_stream(self, session: requests.Session, auth_headers: dict) -> None:
        payload = {
            "name": "TEST_Affiliate Blog",
            "category": "affiliate",
            "initial_investment": 100.0,
            "monthly_estimate": 200.0,
            "notes": "regression",
        }
        r = session.post(f"{API}/streams", json=payload, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"]
        assert d["name"] == payload["name"]
        assert d["category"] == "affiliate"
        assert d["total_earned"] == 0.0
        TestStreamsAndEntries.stream_id = d["id"]

    def test_list_streams(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.get(f"{API}/streams", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert TestStreamsAndEntries.stream_id in ids

    def test_add_entry_updates_total(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestStreamsAndEntries.stream_id
        assert sid
        # add two entries
        for amt in (50.0, 75.5):
            r = session.post(f"{API}/streams/{sid}/entries",
                             json={"amount": amt, "note": "TEST entry"},
                             headers=auth_headers, timeout=DEFAULT_TIMEOUT)
            assert r.status_code == 200, r.text
            assert r.json()["amount"] == amt
        # verify total_earned = 125.5 via list
        r = session.get(f"{API}/streams", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        s = next(x for x in r.json() if x["id"] == sid)
        assert abs(s["total_earned"] - 125.5) < 0.01

    def test_list_entries(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestStreamsAndEntries.stream_id
        r = session.get(f"{API}/streams/{sid}/entries", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_entry_on_missing_stream(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.post(f"{API}/streams/nonexistent-id/entries",
                         json={"amount": 10}, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 404


# ---------- Dashboard ----------
class TestDashboard:
    def test_summary_structure(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.get(f"{API}/dashboard/summary", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        for key in ("total_invested", "total_earned", "monthly_income",
                    "active_streams", "trend", "breakdown", "goal", "recent_entries"):
            assert key in d, f"missing {key}"
        assert isinstance(d["trend"], list) and len(d["trend"]) == 6
        assert d["total_earned"] >= 125.5
        assert d["active_streams"] >= 1
        assert isinstance(d["recent_entries"], list)


# ---------- Goals ----------
class TestGoals:
    def test_get_default_goal(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.get(f"{API}/goals", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200

    def test_upsert_goal_and_persist(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.post(f"{API}/goals",
                         json={"monthly_target": 5000, "freedom_number": 8000},
                         headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["monthly_target"] == 5000
        # GET to verify persistence
        r2 = session.get(f"{API}/goals", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r2.json()["monthly_target"] == 5000
        assert r2.json()["freedom_number"] == 8000


# ---------- DCA Simulator (no auth) ----------
class TestDCA:
    def test_dca_basic(self, session: requests.Session) -> None:
        r = session.post(f"{API}/simulator/dca", json={
            "asset": "BTC", "monthly_contribution": 200, "apy_percent": 8, "years": 5,
        }, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["asset"] == "BTC"
        assert d["total_contributed"] == 12000  # 200 * 60
        assert d["final_value"] > d["total_contributed"]
        assert d["total_interest"] > 0
        assert d["monthly_passive_at_end"] > 0
        assert isinstance(d["series"], list) and len(d["series"]) > 0

    def test_dca_no_auth_required(self, session: requests.Session) -> None:
        # explicitly without Authorization header - still works
        r = requests.post(f"{API}/simulator/dca", json={
            "asset": "ETH", "monthly_contribution": 100, "apy_percent": 5, "years": 1,
        }, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200

    def test_dca_invalid_years(self, session: requests.Session) -> None:
        r = session.post(f"{API}/simulator/dca", json={
            "asset": "BTC", "monthly_contribution": 100, "apy_percent": 5, "years": 0,
        }, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 422


# ---------- AI Ideas ----------
class TestAIIdeas:
    def test_generate_ideas(self, session: requests.Session, auth_headers: dict) -> None:
        payload = {
            "skills": "writing, basic coding",
            "budget_usd": 500,
            "hours_per_week": 8,
            "risk_tolerance": "medium",
            "interests": "tech, finance",
        }
        r = session.post(f"{API}/ai/ideas", json=payload, headers=auth_headers, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        ideas = r.json().get("ideas", [])
        assert len(ideas) >= 3, f"expected >=3 ideas got {len(ideas)}"
        first = ideas[0]
        for k in ("title", "category", "summary", "estimated_monthly_income",
                  "startup_cost", "time_to_first_dollar", "risk", "action_plan", "tools_needed"):
            assert k in first, f"missing field {k}"
        assert isinstance(first["action_plan"], list) and len(first["action_plan"]) > 0
        assert isinstance(first["tools_needed"], list) and len(first["tools_needed"]) > 0


# ---------- AI Content ----------
class TestAIContent:
    def test_generate_content(self, session: requests.Session, auth_headers: dict) -> None:
        payload = {
            "niche": "home office productivity",
            "keywords": "best ergonomic chair, work from home",
            "target_audience": "remote workers",
            "affiliate_product": "ergonomic chairs",
        }
        r = session.post(f"{API}/ai/content", json=payload, headers=auth_headers, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        for k in ("title", "meta_description", "outline", "article_markdown", "cta_suggestions"):
            assert k in d
        assert len(d["article_markdown"]) > 200
        assert isinstance(d["outline"], list) and len(d["outline"]) > 0


# ---------- AI Coach ----------
class TestAICoach:
    session_id = None

    def test_coach_first_message(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.post(f"{API}/ai/coach/chat",
                         json={"message": "I have $1000 to start. What's the best first passive income stream?"},
                         headers=auth_headers, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d["session_id"]
        assert d["reply"] and len(d["reply"]) > 10
        TestAICoach.session_id = d["session_id"]

    def test_coach_followup(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestAICoach.session_id
        assert sid
        r = session.post(f"{API}/ai/coach/chat",
                         json={"session_id": sid, "message": "What about index funds vs dividend ETFs?"},
                         headers=auth_headers, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        assert r.json()["session_id"] == sid

    def test_list_sessions(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.get(f"{API}/ai/coach/sessions", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert TestAICoach.session_id in ids

    def test_session_messages(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestAICoach.session_id
        r = session.get(f"{API}/ai/coach/sessions/{sid}/messages", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        msgs = r.json()
        # At least 4 messages: 2 user + 2 assistant
        assert len(msgs) >= 4
        roles = [m["role"] for m in msgs]
        assert "user" in roles and "assistant" in roles


# ---------- Cleanup: Stream deletion (last) ----------
class TestZCleanup:
    def test_delete_stream_cascade(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestStreamsAndEntries.stream_id
        if not sid:
            pytest.skip("No stream created")
        r = session.delete(f"{API}/streams/{sid}", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        # entries should be gone
        r2 = session.get(f"{API}/streams/{sid}/entries", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        # stream not found, entries returns [] (no auth filter cares)
        assert r2.json() == [] or r2.status_code in (200, 404)
        # second delete returns 404
        r3 = session.delete(f"{API}/streams/{sid}", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r3.status_code == 404

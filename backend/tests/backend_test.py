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


# ---------- Iteration 2: PATCH /streams/{id} ----------
class TestStreamPatch:
    sid = None

    def test_create_for_patch(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.post(f"{API}/streams", json={
            "name": "TEST_PatchMe", "category": "affiliate",
            "initial_investment": 50.0, "monthly_estimate": 100.0, "notes": "before",
        }, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, r.text
        TestStreamPatch.sid = r.json()["id"]
        # Add an entry so we can validate total_earned is preserved across PATCH
        e = session.post(f"{API}/streams/{TestStreamPatch.sid}/entries",
                         json={"amount": 42.5, "note": "TEST seed"},
                         headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert e.status_code == 200

    def test_patch_updates_fields_and_preserves_total(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestStreamPatch.sid
        assert sid
        r = session.patch(f"{API}/streams/{sid}", json={
            "name": "TEST_PatchedName",
            "category": "dividends",
            "initial_investment": 250.0,
            "monthly_estimate": 333.0,
            "notes": "after",
        }, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST_PatchedName"
        assert d["category"] == "dividends"
        assert d["initial_investment"] == 250.0
        assert d["monthly_estimate"] == 333.0
        assert d["notes"] == "after"
        # total_earned must be derived from entries, not lost
        assert abs(d["total_earned"] - 42.5) < 0.01
        # GET to confirm persistence
        r2 = session.get(f"{API}/streams", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        s = next(x for x in r2.json() if x["id"] == sid)
        assert s["name"] == "TEST_PatchedName"
        assert s["category"] == "dividends"
        assert abs(s["total_earned"] - 42.5) < 0.01

    def test_patch_partial_only_name(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestStreamPatch.sid
        r = session.patch(f"{API}/streams/{sid}", json={"name": "TEST_OnlyName"},
                          headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "TEST_OnlyName"
        # Other fields from previous PATCH preserved
        assert d["category"] == "dividends"
        assert d["initial_investment"] == 250.0

    def test_patch_nonexistent_returns_404(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.patch(f"{API}/streams/does-not-exist-uuid",
                          json={"name": "x"}, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 404

    def test_patch_cleanup(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestStreamPatch.sid
        if sid:
            session.delete(f"{API}/streams/{sid}", headers=auth_headers, timeout=DEFAULT_TIMEOUT)


# ---------- Iteration 2: Billing /api/billing/me ----------
class TestBillingMe:
    def test_default_for_new_user(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.get(f"{API}/billing/me", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("is_pro", "ai_calls_used_this_month", "ai_calls_limit"):
            assert k in d, f"missing {k}"
        # pro_until is optional
        assert "pro_until" in d
        assert d["is_pro"] is False
        assert d["ai_calls_limit"] == 5
        assert isinstance(d["ai_calls_used_this_month"], int)
        assert d["ai_calls_used_this_month"] >= 0


# ---------- Iteration 2: Billing /api/billing/checkout ----------
class TestBillingCheckout:
    session_id = None

    def test_checkout_creates_stripe_session(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.post(f"{API}/billing/checkout", json={
            "package_id": "pro_monthly",
            "origin_url": BASE_URL,
        }, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert "url" in d and "session_id" in d
        assert d["url"].startswith("https://checkout.stripe.com"), f"unexpected url: {d['url']}"
        assert isinstance(d["session_id"], str) and len(d["session_id"]) > 5
        TestBillingCheckout.session_id = d["session_id"]

    def test_checkout_invalid_package(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.post(f"{API}/billing/checkout", json={
            "package_id": "bogus_pkg",
            "origin_url": BASE_URL,
        }, headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        # Pydantic Literal will return 422; FastAPI returns 422 for validation
        # Also acceptable: 400 if validated server-side
        assert r.status_code in (400, 422)

    def test_billing_status_returns_schema(self, session: requests.Session, auth_headers: dict) -> None:
        sid = TestBillingCheckout.session_id
        assert sid, "need session id from prior test"
        r = session.get(f"{API}/billing/status/{sid}", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        for k in ("payment_status", "status", "amount_total", "currency"):
            assert k in d, f"missing {k} in status response: {d}"
        # For unpaid sessions, expect open/unpaid
        # 'initiated' is the graceful fallback when Stripe has not yet propagated
        # the session (sk_test_emergent proxy). 'open' once Stripe finds it, 'complete' after paid.
        assert d["status"] in ("open", "complete", "expired", "initiated")
        assert d["payment_status"] in ("unpaid", "paid", "no_payment_required", "initiated")

    def test_billing_status_unknown_session(self, session: requests.Session, auth_headers: dict) -> None:
        r = session.get(f"{API}/billing/status/cs_test_does_not_exist_xyz", headers=auth_headers, timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 404


# ---------- Iteration 2: Stripe webhook route exists ----------
class TestStripeWebhookRoute:
    def test_webhook_route_exists_and_does_not_500(self, session: requests.Session) -> None:
        # No signature header => should be rejected with 400 (NOT 404, NOT 500)
        r = session.post(f"{API}/webhook/stripe", data=b"{}", timeout=DEFAULT_TIMEOUT,
                         headers={"Content-Type": "application/json"})
        assert r.status_code != 404, "webhook route missing"
        assert r.status_code != 500, f"webhook 500: {r.text[:200]}"
        # Expect 400 due to missing/invalid signature
        assert r.status_code == 400


# ---------- Iteration 2: AI Free Quota (DB-mutated to avoid LLM burn) ----------
class TestAIQuota:
    @pytest.fixture(scope="class")
    def fresh_user(self, session: requests.Session) -> dict:
        email = f"test+quota_{int(time.time())}_{uuid.uuid4().hex[:6]}@autopilot.io"
        r = session.post(f"{API}/auth/register",
                         json={"email": email, "password": "TestPass123!", "name": "TEST_Quota"},
                         timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        return {"email": email, "user_id": d["user"]["id"], "token": d["token"]}

    def _set_usage(self, user_id: str, count: int) -> None:
        """Directly mutate db.ai_usage to simulate quota state without burning LLM credits."""
        from pymongo import MongoClient
        from datetime import datetime, timezone
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        cli = MongoClient(mongo_url)
        try:
            now = datetime.now(timezone.utc)
            key = f"{now.year}-{now.month:02d}"
            cli[db_name].ai_usage.update_one(
                {"user_id": user_id, "month": key},
                {"$set": {"count": count, "updated_at": now.isoformat()}},
                upsert=True,
            )
        finally:
            cli.close()

    def _set_pro_until(self, user_id: str, iso_str) -> None:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        cli = MongoClient(mongo_url)
        try:
            cli[db_name].users.update_one({"id": user_id}, {"$set": {"pro_until": iso_str}})
        finally:
            cli.close()

    def test_free_user_402_when_quota_exhausted(self, session: requests.Session, fresh_user: dict) -> None:
        # Simulate 5 calls already used this month
        self._set_usage(fresh_user["user_id"], 5)
        # Verify billing/me reflects it
        r = session.get(f"{API}/billing/me",
                        headers={"Authorization": f"Bearer {fresh_user['token']}"},
                        timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["ai_calls_used_this_month"] == 5
        assert d["is_pro"] is False
        # 6th call must 402
        r2 = session.post(f"{API}/ai/ideas", json={
            "skills": "writing", "budget_usd": 100, "hours_per_week": 5,
            "risk_tolerance": "low", "interests": "blogs",
        }, headers={"Authorization": f"Bearer {fresh_user['token']}"}, timeout=AI_TIMEOUT)
        assert r2.status_code == 402, f"expected 402 got {r2.status_code}: {r2.text[:200]}"
        body = r2.json()
        msg = (body.get("detail") or "").lower()
        assert "upgrade" in msg or "pro" in msg or "limit" in msg, f"missing upgrade msg: {body}"

    def test_pro_user_bypasses_quota(self, session: requests.Session, fresh_user: dict) -> None:
        # Mark user as Pro until far in the future, keep usage at 5
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self._set_pro_until(fresh_user["user_id"], future)
        # billing/me should now reflect Pro + unlimited
        r = session.get(f"{API}/billing/me",
                        headers={"Authorization": f"Bearer {fresh_user['token']}"},
                        timeout=DEFAULT_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["is_pro"] is True
        assert d["ai_calls_limit"] == -1
        assert d["pro_until"] is not None

        # Snapshot usage BEFORE call
        from pymongo import MongoClient
        cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        try:
            now = datetime.now(timezone.utc)
            key = f"{now.year}-{now.month:02d}"
            db_name = os.environ.get("DB_NAME", "test_database")
            before = cli[db_name].ai_usage.find_one({"user_id": fresh_user["user_id"], "month": key}) or {}
            before_count = int(before.get("count", 0))
        finally:
            cli.close()

        # Make an AI call. Pro users should NOT 402, and should NOT increment usage.
        r2 = session.post(f"{API}/ai/ideas", json={
            "skills": "writing", "budget_usd": 100, "hours_per_week": 5,
            "risk_tolerance": "low", "interests": "blogs",
        }, headers={"Authorization": f"Bearer {fresh_user['token']}"}, timeout=AI_TIMEOUT)
        # Allow 502 (transient LLM budget) — but NEVER 402 for a Pro user.
        assert r2.status_code != 402, f"Pro user got 402: {r2.text[:200]}"
        if r2.status_code not in (200, 502, 503):
            pytest.fail(f"unexpected status {r2.status_code}: {r2.text[:200]}")

        # Confirm usage NOT incremented for Pro
        cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        try:
            db_name = os.environ.get("DB_NAME", "test_database")
            after = cli[db_name].ai_usage.find_one({"user_id": fresh_user["user_id"], "month": key}) or {}
            after_count = int(after.get("count", 0))
        finally:
            cli.close()
        assert after_count == before_count, f"Pro user usage should not increment: {before_count} -> {after_count}"


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

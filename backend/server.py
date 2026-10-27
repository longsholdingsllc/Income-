from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import json
import re
import logging
import math
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
import asyncio
from types import SimpleNamespace

import stripe as stripe_sdk
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from store import get_db
from llm import chat as llm_chat
from lead_qualifier import qualify_lead

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Data layer — MongoDB when MONGO_URL is set, otherwise the built-in
# SQLite store (see store.py). `db` exposes the same async API either way.
client, db = get_db()

# Built frontend (served same-origin when present — see SPA fallback below)
BUILD_DIR = Path(os.environ.get("FRONTEND_BUILD_DIR", ROOT_DIR.parent / "frontend" / "build"))

# Config — read with .get() so a missing custom env var never crashes module import
# (which would create a Kubernetes restart loop). Endpoints that need a particular key
# will check at request time and return a clear 500 if it's missing.
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
JWT_SECRET = os.environ.get('JWT_SECRET', '')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
JWT_ALGO = "HS256"
JWT_EXP_DAYS = 14
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# Pricing packages — server-side only (NEVER accept price from frontend)
PACKAGES = {
    "pro_monthly": {
        "name": "Autopilot Pro (30 days)",
        "amount": 9.00,
        "currency": "usd",
        "grants_days": 30,
    },
}

# Free tier quota: total AI calls per month across ideas + content + coach
FREE_AI_QUOTA_PER_MONTH = 5

app = FastAPI(title="Autopilot - Passive Income OS")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logger = logging.getLogger("autopilot")
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_jwt(user_id: str) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="Server auth is not configured (JWT_SECRET missing)")
    payload = {
        "sub": user_id,
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc() + timedelta(days=JWT_EXP_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="Server auth is not configured (JWT_SECRET missing)")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ---------- Models ----------
class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: str


class AuthResp(BaseModel):
    token: str
    user: UserOut


class StreamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: Literal[
        "affiliate", "dividends", "rentals", "digital_products",
        "crypto_staking", "print_on_demand", "royalties", "interest", "ads", "other"
    ]
    initial_investment: float = 0.0
    monthly_estimate: float = 0.0
    notes: Optional[str] = ""


class StreamOut(StreamCreate):
    id: str
    user_id: str
    created_at: str
    total_earned: float = 0.0


class StreamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Optional[Literal[
        "affiliate", "dividends", "rentals", "digital_products",
        "crypto_staking", "print_on_demand", "royalties", "interest", "ads", "other"
    ]] = None
    initial_investment: Optional[float] = None
    monthly_estimate: Optional[float] = None
    notes: Optional[str] = None


class EntryCreate(BaseModel):
    amount: float
    note: Optional[str] = ""
    date: Optional[str] = None  # ISO date


class EntryOut(BaseModel):
    id: str
    stream_id: str
    user_id: str
    amount: float
    note: str
    date: str
    created_at: str


class GoalUpsert(BaseModel):
    monthly_target: float = 0.0
    freedom_number: float = 0.0  # total monthly passive income needed for financial freedom


class GoalOut(GoalUpsert):
    user_id: str
    updated_at: str


class IdeaReq(BaseModel):
    skills: str
    budget_usd: float
    hours_per_week: float
    risk_tolerance: Literal["low", "medium", "high"]
    interests: Optional[str] = ""


class IdeaItem(BaseModel):
    title: str
    category: str
    summary: str
    estimated_monthly_income: str
    startup_cost: str
    time_to_first_dollar: str
    risk: str
    action_plan: List[str]
    tools_needed: List[str]


class IdeaResp(BaseModel):
    ideas: List[IdeaItem]


class ContentReq(BaseModel):
    niche: str
    keywords: str
    target_audience: Optional[str] = ""
    affiliate_product: Optional[str] = ""


class ContentResp(BaseModel):
    title: str
    meta_description: str
    outline: List[str]
    article_markdown: str
    cta_suggestions: List[str]


class CoachReq(BaseModel):
    session_id: Optional[str] = None
    message: str


class CoachResp(BaseModel):
    session_id: str
    reply: str


class CoachSession(BaseModel):
    id: str
    title: str
    updated_at: str


class CoachMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str




class LeadCapture(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=160)
    title: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=2000)
    budget: Optional[str] = Field(default=None, max_length=80)
    timeline: Optional[str] = Field(default=None, max_length=80)
    source: Optional[str] = Field(default="landing", max_length=60)


# ---------- Auth ----------
@api_router.post("/auth/register", response_model=AuthResp)
async def register(req: RegisterReq) -> AuthResp:
    existing = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())

    qualification = await qualify_lead({
        "name": req.name.strip(),
        "email": req.email.lower(),
        "message": "New Autopilot (Income-) account registration",
        "timeline": "this month",
    })

    doc = {
        "id": user_id,
        "email": req.email.lower(),
        "name": req.name.strip(),
        "password_hash": hash_password(req.password),
        "created_at": iso(now_utc()),
        "lead_score": qualification.get("score"),
        "lead_action": qualification.get("recommended_action"),
        "lead_summary": qualification.get("summary"),
    }
    await db.users.insert_one(doc)

    try:
        await db.leads.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": req.name.strip(),
            "email": req.email.lower(),
            "source": "register",
            "score": qualification.get("score"),
            "recommended_action": qualification.get("recommended_action"),
            "summary": qualification.get("summary"),
            "created_at": iso(now_utc()),
        })
    except Exception:
        pass

    logger.info(
        "New user registered & scored: %s · score=%s · action=%s",
        doc["email"], doc.get("lead_score"), doc.get("lead_action"),
    )

    token = create_jwt(user_id)
    return AuthResp(
        token=token,
        user=UserOut(id=user_id, email=doc["email"], name=doc["name"], created_at=doc["created_at"]),
    )


@api_router.post("/auth/login", response_model=AuthResp)
async def login(req: LoginReq) -> AuthResp:
    user = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_jwt(user["id"])
    return AuthResp(
        token=token,
        user=UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"]),
    )


@api_router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])


@api_router.post("/leads", status_code=201)
async def capture_lead(req: LeadCapture) -> dict:
    """Public lead capture – scores with live AI agent and stores result."""
    qualification = await qualify_lead({
        "name": req.name.strip(),
        "email": str(req.email).lower(),
        "company": (req.company or "").strip() or None,
        "title": (req.title or "").strip() or None,
        "message": (req.message or "Inbound lead from Autopilot landing").strip(),
        "budget": (req.budget or "").strip() or None,
        "timeline": (req.timeline or "").strip() or None,
    })
    doc = {
        "id": str(uuid.uuid4()),
        "name": req.name.strip(),
        "email": str(req.email).lower(),
        "company": (req.company or "").strip() or None,
        "title": (req.title or "").strip() or None,
        "message": (req.message or "").strip() or None,
        "budget": (req.budget or "").strip() or None,
        "timeline": (req.timeline or "").strip() or None,
        "source": (req.source or "landing").strip(),
        "score": qualification.get("score"),
        "recommended_action": qualification.get("recommended_action"),
        "summary": qualification.get("summary"),
        "created_at": iso(now_utc()),
    }
    await db.leads.insert_one(doc)
    logger.info(
        "Lead captured & scored: %s · score=%s · action=%s",
        doc["email"], doc.get("score"), doc.get("recommended_action"),
    )
    return {
        "ok": True,
        "id": doc["id"],
        "score": doc["score"],
        "recommended_action": doc["recommended_action"],
        "summary": doc["summary"],
    }


# ---------- Streams ----------
@api_router.post("/streams", response_model=StreamOut)
async def create_stream(req: StreamCreate, user: dict = Depends(get_current_user)) -> StreamOut:
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "user_id": user["id"],
        **req.model_dump(),
        "created_at": iso(now_utc()),
    }
    await db.streams.insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["total_earned"] = 0.0
    return StreamOut(**out)


@api_router.get("/streams", response_model=List[StreamOut])
async def list_streams(user: dict = Depends(get_current_user)) -> List[StreamOut]:
    streams = await db.streams.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    if not streams:
        return []
    # Single aggregation across all streams (avoids N+1 query)
    totals_cursor = db.entries.aggregate([
        {"$match": {"user_id": user["id"]}},
        {"$group": {"_id": "$stream_id", "total": {"$sum": "$amount"}}},
    ])
    totals = {row["_id"]: float(row["total"]) async for row in totals_cursor}
    result = []
    for s in streams:
        s["total_earned"] = totals.get(s["id"], 0.0)
        result.append(StreamOut(**s))
    return result


@api_router.patch("/streams/{stream_id}", response_model=StreamOut)
async def update_stream(stream_id: str, req: StreamUpdate, user: dict = Depends(get_current_user)) -> StreamOut:
    existing = await db.streams.find_one({"id": stream_id, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Stream not found")
    updates = {k: v for k, v in req.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await db.streams.update_one({"id": stream_id, "user_id": user["id"]}, {"$set": updates})
    fresh = await db.streams.find_one({"id": stream_id, "user_id": user["id"]}, {"_id": 0})
    agg = await db.entries.aggregate([
        {"$match": {"stream_id": stream_id, "user_id": user["id"]}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    fresh["total_earned"] = float(agg[0]["total"]) if agg else 0.0
    return StreamOut(**fresh)


@api_router.delete("/streams/{stream_id}")
async def delete_stream(stream_id: str, user: dict = Depends(get_current_user)) -> dict:
    res = await db.streams.delete_one({"id": stream_id, "user_id": user["id"]})
    await db.entries.delete_many({"stream_id": stream_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"ok": True}


@api_router.post("/streams/{stream_id}/entries", response_model=EntryOut)
async def add_entry(stream_id: str, req: EntryCreate, user: dict = Depends(get_current_user)) -> EntryOut:
    stream = await db.streams.find_one({"id": stream_id, "user_id": user["id"]}, {"_id": 0})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    eid = str(uuid.uuid4())
    date_str = req.date or iso(now_utc())
    doc = {
        "id": eid,
        "stream_id": stream_id,
        "user_id": user["id"],
        "amount": float(req.amount),
        "note": req.note or "",
        "date": date_str,
        "created_at": iso(now_utc()),
    }
    await db.entries.insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    return EntryOut(**out)


@api_router.get("/streams/{stream_id}/entries", response_model=List[EntryOut])
async def list_entries(stream_id: str, user: dict = Depends(get_current_user)) -> List[EntryOut]:
    entries = await db.entries.find(
        {"stream_id": stream_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("date", -1).to_list(1000)
    return [EntryOut(**e) for e in entries]


# ---------- Dashboard helpers ----------
def _parse_entry_date(raw: str) -> Optional[datetime]:
    """Parse ISO date from entry, always return aware UTC datetime or None."""
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def _month_range(year: int, month: int) -> tuple[datetime, datetime]:
    """Return [start, end) datetimes for the given calendar month."""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _month_offset(now: datetime, months_back: int) -> tuple[int, int]:
    """Return (year, month) months_back months before `now`."""
    year, month = now.year, now.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return year, month


def _sum_between(entries: List[dict], start: datetime, end: Optional[datetime] = None) -> float:
    total = 0.0
    for e in entries:
        d = _parse_entry_date(e.get("date", ""))
        if d is None:
            continue
        if end is None:
            if d >= start:
                total += float(e["amount"])
        else:
            if start <= d < end:
                total += float(e["amount"])
    return total


def _build_trend(entries: List[dict], now: datetime, months: int = 6) -> List[dict]:
    trend: List[dict] = []
    for i in range(months - 1, -1, -1):
        year, month = _month_offset(now, i)
        m_start, m_end = _month_range(year, month)
        total = _sum_between(entries, m_start, m_end)
        trend.append({"month": m_start.strftime("%b"), "income": round(total, 2)})
    return trend


def _build_recent(streams: List[dict], entries: List[dict], limit: int = 8) -> List[dict]:
    name_by_id = {s["id"]: s["name"] for s in streams}
    recent = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)[:limit]
    return [
        {
            "id": e["id"],
            "stream_name": name_by_id.get(e["stream_id"], "Unknown"),
            "amount": float(e["amount"]),
            "date": e["date"],
            "note": e.get("note", ""),
        }
        for e in recent
    ]


# ---------- Dashboard ----------
@api_router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)) -> dict:
    streams: List[dict] = await db.streams.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)

    now = now_utc()
    month_start, _ = _month_range(now.year, now.month)

    # Bound entries to last 7 months (covers 6-month trend + current). Production-safe
    # for users with very long histories. Older entries still aggregate for total_earned via
    # a single MongoDB pipeline below.
    earliest_year, earliest_month = _month_offset(now, 6)
    earliest_start, _ = _month_range(earliest_year, earliest_month)
    entries: List[dict] = await db.entries.find(
        {"user_id": user["id"], "date": {"$gte": iso(earliest_start)}},
        {"_id": 0},
    ).sort("date", -1).limit(2000).to_list(2000)

    # All-time totals via a single aggregation (does not load all docs into memory)
    total_invested = sum(float(s.get("initial_investment", 0)) for s in streams)
    earned_agg = await db.entries.aggregate([
        {"$match": {"user_id": user["id"]}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    total_earned = float(earned_agg[0]["total"]) if earned_agg else 0.0

    monthly = _sum_between(entries, month_start)

    goal = await db.goals.find_one({"user_id": user["id"]}, {"_id": 0})
    monthly_target = float(goal["monthly_target"]) if goal else 0.0
    freedom_number = float(goal["freedom_number"]) if goal else 0.0
    progress = (monthly / monthly_target * 100.0) if monthly_target > 0 else 0.0

    # Breakdown also via aggregation (covers full history, joined with stream categories)
    breakdown_agg = await db.entries.aggregate([
        {"$match": {"user_id": user["id"]}},
        {"$group": {"_id": "$stream_id", "amount": {"$sum": "$amount"}}},
    ]).to_list(1000)
    stream_cat = {s["id"]: s["category"] for s in streams}
    by_cat: dict = {}
    for row in breakdown_agg:
        cat = stream_cat.get(row["_id"], "other")
        by_cat[cat] = by_cat.get(cat, 0.0) + float(row["amount"])
    breakdown = [
        {"category": k, "amount": round(v, 2)}
        for k, v in sorted(by_cat.items(), key=lambda x: -x[1])
    ]

    return {
        "total_invested": round(total_invested, 2),
        "total_earned": round(total_earned, 2),
        "monthly_income": round(monthly, 2),
        "active_streams": len(streams),
        "trend": _build_trend(entries, now, months=6),
        "breakdown": breakdown,
        "goal": {
            "monthly_target": monthly_target,
            "freedom_number": freedom_number,
            "progress_percent": round(min(progress, 999), 1),
        },
        "recent_entries": _build_recent(streams, entries, limit=8),
    }


# ---------- Goals ----------
@api_router.get("/goals", response_model=GoalOut)
async def get_goal(user: dict = Depends(get_current_user)) -> GoalOut:
    goal = await db.goals.find_one({"user_id": user["id"]}, {"_id": 0})
    if not goal:
        return GoalOut(user_id=user["id"], monthly_target=0, freedom_number=0, updated_at=iso(now_utc()))
    return GoalOut(**goal)


@api_router.post("/goals", response_model=GoalOut)
async def upsert_goal(req: GoalUpsert, user: dict = Depends(get_current_user)) -> GoalOut:
    doc = {
        "user_id": user["id"],
        "monthly_target": float(req.monthly_target),
        "freedom_number": float(req.freedom_number),
        "updated_at": iso(now_utc()),
    }
    await db.goals.update_one({"user_id": user["id"]}, {"$set": doc}, upsert=True)
    return GoalOut(**doc)


# ---------- Billing (Stripe) & Pro Quota ----------
async def _is_pro_active(user_id: str) -> tuple[bool, Optional[str]]:
    """Return (is_pro, pro_until_iso). Pro is active if pro_until > now."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "pro_until": 1})
    pro_until = user.get("pro_until") if user else None
    if not pro_until:
        return False, None
    try:
        dt = datetime.fromisoformat(pro_until.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > now_utc(), pro_until
    except Exception:
        return False, pro_until


async def _ai_quota_check_and_increment(user_id: str) -> None:
    """Gate AI calls: Pro unlimited; Free = FREE_AI_QUOTA_PER_MONTH per calendar month."""
    is_pro, _ = await _is_pro_active(user_id)
    if is_pro:
        return
    now = now_utc()
    key = f"{now.year}-{now.month:02d}"
    rec = await db.ai_usage.find_one({"user_id": user_id, "month": key}, {"_id": 0})
    used = int(rec["count"]) if rec else 0
    if used >= FREE_AI_QUOTA_PER_MONTH:
        raise HTTPException(
            status_code=402,
            detail=f"Free tier limit reached ({FREE_AI_QUOTA_PER_MONTH}/mo). Upgrade to Pro for unlimited AI.",
        )
    await db.ai_usage.update_one(
        {"user_id": user_id, "month": key},
        {"$inc": {"count": 1}, "$set": {"updated_at": iso(now)}},
        upsert=True,
    )


# ---------- Stripe helpers (official SDK) ----------
def _stripe():
    if not STRIPE_API_KEY:
        raise HTTPException(
            status_code=503, detail="Billing is not configured (STRIPE_API_KEY missing)"
        )
    stripe_sdk.api_key = STRIPE_API_KEY
    return stripe_sdk


async def _stripe_create_checkout(amount, currency, success_url, cancel_url, metadata, product_name):
    sdk = _stripe()

    def _create():
        return sdk.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": product_name},
                        "unit_amount": int(round(amount * 100)),
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

    session = await asyncio.to_thread(_create)
    return session.url, session.id


async def _stripe_get_status(session_id):
    sdk = _stripe()
    s = await asyncio.to_thread(sdk.checkout.Session.retrieve, session_id)
    return SimpleNamespace(
        payment_status=s.payment_status,
        status=s.status,
        amount_total=int(s.amount_total or 0),
        currency=s.currency or "usd",
    )


class CheckoutReq(BaseModel):
    package_id: Literal["pro_monthly"]
    origin_url: str


class CheckoutResp(BaseModel):
    url: str
    session_id: str


class BillingStatus(BaseModel):
    is_pro: bool
    pro_until: Optional[str] = None
    ai_calls_used_this_month: int
    ai_calls_limit: int  # -1 means unlimited
    sandbox_mode: bool = False


@api_router.get("/billing/me", response_model=BillingStatus)
async def billing_me(user: dict = Depends(get_current_user)) -> BillingStatus:
    is_pro, pro_until = await _is_pro_active(user["id"])
    now = now_utc()
    key = f"{now.year}-{now.month:02d}"
    rec = await db.ai_usage.find_one({"user_id": user["id"], "month": key}, {"_id": 0})
    used = int(rec["count"]) if rec else 0
    return BillingStatus(
        is_pro=is_pro,
        pro_until=pro_until if is_pro else None,
        ai_calls_used_this_month=used,
        ai_calls_limit=-1 if is_pro else FREE_AI_QUOTA_PER_MONTH,
        sandbox_mode=SANDBOX_MODE,
    )


@api_router.post("/billing/checkout", response_model=CheckoutResp)
async def billing_checkout(req: CheckoutReq, request: Request, user: dict = Depends(get_current_user)) -> CheckoutResp:
    pkg = PACKAGES.get(req.package_id)
    if not pkg:
        raise HTTPException(status_code=400, detail="Invalid package")

    origin = req.origin_url.rstrip("/")
    success_url = f"{origin}/app/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/app/pricing"

    metadata = {
        "user_id": user["id"],
        "user_email": user["email"],
        "package_id": req.package_id,
    }
    session_url, session_id = await _stripe_create_checkout(
        amount=float(pkg["amount"]),
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        product_name=pkg["name"],
    )

    # Create payment_transactions record BEFORE redirect
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "package_id": req.package_id,
        "amount": float(pkg["amount"]),
        "currency": pkg["currency"],
        "payment_status": "initiated",
        "status": "open",
        "metadata": metadata,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })
    return CheckoutResp(url=session_url, session_id=session_id)


@api_router.get("/billing/status/{session_id}")
async def billing_status(session_id: str, request: Request, user: dict = Depends(get_current_user)) -> dict:
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # If already finalized, return cached status (idempotent — never grant credit twice)
    if tx.get("payment_status") == "paid" and tx.get("credit_applied"):
        return {
            "payment_status": tx["payment_status"],
            "status": tx["status"],
            "amount_total": int(tx.get("amount_total") or (float(tx["amount"]) * 100)),
            "currency": tx.get("currency", "usd"),
        }

    try:
        cs = await _stripe_get_status(session_id)
    except Exception as e:
        # SDK can throw when Stripe has not yet propagated the session (especially
        # immediately after creation). Fall back to the cached transaction record
        # so the frontend poll loop sees a graceful pending state instead of 500.
        logger.warning("stripe status fallback: %s", str(e)[:160])
        return {
            "payment_status": tx.get("payment_status", "unpaid"),
            "status": tx.get("status", "open"),
            "amount_total": int(float(tx["amount"]) * 100),
            "currency": tx.get("currency", "usd"),
        }

    # Persist status
    updates = {
        "payment_status": cs.payment_status,
        "status": cs.status,
        "amount_total": int(cs.amount_total),
        "currency": cs.currency,
        "updated_at": iso(now_utc()),
    }

    # On first successful payment, extend user's pro_until
    if cs.payment_status == "paid" and not tx.get("credit_applied"):
        await _grant_pro(user["id"], tx["package_id"])
        updates["credit_applied"] = True

    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": updates})
    return {
        "payment_status": cs.payment_status,
        "status": cs.status,
        "amount_total": int(cs.amount_total),
        "currency": cs.currency,
    }


SANDBOX_MODE = STRIPE_API_KEY.startswith("sk_test_") if STRIPE_API_KEY else False


async def _grant_pro(user_id: str, package_id: str) -> str:
    """Idempotent: extend pro_until for a user based on package grants_days."""
    pkg = PACKAGES[package_id]
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    base = now_utc()
    if user_doc and user_doc.get("pro_until"):
        try:
            existing = datetime.fromisoformat(user_doc["pro_until"].replace("Z", "+00:00"))
            if existing.tzinfo is None:
                existing = existing.replace(tzinfo=timezone.utc)
            if existing > base:
                base = existing
        except Exception:
            pass
    new_until = base + timedelta(days=int(pkg["grants_days"]))
    await db.users.update_one({"id": user_id}, {"$set": {"pro_until": iso(new_until)}})
    return iso(new_until)


@api_router.post("/billing/dev/confirm/{session_id}")
async def billing_dev_confirm(session_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Sandbox-only fallback: confirm a payment when the upstream Stripe proxy's
    read-path is unavailable (returns 404 for just-created sessions in the emergent
    sandbox). Marks the transaction paid and grants Pro. Gated strictly to test keys
    AND to the transaction's owning user."""
    if not SANDBOX_MODE:
        raise HTTPException(status_code=404, detail="Not available")
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("credit_applied"):
        return {"payment_status": "paid", "credit_applied": True, "pro_until": None}
    pro_until = await _grant_pro(user["id"], tx["package_id"])
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": "paid",
            "status": "complete",
            "credit_applied": True,
            "confirmed_via": "sandbox_dev_endpoint",
            "updated_at": iso(now_utc()),
        }},
    )
    return {"payment_status": "paid", "credit_applied": True, "pro_until": pro_until}


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request) -> dict:
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        # Reject quietly without a stack trace — Stripe will always send this header.
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
    body = await request.body()
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not STRIPE_API_KEY or not webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
    stripe_sdk.api_key = STRIPE_API_KEY
    try:
        event = stripe_sdk.Webhook.construct_event(body, signature, webhook_secret)
    except Exception as e:
        logger.warning("stripe webhook verification failed: %s", str(e)[:160])
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {str(e)[:200]}")
    _obj = event["data"]["object"]
    resp = SimpleNamespace(
        session_id=_obj.get("id"),
        payment_status="paid" if _obj.get("payment_status") == "paid" else "unpaid",
        event_type=event["type"],
        event_id=event["id"],
    )

    # Update the transaction and grant Pro if applicable
    tx = await db.payment_transactions.find_one({"session_id": resp.session_id}, {"_id": 0})
    if not tx:
        return {"received": True}
    updates = {
        "payment_status": resp.payment_status,
        "event_type": resp.event_type,
        "event_id": resp.event_id,
        "updated_at": iso(now_utc()),
    }
    if resp.payment_status == "paid" and not tx.get("credit_applied"):
        if tx["package_id"] in PACKAGES:
            await _grant_pro(tx["user_id"], tx["package_id"])
            updates["credit_applied"] = True
    await db.payment_transactions.update_one({"session_id": resp.session_id}, {"$set": updates})
    return {"received": True}


# ---------- AI Idea Generator ----------
def _extract_json(text: str):
    # Try to extract JSON object/array from Claude's response
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Strip markdown code fences
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    # Find outermost braces
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError("Could not parse JSON from LLM response")


@api_router.post("/ai/ideas", response_model=IdeaResp)
async def generate_ideas(req: IdeaReq, user: dict = Depends(get_current_user)) -> IdeaResp:
    await _ai_quota_check_and_increment(user["id"])
    system_msg = (
        "You are a world-class passive income strategist. Generate specific, realistic, and actionable "
        "passive income ideas tailored to the user's profile. Respond ONLY with valid JSON matching "
        "this exact schema (no prose, no markdown fences): "
        '{"ideas":[{"title":str,"category":str,"summary":str,"estimated_monthly_income":str,'
        '"startup_cost":str,"time_to_first_dollar":str,"risk":str,"action_plan":[str,str,...],'
        '"tools_needed":[str,...]}]}'
    )
    prompt = (
        f"User profile:\n"
        f"- Skills: {req.skills}\n"
        f"- Budget: ${req.budget_usd:.2f} USD\n"
        f"- Hours per week available: {req.hours_per_week}\n"
        f"- Risk tolerance: {req.risk_tolerance}\n"
        f"- Interests: {req.interests or '(not specified)'}\n\n"
        f"Generate exactly 5 passive income ideas. Each action_plan should have 4-6 concrete steps. "
        f"Output JSON only."
    )
    try:
        response = await llm_chat(
            "ideas", system_msg, prompt,
            meta={
                "skills": req.skills, "budget_usd": req.budget_usd,
                "hours_per_week": req.hours_per_week,
                "risk_tolerance": req.risk_tolerance, "interests": req.interests or "",
            },
        )
        data = _extract_json(response)
        ideas = [IdeaItem(**i) for i in data.get("ideas", [])]
        return IdeaResp(ideas=ideas)
    except Exception as e:
        logger.exception("ideas generation failed")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)[:200]}")


# ---------- AI Content Generator ----------
@api_router.post("/ai/content", response_model=ContentResp)
async def generate_content(req: ContentReq, user: dict = Depends(get_current_user)) -> ContentResp:
    await _ai_quota_check_and_increment(user["id"])
    system_msg = (
        "You are an expert SEO copywriter who writes affiliate-friendly blog posts that rank. "
        "Respond ONLY with valid JSON (no prose, no markdown fences) matching the schema: "
        '{"title":str,"meta_description":str,"outline":[str,...],"article_markdown":str,'
        '"cta_suggestions":[str,...]}. The article_markdown must be a full SEO-optimized blog post '
        "in markdown (700-1000 words), naturally mentioning the product with [AFFILIATE_LINK] placeholders."
    )
    prompt = (
        f"Niche: {req.niche}\n"
        f"Target keywords: {req.keywords}\n"
        f"Target audience: {req.target_audience or '(general)'}\n"
        f"Affiliate product/category: {req.affiliate_product or '(general affiliate placements)'}\n\n"
        f"Produce a high-quality, engaging blog post. Keep the tone helpful and authoritative. "
        f"Output JSON only."
    )
    try:
        response = await llm_chat(
            "content", system_msg, prompt,
            meta={
                "niche": req.niche, "keywords": req.keywords,
                "target_audience": req.target_audience or "",
                "affiliate_product": req.affiliate_product or "",
            },
        )
        data = _extract_json(response)
        return ContentResp(**data)
    except Exception as e:
        logger.exception("content generation failed")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)[:200]}")


# ---------- AI Coach (multi-turn) ----------
COACH_SYSTEM = (
    "You are Autopilot Coach — a direct, pragmatic personal wealth coach specializing in passive income. "
    "Keep replies concise, actionable, and specific. Use bullet points and concrete next steps when helpful. "
    "Reference realistic numbers, timelines, and risks. Never give legally-binding financial advice; remind the user "
    "briefly when relevant. Be warm but efficient."
)


@api_router.post("/ai/coach/chat", response_model=CoachResp)
async def coach_chat(req: CoachReq, user: dict = Depends(get_current_user)) -> CoachResp:
    await _ai_quota_check_and_increment(user["id"])
    # Create or load session
    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        title = req.message.strip()[:60] or "New conversation"
        await db.coach_sessions.insert_one({
            "id": session_id,
            "user_id": user["id"],
            "title": title,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        })
    else:
        existing = await db.coach_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")

    # Persist user message
    await db.coach_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user["id"],
        "role": "user",
        "content": req.message,
        "created_at": iso(now_utc()),
    })

    # Multi-turn memory comes from the stored messages for this session.
    _history_docs = await db.coach_messages.find(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    _history = [
        {"role": m["role"], "content": m["content"]} for m in _history_docs[:-1]
    ]
    _streams = await db.streams.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    _goal = await db.goals.find_one({"user_id": user["id"]}, {"_id": 0})
    reply: str = ""
    try:
        reply = await llm_chat(
            "coach", COACH_SYSTEM, req.message, history=_history,
            meta={
                "streams": [
                    {
                        "name": s.get("name"), "category": s.get("category"),
                        "monthly_estimate": s.get("monthly_estimate", 0),
                    }
                    for s in _streams
                ],
                "monthly_target": (_goal or {}).get("monthly_target", 0),
            },
        )
    except Exception as e:
        logger.exception("coach chat failed")
        raise HTTPException(status_code=502, detail=f"AI chat failed: {str(e)[:200]}")

    await db.coach_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user["id"],
        "role": "assistant",
        "content": reply,
        "created_at": iso(now_utc()),
    })
    await db.coach_sessions.update_one(
        {"id": session_id},
        {"$set": {"updated_at": iso(now_utc())}},
    )
    return CoachResp(session_id=session_id, reply=reply)


@api_router.get("/ai/coach/sessions", response_model=List[CoachSession])
async def list_sessions(user: dict = Depends(get_current_user)) -> List[CoachSession]:
    sessions = await db.coach_sessions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    return [CoachSession(id=s["id"], title=s["title"], updated_at=s["updated_at"]) for s in sessions]


@api_router.get("/ai/coach/sessions/{session_id}/messages", response_model=List[CoachMessage])
async def session_messages(session_id: str, user: dict = Depends(get_current_user)) -> List[CoachMessage]:
    session = await db.coach_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = await db.coach_messages.find(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    return [CoachMessage(role=m["role"], content=m["content"], created_at=m["created_at"]) for m in msgs]


# ---------- Health ----------
@api_router.get("/")
async def root() -> dict:
    return {"app": "Autopilot - Passive Income OS", "status": "ok"}


# ---------- Wire up ----------
app.include_router(api_router)

# SPA fallback — serve the built frontend same-origin when it exists.
if BUILD_DIR.is_dir():
    _static_dir = BUILD_DIR / "static"
    if _static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = BUILD_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(BUILD_DIR / "index.html")


# Root-level health endpoints (Kubernetes liveness/readiness probes hit these directly,
# NOT under /api/). Without these, probes 404 and the pod is killed → restart loop.
@app.get("/")
async def app_root():
    if BUILD_DIR.is_dir():
        return FileResponse(BUILD_DIR / "index.html")
    return {"app": "Autopilot - Passive Income OS", "status": "ok"}


@app.get("/health")
async def app_health() -> dict:
    return {"status": "healthy"}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()

from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

from lead_qualifier import qualify_lead

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
JWT_SECRET = os.environ.get('JWT_SECRET', '')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
JWT_ALGO = "HS256"
JWT_EXP_DAYS = 14
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

PACKAGES = {
    "pro_monthly": {
        "name": "Autopilot Pro (30 days)",
        "amount": 9.00,
        "currency": "usd",
        "grants_days": 30,
    },
}

FREE_AI_QUOTA_PER_MONTH = 5

app = FastAPI(title="Autopilot - Passive Income OS")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logger = logging.getLogger("autopilot")
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


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
    date: Optional[str] = None


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
    freedom_number: float = 0.0


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


class DCAReq(BaseModel):
    asset: str
    monthly_contribution: float
    apy_percent: float
    years: int = Field(ge=1, le=50)


class DCAPoint(BaseModel):
    month: int
    contributed: float
    value: float


class DCAResp(BaseModel):
    asset: str
    final_value: float
    total_contributed: float
    total_interest: float
    monthly_passive_at_end: float
    series: List[DCAPoint]


class LeadCapture(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=160)
    title: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=2000)
    budget: Optional[str] = Field(default=None, max_length=80)
    timeline: Optional[str] = Field(default=None, max_length=80)
    source: Optional[str] = Field(default="landing", max_length=60)


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


def _parse_entry_date(raw: str) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def _month_range(year: int, month: int):
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _month_offset(now: datetime, months_back: int):
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


@api_router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)) -> dict:
    streams: List[dict] = await db.streams.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    now = now_utc()
    month_start, _ = _month_range(now.year, now.month)
    earliest_year, earliest_month = _month_offset(now, 6)
    earliest_start, _ = _month_range(earliest_year, earliest_month)
    entries: List[dict] = await db.entries.find(
        {"user_id": user["id"], "date": {"$gte": iso(earliest_start)}},
        {"_id": 0},
    ).sort("date", -1).limit(2000).to_list(2000)
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


@api_router.get("/goals", response_model=GoalOut)
async def get_goals(user: dict = Depends(get_current_user)) -> GoalOut:
    goal = await db.goals.find_one({"user_id": user["id"]}, {"_id": 0})
    if not goal:
        return GoalOut(user_id=user["id"], monthly_target=0.0, freedom_number=0.0, updated_at=iso(now_utc()))
    return GoalOut(**goal)


@api_router.put("/goals", response_model=GoalOut)
async def upsert_goals(req: GoalUpsert, user: dict = Depends(get_current_user)) -> GoalOut:
    doc = {
        "user_id": user["id"],
        "monthly_target": float(req.monthly_target),
        "freedom_number": float(req.freedom_number),
        "updated_at": iso(now_utc()),
    }
    await db.goals.update_one({"user_id": user["id"]}, {"$set": doc}, upsert=True)
    return GoalOut(**doc)


app.include_router(api_router)

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

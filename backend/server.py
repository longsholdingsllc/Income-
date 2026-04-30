from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Config
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = "HS256"
JWT_EXP_DAYS = 14
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

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
    payload = {
        "sub": user_id,
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc() + timedelta(days=JWT_EXP_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
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


# ---------- Auth ----------
@api_router.post("/auth/register", response_model=AuthResp)
async def register(req: RegisterReq):
    existing = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": req.email.lower(),
        "name": req.name.strip(),
        "password_hash": hash_password(req.password),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    token = create_jwt(user_id)
    return AuthResp(
        token=token,
        user=UserOut(id=user_id, email=doc["email"], name=doc["name"], created_at=doc["created_at"]),
    )


@api_router.post("/auth/login", response_model=AuthResp)
async def login(req: LoginReq):
    user = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_jwt(user["id"])
    return AuthResp(
        token=token,
        user=UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"]),
    )


@api_router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])


# ---------- Streams ----------
@api_router.post("/streams", response_model=StreamOut)
async def create_stream(req: StreamCreate, user: dict = Depends(get_current_user)):
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
async def list_streams(user: dict = Depends(get_current_user)):
    streams = await db.streams.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # compute total earned per stream
    result = []
    for s in streams:
        agg = await db.entries.aggregate([
            {"$match": {"stream_id": s["id"], "user_id": user["id"]}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]).to_list(1)
        s["total_earned"] = float(agg[0]["total"]) if agg else 0.0
        result.append(StreamOut(**s))
    return result


@api_router.delete("/streams/{stream_id}")
async def delete_stream(stream_id: str, user: dict = Depends(get_current_user)):
    res = await db.streams.delete_one({"id": stream_id, "user_id": user["id"]})
    await db.entries.delete_many({"stream_id": stream_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"ok": True}


@api_router.post("/streams/{stream_id}/entries", response_model=EntryOut)
async def add_entry(stream_id: str, req: EntryCreate, user: dict = Depends(get_current_user)):
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
async def list_entries(stream_id: str, user: dict = Depends(get_current_user)):
    entries = await db.entries.find(
        {"stream_id": stream_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("date", -1).to_list(1000)
    return [EntryOut(**e) for e in entries]


# ---------- Dashboard ----------
@api_router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    streams = await db.streams.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    entries = await db.entries.find({"user_id": user["id"]}, {"_id": 0}).to_list(5000)

    total_invested = sum(float(s.get("initial_investment", 0)) for s in streams)
    total_earned = sum(float(e["amount"]) for e in entries)

    # monthly passive income (sum of this calendar month entries)
    now = now_utc()
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    monthly = 0.0
    for e in entries:
        try:
            d = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d >= month_start:
                monthly += float(e["amount"])
        except Exception:
            pass

    # last 6 months trend
    trend = []
    for i in range(5, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        m_start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            m_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            m_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        total = 0.0
        for e in entries:
            try:
                d = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                if m_start <= d < m_end:
                    total += float(e["amount"])
            except Exception:
                pass
        trend.append({"month": m_start.strftime("%b"), "income": round(total, 2)})

    # breakdown by category (all-time earned)
    by_cat: dict = {}
    stream_cat = {s["id"]: s["category"] for s in streams}
    for e in entries:
        cat = stream_cat.get(e["stream_id"], "other")
        by_cat[cat] = by_cat.get(cat, 0.0) + float(e["amount"])
    breakdown = [{"category": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]

    # goal progress
    goal = await db.goals.find_one({"user_id": user["id"]}, {"_id": 0})
    monthly_target = float(goal["monthly_target"]) if goal else 0.0
    freedom_number = float(goal["freedom_number"]) if goal else 0.0
    progress = (monthly / monthly_target * 100.0) if monthly_target > 0 else 0.0

    # recent entries
    recent = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)[:8]
    recent_out = []
    name_by_id = {s["id"]: s["name"] for s in streams}
    for e in recent:
        recent_out.append({
            "id": e["id"],
            "stream_name": name_by_id.get(e["stream_id"], "Unknown"),
            "amount": float(e["amount"]),
            "date": e["date"],
            "note": e.get("note", ""),
        })

    return {
        "total_invested": round(total_invested, 2),
        "total_earned": round(total_earned, 2),
        "monthly_income": round(monthly, 2),
        "active_streams": len(streams),
        "trend": trend,
        "breakdown": breakdown,
        "goal": {
            "monthly_target": monthly_target,
            "freedom_number": freedom_number,
            "progress_percent": round(min(progress, 999), 1),
        },
        "recent_entries": recent_out,
    }


# ---------- Goals ----------
@api_router.get("/goals", response_model=GoalOut)
async def get_goal(user: dict = Depends(get_current_user)):
    goal = await db.goals.find_one({"user_id": user["id"]}, {"_id": 0})
    if not goal:
        return GoalOut(user_id=user["id"], monthly_target=0, freedom_number=0, updated_at=iso(now_utc()))
    return GoalOut(**goal)


@api_router.post("/goals", response_model=GoalOut)
async def upsert_goal(req: GoalUpsert, user: dict = Depends(get_current_user)):
    doc = {
        "user_id": user["id"],
        "monthly_target": float(req.monthly_target),
        "freedom_number": float(req.freedom_number),
        "updated_at": iso(now_utc()),
    }
    await db.goals.update_one({"user_id": user["id"]}, {"$set": doc}, upsert=True)
    return GoalOut(**doc)


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
async def generate_ideas(req: IdeaReq, user: dict = Depends(get_current_user)):
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
    session_id = f"ideas-{user['id']}-{uuid.uuid4()}"
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system_msg).with_model(
        "anthropic", CLAUDE_MODEL
    )
    try:
        response = await chat.send_message(UserMessage(text=prompt))
        data = _extract_json(response)
        ideas = [IdeaItem(**i) for i in data.get("ideas", [])]
        return IdeaResp(ideas=ideas)
    except Exception as e:
        logger.exception("ideas generation failed")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)[:200]}")


# ---------- AI Content Generator ----------
@api_router.post("/ai/content", response_model=ContentResp)
async def generate_content(req: ContentReq, user: dict = Depends(get_current_user)):
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
    session_id = f"content-{user['id']}-{uuid.uuid4()}"
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system_msg).with_model(
        "anthropic", CLAUDE_MODEL
    )
    try:
        response = await chat.send_message(UserMessage(text=prompt))
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
async def coach_chat(req: CoachReq, user: dict = Depends(get_current_user)):
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

    # LlmChat with stable session_id => library handles multi-turn memory
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=COACH_SYSTEM).with_model(
        "anthropic", CLAUDE_MODEL
    )
    try:
        reply = await chat.send_message(UserMessage(text=req.message))
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
async def list_sessions(user: dict = Depends(get_current_user)):
    sessions = await db.coach_sessions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    return [CoachSession(id=s["id"], title=s["title"], updated_at=s["updated_at"]) for s in sessions]


@api_router.get("/ai/coach/sessions/{session_id}/messages", response_model=List[CoachMessage])
async def session_messages(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.coach_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = await db.coach_messages.find(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    return [CoachMessage(role=m["role"], content=m["content"], created_at=m["created_at"]) for m in msgs]


# ---------- DCA Simulator ----------
@api_router.post("/simulator/dca", response_model=DCAResp)
async def dca_simulator(req: DCAReq):
    monthly_rate = (req.apy_percent / 100.0) / 12.0
    months = req.years * 12
    value = 0.0
    contributed = 0.0
    series: List[DCAPoint] = []
    for m in range(1, months + 1):
        value = value * (1 + monthly_rate) + req.monthly_contribution
        contributed += req.monthly_contribution
        if m % max(1, months // 60) == 0 or m == months:
            series.append(DCAPoint(
                month=m, contributed=round(contributed, 2), value=round(value, 2),
            ))
    monthly_passive_at_end = value * monthly_rate
    return DCAResp(
        asset=req.asset,
        final_value=round(value, 2),
        total_contributed=round(contributed, 2),
        total_interest=round(value - contributed, 2),
        monthly_passive_at_end=round(monthly_passive_at_end, 2),
        series=series,
    )


# ---------- Health ----------
@api_router.get("/")
async def root():
    return {"app": "Autopilot - Passive Income OS", "status": "ok"}


# ---------- Wire up ----------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

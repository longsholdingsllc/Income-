from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, bcrypt, jwt
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timezone, timedelta
from lead_qualifier import qualify_lead

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGO = "HS256"
JWT_EXP_DAYS = 14
app = FastAPI(title="Autopilot - Passive Income OS")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)
logger = logging.getLogger("autopilot")
logging.basicConfig(level=logging.INFO)

def now_utc():
    return datetime.now(timezone.utc)
def iso(dt):
    return dt.isoformat()
def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def verify_password(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False
def create_jwt(user_id):
    if not JWT_SECRET:
        raise HTTPException(500, "JWT_SECRET missing")
    payload = {"sub": user_id, "iat": int(now_utc().timestamp()), "exp": int((now_utc()+timedelta(days=JWT_EXP_DAYS)).timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not creds or not creds.credentials:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
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
class LeadCapture(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    source: Optional[str] = "landing"

@api_router.post("/auth/register", response_model=AuthResp)
async def register(req: RegisterReq):
    existing = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Email already registered")
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
            "id": str(uuid.uuid4()), "user_id": user_id, "name": req.name.strip(),
            "email": req.email.lower(), "source": "register",
            "score": qualification.get("score"),
            "recommended_action": qualification.get("recommended_action"),
            "summary": qualification.get("summary"),
            "created_at": iso(now_utc()),
        })
    except Exception:
        pass
    logger.info("New user registered & scored: %s score=%s", doc["email"], doc.get("lead_score"))
    return AuthResp(token=create_jwt(user_id), user=UserOut(id=user_id, email=doc["email"], name=doc["name"], created_at=doc["created_at"]))

@api_router.post("/auth/login", response_model=AuthResp)
async def login(req: LoginReq):
    user = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return AuthResp(token=create_jwt(user["id"]), user=UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"]))

@api_router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])

@api_router.post("/leads", status_code=201)
async def capture_lead(req: LeadCapture):
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
    logger.info("Lead captured & scored: %s score=%s", doc["email"], doc.get("score"))
    return {"ok": True, "id": doc["id"], "score": doc["score"], "recommended_action": doc["recommended_action"], "summary": doc["summary"]}

@api_router.get("/")
async def root():
    return {"message": "Autopilot API", "lead_qualifier": "integrated"}

app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

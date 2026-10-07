from dotenv import load_dotenv
load_dotenv()

import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

ROOT_DIR = Path(__file__).parent
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
JWT_ALGORITHM = "HS256"
PROVIDERS = {
    "AWS": {"cpu": 2.13, "ram": 0.28, "storage": 6.68, "latency": 24, "sla": 99.99, "color": "#F59E0B"},
    "Azure": {"cpu": 1.99, "ram": 0.26, "storage": 6.26, "latency": 21, "sla": 99.95, "color": "#0284C7"},
    "GCP": {"cpu": 2.05, "ram": 0.27, "storage": 5.85, "latency": 22, "sla": 99.95, "color": "#34A853"},
}

app = FastAPI(title="CloudWeaver API")
api = APIRouter(prefix="/api")

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    region: str = Field(min_length=2, max_length=40)

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class WorkloadInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    vcpu: int = Field(ge=1, le=128)
    ram: int = Field(ge=1, le=512)
    storage: int = Field(ge=10, le=10000)
    hours: int = Field(ge=1, le=744)
    region: str

class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

def clean_user(doc):
    return {"id": str(doc["_id"]), "name": doc.get("name", ""), "email": doc["email"], "region": doc.get("region", "India"), "role": doc.get("role", "user")}

def token(user_id, email, kind="access"):
    lifetime = timedelta(minutes=30) if kind == "access" else timedelta(days=7)
    return jwt.encode({"sub": user_id, "email": email, "type": kind, "exp": datetime.now(timezone.utc) + lifetime}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, user):
    secure = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
    response.set_cookie("access_token", token(str(user["_id"]), user["email"]), httponly=True, secure=secure, samesite="none" if secure else "lax", max_age=1800, path="/")
    response.set_cookie("refresh_token", token(str(user["_id"]), user["email"], "refresh"), httponly=True, secure=secure, samesite="none" if secure else "lax", max_age=604800, path="/")

async def current_user(request: Request):
    raw = request.cookies.get("access_token")
    if not raw and request.headers.get("Authorization", "").startswith("Bearer "):
        raw = request.headers["Authorization"][7:]
    if not raw:
        raise HTTPException(401, "Please sign in to continue")
    try:
        payload = jwt.decode(raw, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access": raise HTTPException(401, "Invalid session")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user: raise HTTPException(401, "Account not found")
        return user
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(401, "Session expired")

def calculate(data):
    result = {}
    for name, rate in PROVIDERS.items():
        compute = (data.vcpu * rate["cpu"] + data.ram * rate["ram"]) * data.hours
        storage_fee = data.storage * rate["storage"]
        total = round(compute + storage_fee, 2)
        result[name] = {"provider": name, "monthly": total, "annual": round(total * 12, 2), "cpu_fee": round(data.vcpu * rate["cpu"] * data.hours, 2), "ram_fee": round(data.ram * rate["ram"] * data.hours, 2), "storage_fee": round(storage_fee, 2), "latency": rate["latency"], "sla": rate["sla"], "color": rate["color"]}
    lowest = min(result, key=lambda k: result[k]["monthly"])
    highest = max(result, key=lambda k: result[k]["monthly"])
    return {"providers": list(result.values()), "recommended": lowest, "most_expensive": highest, "monthly_savings": round(result[highest]["monthly"] - result[lowest]["monthly"], 2), "annual_savings": round((result[highest]["monthly"] - result[lowest]["monthly"]) * 12, 2)}

@api.get("/")
async def root(): return {"message": "CloudWeaver API is ready"}

@api.post("/auth/register")
async def register(data: RegisterInput, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}): raise HTTPException(409, "An account with this email already exists")
    user = {"name": data.name.strip(), "email": email, "password_hash": bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode(), "region": data.region, "role": "user", "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(user)
    set_auth_cookies(response, user)
    return clean_user(user)

@api.post("/auth/login")
async def login(data: LoginInput, response: Response):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user or not bcrypt.checkpw(data.password.encode(), user["password_hash"].encode()): raise HTTPException(401, "Email or password is incorrect")
    set_auth_cookies(response, user)
    return clean_user(user)

@api.get("/auth/me")
async def me(user=Depends(current_user)): return clean_user(user)

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/"); response.delete_cookie("refresh_token", path="/"); return {"ok": True}

@api.post("/auth/google")
async def google_login():
    raise HTTPException(501, "Google sign-in is ready for OAuth client configuration")

@api.post("/cost/analyze")
async def analyze(data: WorkloadInput, user=Depends(current_user)):
    calculated = calculate(data)
    doc = {"user_id": str(user["_id"]), "workload": data.model_dump(), "analysis": calculated, "created_at": datetime.now(timezone.utc).isoformat()}
    saved = await db.workloads.insert_one(doc)
    return {"id": str(saved.inserted_id), **calculated, "workload": data.model_dump()}

@api.get("/workloads")
async def workloads(user=Depends(current_user)):
    docs = await db.workloads.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(50)
    return [{"id": str(d["_id"]), "created_at": d["created_at"], "workload": d["workload"], "analysis": d["analysis"]} for d in docs]

@api.post("/assistant/chat")
async def assistant(data: ChatInput, user=Depends(current_user)):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=str(user["_id"]), system_message="You are CloudWeaver AI, a concise cloud cost optimization expert. Answer in plain language with practical AWS, Azure, GCP and migration advice.").with_model("gemini", "gemini-2.5-flash")
        reply = await chat.send_message(UserMessage(text=data.message))
        return {"reply": reply}
    except Exception as exc:
        logging.exception("assistant failure")
        raise HTTPException(503, "The assistant is temporarily unavailable") from exc

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.workloads.create_index([("user_id", 1), ("created_at", -1)])
    admin_email, admin_password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if admin_email and admin_password and not await db.users.find_one({"email": admin_email.lower()}):
        await db.users.insert_one({"name": "CloudWeaver Admin", "email": admin_email.lower(), "password_hash": bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode(), "region": "India", "role": "admin", "created_at": datetime.now(timezone.utc).isoformat()})

app.include_router(api)
origins = [os.environ["FRONTEND_URL"]] if os.environ.get("FRONTEND_URL") else [x for x in os.environ.get("CORS_ORIGINS", "").split(",") if x and x != "*"]
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown(): client.close()
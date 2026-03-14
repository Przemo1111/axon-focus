from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'axon_focus')]

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ========== Models ==========

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    email: str
    display_name: str
    total_focus_time: int = 0  # in minutes
    streak_days: int = 0
    last_focus_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    user_id: str
    email: str
    display_name: str

class UserUpdate(BaseModel):
    total_focus_time: Optional[int] = None
    streak_days: Optional[int] = None
    last_focus_date: Optional[str] = None

class FocusSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: int = 0  # in minutes
    date: str  # YYYY-MM-DD format
    completed: bool = False

class FocusSessionCreate(BaseModel):
    user_id: str
    duration: int  # planned duration in minutes

class FocusSessionEnd(BaseModel):
    actual_duration: int  # actual duration completed in minutes

class BlockedSite(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    site_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BlockedSiteCreate(BaseModel):
    user_id: str
    site_url: str

# ========== Auth Routes (Mock) ==========

@api_router.post("/auth/login", response_model=User)
async def mock_login(user_data: UserCreate):
    """Mock login - creates user if doesn't exist, returns user if exists"""
    existing_user = await db.users.find_one({"user_id": user_data.user_id})
    
    if existing_user:
        return User(**existing_user)
    
    # Create new user
    user = User(
        user_id=user_data.user_id,
        email=user_data.email,
        display_name=user_data.display_name
    )
    await db.users.insert_one(user.dict())
    return user

@api_router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Get user by user_id"""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**user)

@api_router.patch("/users/{user_id}", response_model=User)
async def update_user(user_id: str, user_update: UserUpdate):
    """Update user stats"""
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = await db.users.find_one({"user_id": user_id})
    return User(**user)

# ========== Focus Session Routes ==========

@api_router.post("/focus-sessions", response_model=FocusSession)
async def start_focus_session(session_data: FocusSessionCreate):
    """Start a new focus session"""
    now = datetime.utcnow()
    session = FocusSession(
        user_id=session_data.user_id,
        start_time=now,
        duration=session_data.duration,
        date=now.strftime("%Y-%m-%d"),
        completed=False
    )
    await db.focus_sessions.insert_one(session.dict())
    return session

@api_router.patch("/focus-sessions/{session_id}/end", response_model=FocusSession)
async def end_focus_session(session_id: str, end_data: FocusSessionEnd):
    """End a focus session and update user stats"""
    session = await db.focus_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    now = datetime.utcnow()
    
    # Update session
    await db.focus_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "end_time": now,
            "duration": end_data.actual_duration,
            "completed": True
        }}
    )
    
    # Get user and update stats
    user = await db.users.find_one({"user_id": session["user_id"]})
    if user:
        today = now.strftime("%Y-%m-%d")
        new_total_time = user.get("total_focus_time", 0) + end_data.actual_duration
        
        # Calculate streak
        last_focus_date = user.get("last_focus_date")
        current_streak = user.get("streak_days", 0)
        
        # Get today's total focus time
        today_sessions = await db.focus_sessions.find({
            "user_id": session["user_id"],
            "date": today,
            "completed": True
        }).to_list(1000)
        
        today_total = sum(s.get("duration", 0) for s in today_sessions) + end_data.actual_duration
        
        # Update streak logic
        if today_total >= 30:  # 30 minutes threshold
            if last_focus_date:
                last_date = datetime.strptime(last_focus_date, "%Y-%m-%d").date()
                today_date = datetime.strptime(today, "%Y-%m-%d").date()
                diff = (today_date - last_date).days
                
                if diff == 0:
                    # Same day, streak already counted
                    pass
                elif diff == 1:
                    # Consecutive day, increment streak
                    current_streak += 1
                else:
                    # Streak broken, reset to 1
                    current_streak = 1
            else:
                # First focus session ever
                current_streak = 1
        
        await db.users.update_one(
            {"user_id": session["user_id"]},
            {"$set": {
                "total_focus_time": new_total_time,
                "streak_days": current_streak,
                "last_focus_date": today
            }}
        )
    
    updated_session = await db.focus_sessions.find_one({"id": session_id})
    return FocusSession(**updated_session)

@api_router.get("/focus-sessions/{user_id}", response_model=List[FocusSession])
async def get_user_sessions(user_id: str, days: int = 7):
    """Get user's focus sessions for the last N days"""
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    sessions = await db.focus_sessions.find({
        "user_id": user_id,
        "date": {"$gte": start_date},
        "completed": True
    }).sort("start_time", -1).to_list(1000)
    
    return [FocusSession(**s) for s in sessions]

@api_router.get("/focus-sessions/{user_id}/today", response_model=dict)
async def get_today_stats(user_id: str):
    """Get today's focus stats for a user"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    sessions = await db.focus_sessions.find({
        "user_id": user_id,
        "date": today,
        "completed": True
    }).to_list(1000)
    
    total_minutes = sum(s.get("duration", 0) for s in sessions)
    session_count = len(sessions)
    
    return {
        "date": today,
        "total_minutes": total_minutes,
        "session_count": session_count
    }

@api_router.get("/focus-sessions/{user_id}/weekly", response_model=List[dict])
async def get_weekly_stats(user_id: str):
    """Get weekly focus stats for charts"""
    result = []
    
    for i in range(7):
        date = (datetime.utcnow() - timedelta(days=6-i)).strftime("%Y-%m-%d")
        sessions = await db.focus_sessions.find({
            "user_id": user_id,
            "date": date,
            "completed": True
        }).to_list(1000)
        
        total_minutes = sum(s.get("duration", 0) for s in sessions)
        day_name = (datetime.utcnow() - timedelta(days=6-i)).strftime("%a")
        
        result.append({
            "date": date,
            "day": day_name,
            "minutes": total_minutes
        })
    
    return result

# ========== Blocked Sites Routes ==========

@api_router.post("/blocked-sites", response_model=BlockedSite)
async def add_blocked_site(site_data: BlockedSiteCreate):
    """Add a site to the block list"""
    # Check if already exists
    existing = await db.blocked_sites.find_one({
        "user_id": site_data.user_id,
        "site_url": site_data.site_url
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="Site already blocked")
    
    site = BlockedSite(
        user_id=site_data.user_id,
        site_url=site_data.site_url
    )
    await db.blocked_sites.insert_one(site.dict())
    return site

@api_router.get("/blocked-sites/{user_id}", response_model=List[BlockedSite])
async def get_blocked_sites(user_id: str):
    """Get all blocked sites for a user"""
    sites = await db.blocked_sites.find({"user_id": user_id}).to_list(1000)
    return [BlockedSite(**s) for s in sites]

@api_router.delete("/blocked-sites/{site_id}")
async def remove_blocked_site(site_id: str):
    """Remove a site from the block list"""
    result = await db.blocked_sites.delete_one({"id": site_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Site not found")
    
    return {"message": "Site removed successfully"}

# ========== Health Check ==========

@api_router.get("/")
async def root():
    return {"message": "Axon Focus API is running"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

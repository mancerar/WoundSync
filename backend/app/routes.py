"""Wound profile API endpoints"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from .models import WoundProfile, WoundRecord

router = APIRouter(prefix="/api", tags=["wound_profiles"])

# Pydantic models
class WoundProfileCreate(BaseModel):
    name: str
    location: Optional[str] = None
    wound_type: Optional[str] = None
    notes: Optional[str] = None

def calculate_streak(records):
    """Calculate current photo upload streak"""
    if not records:
        return 0
    
    sorted_records = sorted(records, key=lambda r: r.recorded_at, reverse=True)
    streak = 1
    
    for i in range(len(sorted_records) - 1):
        current = sorted_records[i].recorded_at
        previous = sorted_records[i + 1].recorded_at
        days_diff = (current.date() - previous.date()).days
        
        # Allow up to 3 days between uploads to maintain streak
        if days_diff <= 3:
            streak += 1
        else:
            break
    
    return streak

def get_achievements(profile, records):
    """Calculate achievements/badges for a wound profile"""
    achievements = []
    
    if not records:
        return achievements
    
    # First photo achievement
    if len(records) >= 1:
        achievements.append({"id": "first_photo", "name": "First Step", "icon": "📸", "description": "Took your first wound photo"})
    
    # Consistency achievements
    if len(records) >= 3:
        achievements.append({"id": "consistent_3", "name": "Getting Consistent", "icon": "⭐", "description": "3 photos tracked"})
    if len(records) >= 7:
        achievements.append({"id": "week_warrior", "name": "Week Warrior", "icon": "🏆", "description": "7 photos tracked"})
    if len(records) >= 14:
        achievements.append({"id": "two_week_champ", "name": "Two Week Champion", "icon": "🥇", "description": "14 photos tracked"})
    
    # Healing progress achievements
    sorted_records = sorted(records, key=lambda r: r.recorded_at)
    if len(sorted_records) >= 2:
        first_area = sorted_records[0].area_cm2
        latest_area = sorted_records[-1].area_cm2
        reduction_pct = ((first_area - latest_area) / first_area * 100) if first_area > 0 else 0
        
        if reduction_pct >= 25:
            achievements.append({"id": "healing_25", "name": "Quarter Healed", "icon": "💪", "description": "25% wound size reduction"})
        if reduction_pct >= 50:
            achievements.append({"id": "healing_50", "name": "Halfway There", "icon": "🎯", "description": "50% wound size reduction"})
        if reduction_pct >= 75:
            achievements.append({"id": "healing_75", "name": "Almost Done", "icon": "✨", "description": "75% wound size reduction"})
        if reduction_pct >= 90:
            achievements.append({"id": "healing_90", "name": "Nearly Healed", "icon": "🌟", "description": "90% wound size reduction"})
    
    # Streak achievements
    streak = calculate_streak(records)
    if streak >= 3:
        achievements.append({"id": "streak_3", "name": "On a Roll", "icon": "🔥", "description": "3-day streak"})
    if streak >= 7:
        achievements.append({"id": "streak_7", "name": "Week Streak", "icon": "🔥🔥", "description": "7-day streak"})
    
    return achievements

@router.get("/profiles")
def get_wound_profiles(user_id: str = "demo_user", db: Session = Depends(get_db)):
    """Get all wound profiles for a user"""
    profiles = db.query(WoundProfile).filter(
        WoundProfile.user_id == user_id,
        WoundProfile.is_active == 1
    ).all()
    
    result = []
    for p in profiles:
        streak = calculate_streak(p.records)
        achievements = get_achievements(p, p.records)
        
        result.append({
            "id": p.id,
            "name": p.name,
            "location": p.location,
            "wound_type": p.wound_type,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "notes": p.notes,
            "record_count": len(p.records),
            "is_active": p.is_active,
            "streak": streak,
            "achievement_count": len(achievements)
        })
    
    return {"ok": True, "profiles": result}


@router.post("/profiles")
def create_wound_profile(
    profile: WoundProfileCreate,
    user_id: str = "demo_user",
    db: Session = Depends(get_db)
):
    """Create a new wound profile"""
    new_profile = WoundProfile(
        user_id=user_id,
        name=profile.name,
        location=profile.location,
        wound_type=profile.wound_type,
        notes=profile.notes,
        start_date=datetime.utcnow(),
        is_active=1
    )
    
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    
    return {
        "ok": True,
        "profile": {
            "id": new_profile.id,
            "name": new_profile.name,
            "location": new_profile.location,
            "wound_type": new_profile.wound_type,
            "start_date": new_profile.start_date.isoformat(),
            "notes": new_profile.notes
        }
    }


@router.get("/profiles/{profile_id}")
def get_wound_profile(profile_id: int, db: Session = Depends(get_db)):
    """Get a specific wound profile with all records"""
    profile = db.query(WoundProfile).filter(WoundProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    records = []
    for r in profile.records:
        records.append({
            "id": r.id,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
            "length_cm": r.length_cm,
            "width_cm": r.width_cm,
            "area_cm2": r.area_cm2,
            "healing_stage": r.healing_stage,
            "severity": r.severity,
            "infection_risk": r.infection_risk,
            "confidence": r.confidence
        })
    
    # Calculate gamification stats
    streak = calculate_streak(profile.records)
    achievements = get_achievements(profile, profile.records)
    
    # Calculate healing prediction
    healing_prediction = None
    if len(profile.records) >= 2:
        sorted_records = sorted(profile.records, key=lambda x: x.recorded_at)
        first = sorted_records[0]
        latest = sorted_records[-1]
        days_elapsed = (latest.recorded_at - first.recorded_at).days
        
        if days_elapsed > 0:
            area_change = first.area_cm2 - latest.area_cm2
            daily_rate = area_change / days_elapsed
            
            if daily_rate > 0 and latest.area_cm2 > 0:
                days_to_heal = int(latest.area_cm2 / daily_rate)
                predicted_date = (latest.recorded_at + timedelta(days=days_to_heal)).date().isoformat()
                healing_prediction = {
                    "days_remaining": days_to_heal,
                    "predicted_date": predicted_date,
                    "daily_reduction_cm2": round(daily_rate, 3),
                    "current_healing_rate": "good" if daily_rate > 0.1 else "moderate"
                }
    
    return {
        "ok": True,
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "location": profile.location,
            "wound_type": profile.wound_type,
            "start_date": profile.start_date.isoformat() if profile.start_date else None,
            "notes": profile.notes,
            "record_count": len(records),
            "records": records,
            "streak": streak,
            "achievements": achievements,
            "healing_prediction": healing_prediction
        }
    }


@router.delete("/profiles/{profile_id}")
def delete_wound_profile(profile_id: int, db: Session = Depends(get_db)):
    """Archive a wound profile"""
    profile = db.query(WoundProfile).filter(WoundProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile.is_active = 0
    db.commit()
    
    return {"ok": True, "message": "Profile archived"}


@router.post("/profiles/seed")
def seed_placeholder_data(user_id: str = "demo_user", db: Session = Depends(get_db)):
    """Create placeholder wound profiles with sample data for testing"""
    
    # Check if data already exists
    existing = db.query(WoundProfile).filter(WoundProfile.user_id == user_id).count()
    if existing > 0:
        return {"ok": True, "message": "Placeholder data already exists", "count": existing}
    
    # Create 3 sample wound profiles
    wounds = [
        {
            "name": "Left Knee Scrape",
            "location": "Left Knee",
            "wound_type": "Abrasion",
            "notes": "Fell while biking on Jan 10",
            "records": [
                {"days_ago": 7, "area": 4.5, "stage": "inflammatory", "severity": "moderate", "infection_risk": "low"},
                {"days_ago": 4, "area": 3.2, "stage": "inflammatory", "severity": "moderate", "infection_risk": "low"},
                {"days_ago": 1, "area": 2.1, "stage": "proliferative", "severity": "mild", "infection_risk": "low"},
            ]
        },
        {
            "name": "Right Arm Cut",
            "location": "Right Forearm",
            "wound_type": "Laceration",
            "notes": "Kitchen accident on Jan 12",
            "records": [
                {"days_ago": 5, "area": 2.8, "stage": "inflammatory", "severity": "moderate", "infection_risk": "moderate"},
                {"days_ago": 2, "area": 2.3, "stage": "proliferative", "severity": "mild", "infection_risk": "low"},
            ]
        },
        {
            "name": "Ankle Blister",
            "location": "Right Ankle",
            "wound_type": "Blister",
            "notes": "New hiking boots",
            "records": [
                {"days_ago": 3, "area": 1.5, "stage": "inflammatory", "severity": "mild", "infection_risk": "low"},
                {"days_ago": 0, "area": 0.8, "stage": "proliferative", "severity": "mild", "infection_risk": "low"},
            ]
        }
    ]
    
    for wound_data in wounds:
        # Create profile
        profile = WoundProfile(
            user_id=user_id,
            name=wound_data["name"],
            location=wound_data["location"],
            wound_type=wound_data["wound_type"],
            notes=wound_data["notes"],
            start_date=datetime.utcnow() - timedelta(days=wound_data["records"][0]["days_ago"]),
            is_active=1
        )
        db.add(profile)
        db.flush()  # Get the profile ID
        
        # Create records
        for rec_data in wound_data["records"]:
            record = WoundRecord(
                profile_id=profile.id,
                recorded_at=datetime.utcnow() - timedelta(days=rec_data["days_ago"]),
                length_cm=round(rec_data["area"] * 0.7, 1),  # Approximate from area
                width_cm=round(rec_data["area"] / 0.7, 1),
                area_cm2=rec_data["area"],
                confidence=0.85,
                healing_stage=rec_data["stage"],
                severity=rec_data["severity"],
                infection_risk=rec_data["infection_risk"],
                redness_level=0.3 if rec_data["infection_risk"] == "low" else 0.6
            )
            db.add(record)
    
    db.commit()
    
    return {"ok": True, "message": "Created 3 placeholder wound profiles with sample tracking data", "count": 3}

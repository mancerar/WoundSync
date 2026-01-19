"""Chart data generation for wound tracking metrics"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import WoundProfile

router = APIRouter(prefix="/api/charts", tags=["charts"])

@router.get("/metrics/{profile_id}")
def get_metrics_chart_data(profile_id: int, db: Session = Depends(get_db)):
    """Get time-series data for wound metrics (size, color, infection risk)"""
    profile = db.query(WoundProfile).filter(WoundProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    sorted_records = sorted(profile.records, key=lambda x: x.recorded_at)
    
    # Build chart datasets
    dates = []
    area_data = []
    length_data = []
    width_data = []
    infection_risk_data = []
    redness_data = []
    
    for r in sorted_records:
        dates.append(r.recorded_at.isoformat())
        area_data.append(r.area_cm2)
        length_data.append(r.length_cm)
        width_data.append(r.width_cm)
        
        # Convert infection risk to numeric (low=1, moderate=2, high=3)
        if isinstance(r.infection_risk, str):
            risk_map = {"low": 1, "moderate": 2, "high": 3}
            infection_risk_data.append(risk_map.get(r.infection_risk.lower(), 1))
        else:
            infection_risk_data.append(1)
        
        # Convert redness to numeric
        if isinstance(r.redness_level, str):
            redness_map = {"minimal": 1, "moderate": 2, "high": 3}
            redness_data.append(redness_map.get(r.redness_level.lower(), 1))
        elif isinstance(r.redness_level, (int, float)):
            # If it's already a number, use it directly (clamped to 1-3)
            redness_data.append(int(max(1, min(3, r.redness_level))))
        else:
            redness_data.append(1)
    
    return {
        "ok": True,
        "data": {
            "dates": dates,
            "area_cm2": area_data,
            "length_cm": length_data,
            "width_cm": width_data,
            "infection_risk": infection_risk_data,
            "redness_level": redness_data,
            "record_count": len(sorted_records)
        }
    }

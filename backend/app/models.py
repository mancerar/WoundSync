"""Database models for WoundSync"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class WoundProfile(Base):
    """Model for wound profiles"""
    __tablename__ = "wound_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)  # Will link to Firebase user ID later
    name = Column(String, nullable=False)  # e.g., "Left Knee", "Right Arm"
    location = Column(String)  # Body location
    wound_type = Column(String)  # e.g., "Cut", "Burn", "Surgical"
    start_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)  # 1 = active, 0 = archived
    notes = Column(Text, nullable=True)
    
    # Relationship to wound records
    records = relationship("WoundRecord", back_populates="profile", cascade="all, delete-orphan")

class WoundRecord(Base):
    """Model for individual wound analysis records"""
    __tablename__ = "wound_records"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("wound_profiles.id"), nullable=False)
    
    # Analysis timestamp
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    # Image data
    image_filename = Column(String)
    image_base64 = Column(Text, nullable=True)  # Store image as base64
    
    # Measurements
    length_cm = Column(Float)
    width_cm = Column(Float)
    area_cm2 = Column(Float)
    perimeter_cm = Column(Float)
    
    # Analysis results
    confidence = Column(Float)
    healing_stage = Column(String)  # e.g., "inflammatory", "proliferative"
    severity = Column(String)  # e.g., "mild", "moderate", "severe"
    infection_risk = Column(String)  # e.g., "low", "moderate", "high"
    
    # Color analysis
    redness_level = Column(Float)
    color_description = Column(String)
    
    # Complete analysis JSON
    full_analysis = Column(Text)  # JSON string of complete analysis
    
    # Relationship
    profile = relationship("WoundProfile", back_populates="records")

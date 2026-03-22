# this file creates an empty database for processung in another file
from sqlalchemy import create_engine, Column, String, Text, DateTime, Float
from sqlalchemy.dialects.sqlite import JSON
# sqlalchemy lets me work with databases using python objects
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timezone



SQL_DATABASE = "sqlite:///../wound.db" #database URL
# sqlite is being used with sqlalchemy, creates a database in folder above

db_engine = create_engine( #craetes an empty databae with the database name above
    SQL_DATABASE, 
    connect_args={"check_same_thread": False} #allows multiple threads to database (multithreading)
) 

Session = sessionmaker(autoflush=False, bind=db_engine)
#session maker gives every connection their own workspace in the database

Base = declarative_base() #parent

def get_db(): #function provides database sessions when called
    db = Session()
    try:
        yield db
    finally:
        db.close()


# ── Local wound profile (used when DynamoDB is not configured) ──────────────
class LocalWound(Base):
    __tablename__ = "local_wounds"
    wound_id  = Column(String, primary_key=True)
    user_id   = Column(String, nullable=False, index=True)
    name      = Column(String, default="Wound")
    timestamp = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())


# ── Local wound image entry (used when DynamoDB is not configured) ──────────
class LocalWoundImage(Base):
    __tablename__ = "local_wound_images"
    image_id      = Column(String, primary_key=True)          # timestamp-based key
    user_id       = Column(String, nullable=False, index=True)
    wound_id      = Column(String, nullable=False, index=True)
    timestamp     = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    healing_score = Column(Float, default=0.0)
    analysis      = Column(Text, default="{}")                # JSON string
    image_data    = Column(Text, default=None)                # base64 annotated image

# ── Create tables (no-op if already exists) & migrate missing columns ───────
Base.metadata.create_all(db_engine)

def _migrate():
    """Add columns that didn't exist in older DB versions."""
    with db_engine.connect() as conn:
        existing = {row[1] for row in conn.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(local_wound_images)")
        )}
        if "image_data" not in existing:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE local_wound_images ADD COLUMN image_data TEXT"
            ))
            conn.commit()

try:
    _migrate()
except Exception:
    pass

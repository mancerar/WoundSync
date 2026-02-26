import base64
import io
import json
import logging
import os
import tempfile
import boto3
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key


import uuid
import numpy as np
import requests
from fastapi import FastAPI, File, UploadFile, Query, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.security import require_auth


from decimal import Decimal



logger = logging.getLogger("woundsync-backend")
logging.basicConfig(level=logging.INFO)

# Import wound analyzer for comprehensive analysis
try:
    from .wound_analyzer import analyze_wound_image
    logger.info("✓ Comprehensive wound analyzer loaded successfully")
except ImportError as e:
    logger.warning(f"✗ Wound analyzer not available: {e}")
    analyze_wound_image = None

# Import database and models
from .database import Base, db_engine
from .models import WoundProfile, WoundRecord
from .routes import router as profile_router
from .charts import router as charts_router

# Create database tables
Base.metadata.create_all(bind=db_engine)
logger.info("✓ Database tables created")

app = FastAPI(title="WoundSync Backend (Roboflow + Zoom-Resistant Heuristics)")

# Include wound profile routes
app.include_router(profile_router)
app.include_router(charts_router)

# --- CORS (adjust for deployment) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",

        # Capacitor / iOS WebView origins:
        "capacitor://localhost",
        "ionic://localhost",
        "http://localhost",
        "http://localhost:8100",

        # Your LAN UI (optional, if you ever run UI on LAN):
        "http://192.168.86.33:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default

from dotenv import load_dotenv
load_dotenv()  # loads backend/.env when running from backend folder

MIN_CONFIDENCE = _env_float("MIN_CONFIDENCE", 0.35)
MAX_IMAGE_SIDE = _env_int("MAX_IMAGE_SIDE", 1600)


# ---------------------------
# Image helpers
# ---------------------------
def preprocess_image(image_bytes: bytes, max_side: int = 1600) -> Tuple[Image.Image, bytes]:
    """
    - Apply EXIF orientation correction
    - Downscale large images for faster inference while keeping detail
    Returns (PIL image RGB, jpeg_bytes used for inference + analysis)
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    w, h = img.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return img, buf.getvalue()


def photo_quality(img: Image.Image) -> Dict[str, Any]:
    """
    Simple, cheap quality checks:
    - brightness
    - edge_strength as a blur proxy
    """
    rgb = np.array(img.convert("RGB"), dtype=np.float32)
    gray = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) / 255.0
    brightness = float(np.mean(gray))

    edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_strength = float(np.mean(np.array(edges, dtype=np.float32)) / 255.0)

    exposure = "OK"
    if brightness < 0.22:
        exposure = "Too Dark"
    elif brightness > 0.88:
        exposure = "Overexposed"

    sharpness = "OK"
    if edge_strength < 0.03:
        sharpness = "Blurry"

    return {
        "brightness": round(brightness, 3),
        "edge_strength": round(edge_strength, 3),
        "exposure_label": exposure,
        "sharpness_label": sharpness,
    }


# ---------------------------
# Roboflow Model inference (currently active)
# ---------------------------
def roboflow_workflow_infer(image_bytes: bytes) -> Dict[str, Any]:
    """
    Infers using Roboflow Model (direct model endpoint).
    Can be switched to Workflow inference when workflow is set up.
    """
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    model_id = os.getenv("ROBOFLOW_MODEL_ID", "").strip()
    api_url = os.getenv("ROBOFLOW_API_URL", "https://serverless.roboflow.com").strip().rstrip("/")

    if not api_key:
        raise RuntimeError("Missing ROBOFLOW_API_KEY environment variable.")
    
    if not model_id:
        raise RuntimeError("Missing ROBOFLOW_MODEL_ID environment variable.")
    
    # Model inference endpoint - API key goes in URL for detect.roboflow.com
    url = f"{api_url}/{model_id}?api_key={api_key}"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # For detect.roboflow.com, send the base64 string directly
    r = requests.post(url, data=b64, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(f"Roboflow error {r.status_code}: {r.text}")
    return r.json()


# ---------------------------
# Roboflow Workflow inference (for future use - currently commented out)
# ---------------------------
# def roboflow_workflow_infer(image_bytes: bytes) -> Dict[str, Any]:
#     """
#     Infers using Roboflow Workflow endpoint.
#     Uncomment this function and comment out the model version above when workflow is ready.
#     """
#     api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
#     workspace = os.getenv("ROBOFLOW_WORKSPACE", "").strip()
#     workflow_id = os.getenv("ROBOFLOW_WORKFLOW_ID", "").strip()
#     api_url = os.getenv("ROBOFLOW_API_URL", "https://serverless.roboflow.com").strip().rstrip("/")
#
#     if not api_key or not workspace or not workflow_id:
#         raise RuntimeError(
#             "Missing Roboflow env vars. Need ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_WORKFLOW_ID."
#         )
#
#     # Workflows endpoint
#     url = f"{api_url}/infer/workflows/{workspace}/{workflow_id}"
#     b64 = base64.b64encode(image_bytes).decode("utf-8")
#     payload = {
#         "api_key": api_key,
#         "inputs": {
#             "image": {"type": "base64", "value": b64}
#         },
#     }
#
#     r = requests.post(url, json=payload, timeout=45)
#     if r.status_code != 200:
#         raise RuntimeError(f"Roboflow error {r.status_code}: {r.text}")
#     return r.json()


# ---------------------------
# Parsing predictions (robust)
# ---------------------------
def _is_pred_list(lst: Any) -> bool:
    if not isinstance(lst, list) or not lst:
        return False
    if not isinstance(lst[0], dict):
        return False
    for d in lst[:10]:
        if isinstance(d, dict) and ("confidence" in d or "score" in d):
            return True
    return False


def extract_prediction_lists(obj: Any) -> List[List[Dict[str, Any]]]:
    found: List[List[Dict[str, Any]]] = []

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, list) and (k.lower() == "predictions" or _is_pred_list(v)):
                    if _is_pred_list(v):
                        found.append(v)  # type: ignore
                else:
                    walk(v)
        elif isinstance(x, list):
            for it in x:
                walk(it)

    walk(obj)
    return found


def pred_conf(p: Dict[str, Any]) -> float:
    try:
        return float(p.get("confidence", p.get("score", 0.0)))
    except Exception:
        return 0.0


def pred_class(p: Dict[str, Any]) -> str:
    for k in ["class", "class_name", "label", "name"]:
        if k in p and isinstance(p[k], str):
            return p[k]
    return "wound"


def bbox_area_of_pred(p: Dict[str, Any], img_w: int, img_h: int) -> float:
    """Calculate bounding box area for a prediction."""
    bb = parse_bbox(p, img_w, img_h)
    if not bb:
        return 0.0
    x1, y1, x2, y2 = bb
    return float((x2 - x1) * (y2 - y1))


def parse_bbox(p: Dict[str, Any], img_w: int, img_h: int) -> Optional[Tuple[int, int, int, int]]:
    # center x/y + width/height
    if all(k in p for k in ["x", "y", "width", "height"]):
        try:
            cx = float(p["x"])
            cy = float(p["y"])
            w = float(p["width"])
            h = float(p["height"])
            x1 = int(round(cx - w / 2))
            y1 = int(round(cy - h / 2))
            x2 = int(round(cx + w / 2))
            y2 = int(round(cy + h / 2))
            x1 = max(0, min(img_w - 1, x1))
            y1 = max(0, min(img_h - 1, y1))
            x2 = max(0, min(img_w, x2))
            y2 = max(0, min(img_h, y2))
            if x2 <= x1 or y2 <= y1:
                return None
            return (x1, y1, x2, y2)
        except Exception:
            return None

    bb = p.get("bbox")
    if isinstance(bb, dict):
        try:
            x1 = int(bb.get("x1", bb.get("left", 0)))
            y1 = int(bb.get("y1", bb.get("top", 0)))
            x2 = int(bb.get("x2", bb.get("right", 0)))
            y2 = int(bb.get("y2", bb.get("bottom", 0)))
            x1 = max(0, min(img_w - 1, x1))
            y1 = max(0, min(img_h - 1, y1))
            x2 = max(0, min(img_w, x2))
            y2 = max(0, min(img_h, y2))
            if x2 <= x1 or y2 <= y1:
                return None
            return (x1, y1, x2, y2)
        except Exception:
            return None

    return None


def parse_polygon_points(p: Dict[str, Any]) -> Optional[List[Tuple[int, int]]]:
    candidates = []
    for key in ["points", "segmentation", "polygon"]:
        v = p.get(key)
        if v is not None:
            candidates.append(v)

    for v in candidates:
        if isinstance(v, dict) and "points" in v:
            v = v["points"]

        if isinstance(v, list) and v:
            pts: List[Tuple[int, int]] = []
            if isinstance(v[0], dict) and ("x" in v[0] and "y" in v[0]):
                try:
                    for d in v:
                        pts.append((int(round(float(d["x"]))), int(round(float(d["y"])))))
                    if len(pts) >= 3:
                        return pts
                except Exception:
                    pass
            if isinstance(v[0], (list, tuple)) and len(v[0]) >= 2:
                try:
                    for a in v:
                        pts.append((int(round(float(a[0]))), int(round(float(a[1])))))
                    if len(pts) >= 3:
                        return pts
                except Exception:
                    pass

    return None


# ---------------------------
# Mask + geometry
# ---------------------------
def polygon_area(points: List[Tuple[int, int]]) -> float:
    x = np.array([p[0] for p in points], dtype=np.float32)
    y = np.array([p[1] for p in points], dtype=np.float32)
    return float(0.5 * np.abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def make_mask(img_w: int, img_h: int, bbox: Tuple[int, int, int, int], poly: Optional[List[Tuple[int, int]]]) -> np.ndarray:
    if poly and len(poly) >= 3:
        m = Image.new("L", (img_w, img_h), 0)
        ImageDraw.Draw(m).polygon(poly, outline=1, fill=1)
        return np.array(m, dtype=np.uint8)

    x1, y1, x2, y2 = bbox
    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 1
    return mask


def mask_perimeter(mask: np.ndarray) -> int:
    """
    Approx boundary pixel count (scale-invariant when used as compactness).
    """
    m = mask.astype(np.uint8)
    up = np.roll(m, -1, axis=0)
    down = np.roll(m, 1, axis=0)
    left = np.roll(m, -1, axis=1)
    right = np.roll(m, 1, axis=1)
    inner = (m & up & down & left & right).astype(np.uint8)
    boundary = (m & (1 - inner)).astype(np.uint8)
    return int(boundary.sum())


# ---------------------------
# Color features (scale-free)
# ---------------------------
def color_features(rgb_pixels: np.ndarray) -> Dict[str, float]:
    """
    rgb_pixels: (N,3) uint8
    Returns robust-ish ratios. These DO NOT depend on zoom.
    """
    if rgb_pixels.size == 0:
        return {"redness_ratio": 0.0, "bleeding_ratio": 0.0, "yellowish_ratio": 0.0, "dark_ratio": 0.0}

    r = rgb_pixels[:, 0].astype(np.int32)
    g = rgb_pixels[:, 1].astype(np.int32)
    b = rgb_pixels[:, 2].astype(np.int32)

    # Redness: red dominates
    redish = (r > g + 25) & (r > b + 25) & (r > 85)

    # Bleeding-ish: strong saturated red
    bleeding = (r > 165) & (r > g + 55) & (r > b + 55)

    # Yellow-ish (weak signal)
    yellowish = (r > 160) & (g > 150) & (b < 135)

    # Dark core
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    dark = lum < 70

    n = float(len(r))
    return {
        "redness_ratio": float(redish.sum() / n),
        "bleeding_ratio": float(bleeding.sum() / n),
        "yellowish_ratio": float(yellowish.sum() / n),
        "dark_ratio": float(dark.sum() / n),
    }


# ---------------------------
# Zoom-resistant wound assessment
# ---------------------------
def compute_wound_assessment(
    img: Image.Image,
    bbox: Tuple[int, int, int, int],
    poly: Optional[List[Tuple[int, int]]],
    conf: float,
) -> Dict[str, Any]:
    """
    IMPORTANT DESIGN CHOICE:
    - Do NOT use "how big it is in the photo" to decide urgency (zoom problem).
    - Only use scale-free cues: shape ratios, fill ratio, color ratios, ring redness, dark core.
    """
    img_w, img_h = img.size
    arr = np.array(img.convert("RGB"), dtype=np.uint8)
    mask = make_mask(img_w, img_h, bbox, poly)

    x1, y1, x2, y2 = bbox
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)

    # Shape ratios (zoom-invariant)
    elongation = float(max(bw, bh) / (min(bw, bh) + 1e-6))          # long vs wide
    thickness_ratio = float(min(bw, bh) / (max(bw, bh) + 1e-6))     # 0..1 (thin if small)

    # Mask fill inside bbox (zoom-invariant)
    wound_area_px = float(mask.sum())
    bbox_area_px = float(bw * bh)
    fill_ratio = float(wound_area_px / (bbox_area_px + 1e-6))       # thin cut => small fill, scrape => higher fill

    # Boundary complexity (used lightly)
    perim = mask_perimeter(mask)
    compactness = float((perim * perim) / (wound_area_px + 1e-6))   # higher = more irregular / thin

    wound_pixels = arr[mask == 1]
    wound_cf = color_features(wound_pixels)

    # Surrounding ring redness (weak)
    pad = int(round(0.35 * max(bw, bh)))
    ex1 = max(0, x1 - pad)
    ey1 = max(0, y1 - pad)
    ex2 = min(img_w, x2 + pad)
    ey2 = min(img_h, y2 + pad)

    ring = np.zeros((img_h, img_w), dtype=np.uint8)
    ring[ey1:ey2, ex1:ex2] = 1
    ring[mask == 1] = 0
    ring_pixels = arr[ring == 1]
    ring_cf = color_features(ring_pixels)

    # Wound type (best-effort)
    looks_cut = (elongation >= 2.0 and fill_ratio <= 0.45) or (elongation >= 3.0)
    looks_scrape = (fill_ratio >= 0.55 and elongation <= 2.4) or (wound_cf["redness_ratio"] >= 0.18 and fill_ratio >= 0.45)

    if looks_cut and not looks_scrape:
        wound_type = "cut"
        summary = "This looks like a cut / laceration."
    elif looks_scrape and not looks_cut:
        wound_type = "scrape"
        summary = "This looks like a scrape / abrasion."
    else:
        wound_type = "uncertain"
        summary = "Wound detected, but the type is unclear from this photo."

    # -----------------------
    # Urgency scoring (NO size-in-frame!)
    # -----------------------
    score = 0.0

    # Bleeding cues
    if wound_cf["bleeding_ratio"] >= 0.06:
        score += 2.4
    elif wound_cf["bleeding_ratio"] >= 0.03:
        score += 1.6
    elif wound_cf["bleeding_ratio"] >= 0.015:
        score += 0.8

    # Dark core cues (depth/shadow proxy; imperfect)
    if wound_cf["dark_ratio"] >= 0.40:
        score += 2.2
    elif wound_cf["dark_ratio"] >= 0.25:
        score += 1.4
    elif wound_cf["dark_ratio"] >= 0.16:
        score += 0.7

    # "Wider" cuts are more concerning than thin papercuts (still zoom-invariant)
    # papercut: thickness_ratio tiny (e.g. 0.05–0.15)
    if wound_type == "cut":
        if thickness_ratio >= 0.38:
            score += 2.0
        elif thickness_ratio >= 0.28:
            score += 1.2
        elif thickness_ratio <= 0.14:
            score -= 0.6  # actively de-escalate thin cuts (fixes zoomed papercut panic)

    # Surrounding redness (weak, don’t over-weight)
    if ring_cf["redness_ratio"] >= 0.25:
        score += 0.7
    elif ring_cf["redness_ratio"] >= 0.18:
        score += 0.4

    # Yellow-ish (very weak)
    if wound_cf["yellowish_ratio"] >= 0.08:
        score += 0.5

    # Low confidence => don’t escalate; suggest retake instead
    if conf < 0.45:
        score -= 0.8

    # Map score -> urgency
    if score >= 4.0:
        urgency = "urgent"
    elif score >= 2.0:
        urgency = "soon"
    else:
        urgency = "home"

    # -----------------------
    # Guidance (practical + realistic)
    # -----------------------
    disclaimer = "Not a diagnosis. Image-only guidance can be wrong. If you’re worried, get checked in person."

    retake_tips: List[str] = []
    q = photo_quality(img)
    if q["exposure_label"] != "OK":
        retake_tips.append("Retake in bright, even indoor light (avoid harsh shadows / direct sun).")
    if q["sharpness_label"] != "OK":
        retake_tips.append("Hold steady and tap-to-focus on the wound (or rest your hand on a surface).")
    if conf < 0.55:
        retake_tips.append("Fill more of the frame with the wound, but keep edges visible and in focus (avoid extreme blur).")
    retake_tips.append("Avoid glare: wipe moisture and tilt slightly so light doesn’t reflect off shiny skin.")

    next_steps: List[str] = []
    tips: List[str] = []
    watch_for: List[str] = []

    # Common wound care (safe baseline)
    base_tips = [
        "Rinse with clean running water. Use mild soap around the area (don’t scrub inside a cut).",
        "Apply a thin layer of petroleum jelly. Cover with a non-stick dressing.",
        "Change dressing daily (or sooner if wet/dirty). Keep it clean and protected.",
        "Avoid hydrogen peroxide or alcohol repeatedly (can slow healing).",
    ]

    # Stitch/closure is about gaping depth + location + bleeding (NOT size in photo)
    if urgency == "urgent":
        next_steps.append("This photo has features that can sometimes be seen with a deeper/wider cut or active bleeding.")
        next_steps.append("Consider urgent care today—especially if the wound edges gape open, won’t stay closed, or bleeding persists.")
        tips.extend([
            "If bleeding: apply firm, steady pressure with clean gauze/cloth for 10 minutes without peeking.",
            "If the cut is gaping, don’t force it closed with tape—keep it covered until you’re seen.",
            "If the wound is dirty or you’re not up to date on tetanus shots, ask about a tetanus booster.",
        ])
        tips.extend(base_tips)
        watch_for.extend([
            "Bleeding that won’t stop after 10 minutes of firm pressure",
            "Wound edges gaping open, deep tissue visible, or new numbness/weakness",
            "Rapidly spreading redness, worsening pain, fever, thick/cloudy drainage, or red streaking",
        ])
    elif urgency == "soon":
        next_steps.append("This may be worth a same-day or next-day check if symptoms worsen or you’re unsure.")
        next_steps.append("If pain, swelling, warmth, or drainage increases instead of improving, get checked.")
        tips.extend(base_tips)
        tips.append("Retake a photo in ~24 hours in similar lighting to compare changes.")
        watch_for.extend([
            "Redness spreading outward day to day",
            "Pain increasing instead of improving",
            "Swelling, warmth, bad smell, or cloudy drainage",
        ])
    else:
        next_steps.append("This looks consistent with a more superficial wound in this photo (even if zoomed in).")
        next_steps.append("Home care + monitoring is reasonable if symptoms are mild and improving.")
        tips.extend(base_tips)
        if wound_type == "cut":
            tips.append("Thin cuts (papercuts) often look dramatic when zoomed—focus on symptoms and whether it’s closing.")
        if wound_type == "scrape":
            tips.append("Scrapes usually heal faster when kept slightly moist and covered (not dried out).")
        watch_for.extend([
            "Redness spreading, increasing pain, swelling, warmth",
            "Drainage, fever, or not improving over 48–72 hours",
        ])

    # Extra targeted notes
    if wound_type == "cut":
        tips.append("Cuts on face/hands, over joints, or from bites typically deserve clinician advice.")
    if wound_cf["bleeding_ratio"] >= 0.05:
        tips.append("Because there may be active bleeding, prioritize pressure + dressing first (ointment later).")

    # “why” explanation (for demo / transparency)
    context = {
        "confidence": round(float(conf), 3),
        "shape": {
            "elongation": round(elongation, 2),
            "thickness_ratio": round(thickness_ratio, 3),
            "fill_ratio": round(fill_ratio, 3),
            "compactness": round(compactness, 1),
        },
        "wound_color": {k: round(v, 3) for k, v in wound_cf.items()},
        "ring_color": {k: round(v, 3) for k, v in ring_cf.items()},
        "note": "Urgency is NOT based on wound size in the photo (zoom-safe). It uses shape + color cues instead.",
    }

    return {
        "summary": summary,
        "urgency": urgency,            # "home" | "soon" | "urgent"
        "wound_type": wound_type,      # "cut" | "scrape" | "uncertain"
        "disclaimer": disclaimer,
        "next_steps": next_steps,
        "tips": tips,
        "watch_for": watch_for,
        "retake_tips": retake_tips,
        "quality": q,
        "context": context,
    }
    
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

BUCKET_NAME = os.getenv("S3_BUCKET")

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "WoundSyncData").strip() or "WoundSyncData"

@app.get("/test-s3")
def test_s3():
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)
    return {"status": "connected", "objects": response.get("Contents", [])}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/wounds/{wound_id}/upload-url")
def generate_upload_url(
    wound_id: str,
    content_type: str = Query("image/jpeg"),
    #uid="demo-user"
    uid:str = Depends(require_auth)
):
    if not isinstance(content_type, str) or not content_type.strip():
        content_type = "image/jpeg"
    content_type = content_type.strip()
    key = f"{uid}/{wound_id}/{datetime.now(timezone.utc).isoformat()}.jpg"

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": key,
            "ContentType": content_type
        },
        ExpiresIn=300
    )

    return {
        "uploadUrl": upload_url,
        "imageKey": key
    }
    
@app.post("/wounds/{wound_id}/images")
def save_wound_metadata(
    wound_id: str,
    body: dict,
    #uid="demo-user"
    uid: str = Depends(require_auth)
):
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object")
        if "imageKey" not in body or not body.get("imageKey"):
            raise HTTPException(status_code=400, detail="Missing required field: imageKey")

        clean_body = json.loads(json.dumps(body), parse_float=Decimal)

        ts = clean_body.get("timestamp", datetime.now().isoformat())
        sk_value = clean_body.get("sk") or f"WOUND#{wound_id}#IMG#{ts}"

        item = {
            "userId": uid,
            "woundId": wound_id,
            "sk": sk_value,
            "timestamp": ts,
            "imageKey": clean_body["imageKey"],
            "healingScore": clean_body.get("healingScore", Decimal("0")),
            "analysis": clean_body.get("analysis", {}),
        }

        print("ITEM BEING SAVED:", item)

        response = table.put_item(Item=item)

        print("DYNAMO RESPONSE:", response)

        return {"ok": True}

    except Exception as e:
        print("🔥 DYNAMO ERROR:", str(e))
        return {"error": str(e)}


class CreateWoundBody(BaseModel):
    name: Optional[str] = None


@app.post("/wounds")
def create_wound_profile(
    body: Optional[CreateWoundBody] = None,
    uid: str = Depends(require_auth),
):
    
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        name = (body.name if body else None) or "New wound"
        slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.strip())[:50] or "wound"
        wound_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        ts = datetime.now(timezone.utc).isoformat()
        sk_value = f"WOUND#{wound_id}#PROFILE"

        item = {
            "userId": uid,
            "woundId": wound_id,
            "sk": sk_value,
            "timestamp": ts,
            "name": name[:200],
        }
        table.put_item(Item=item)
        return {"ok": True, "woundId": wound_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wounds")
def list_user_wounds(uid: str = Depends(require_auth)):
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        items = []
        try:
            resp = table.query(
                KeyConditionExpression=Key("userId").eq(uid) & Key("sk").begins_with("WOUND#")
            )
            items = resp.get("Items", [])

            while "LastEvaluatedKey" in resp:
                resp = table.query(
                    KeyConditionExpression=Key("userId").eq(uid) & Key("sk").begins_with("WOUND#"),
                    ExclusiveStartKey=resp["LastEvaluatedKey"]
                )
                items.extend(resp.get("Items", []))
        except Exception as qerr:
            logger.warning(f"Query by userId failed (table key may differ): {qerr}")
            items = []

        
        if not items:
            from boto3.dynamodb.conditions import Attr
            resp = table.scan(FilterExpression=Attr("userId").eq(uid) & Attr("sk").begins_with("WOUND#"))
            items = resp.get("Items", [])
            while resp.get("LastEvaluatedKey"):
                resp = table.scan(FilterExpression=Attr("userId").eq(uid) & Attr("sk").begins_with("WOUND#"), ExclusiveStartKey=resp.get("LastEvaluatedKey"))
                items.extend(resp.get("Items", []))

        
        wounds = {}

        for it in items:
            wid = it.get("woundId")
            ts = it.get("timestamp") or it.get("sk")
            sk = it.get("sk") or ""

            if not wid:
                continue

            entry = wounds.setdefault(
                wid,
                {"id": wid, "name": wid, "image_count": 0, "last_timestamp": None, "last_imageKey": None}
            )

            if "#IMG#" in sk or it.get("imageKey"):
                entry["image_count"] += 1
                if ts and (entry["last_timestamp"] is None or ts > entry["last_timestamp"]):
                    entry["last_timestamp"] = ts
                    entry["last_imageKey"] = it.get("imageKey")
            else:
               
                if it.get("name"):
                    entry["name"] = it["name"]
                if entry["last_timestamp"] is None and ts:
                    entry["last_timestamp"] = ts

        
        try:
            logger.info(f"/wounds raw items count={len(items)}; aggregated wounds={len(wounds)}")
            sample = list(wounds.values())[:5]
            logger.info(f"/wounds sample aggregated: {sample}")
        except Exception:
            pass

        return {"ok": True, "wounds": list(wounds.values())}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/wounds/{wound_id}/images")
def list_wound_images(wound_id: str, uid: str = Depends(require_auth)):
    
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        from boto3.dynamodb.conditions import Attr

        resp = table.scan(FilterExpression=Attr("userId").eq(uid) & Attr("woundId").eq(wound_id))
        items = resp.get("Items", [])
        while resp.get("LastEvaluatedKey"):
            resp = table.scan(FilterExpression=Attr("userId").eq(uid) & Attr("woundId").eq(wound_id), ExclusiveStartKey=resp.get("LastEvaluatedKey"))
            items.extend(resp.get("Items", []))

       
        def sort_key(itm):
            return itm.get("timestamp") or itm.get("created_at") or itm.get("sk") or ""

        items_sorted = sorted(items, key=sort_key, reverse=True)

       
        for it in items_sorted:
            key = it.get("imageKey")
            if key and isinstance(key, str) and key.startswith(str(uid)):
                try:
                    view_url = s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": BUCKET_NAME, "Key": key},
                        ExpiresIn=3600,
                    )
                    it["viewUrl"] = view_url
                except Exception:
                    pass

        return {"ok": True, "images": items_sorted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict")
async def predict(
    image: UploadFile = File(...),
    debug: bool = Query(False),
):
    logger.info("="*80)
    logger.info(f"📥 POST /predict - File: {image.filename}, Debug: {debug}")
    logger.info("="*80)
    try:
        image_bytes = await image.read()
        logger.info(f"📷 Image read: {len(image_bytes)} bytes")
        pil_img, infer_bytes = preprocess_image(image_bytes, max_side=MAX_IMAGE_SIDE)
        logger.info(f"🖼️ Preprocessed to {pil_img.size[0]}x{pil_img.size[1]}")

        # Use comprehensive wound analyzer if available
        if analyze_wound_image is not None:
            try:
                logger.info("Running comprehensive wound analysis...")
                
                # FIRST: Get Roboflow predictions for bounding box
                rf_json = roboflow_workflow_infer(infer_bytes)
                pred_lists = extract_prediction_lists(rf_json)
                all_preds: List[Dict[str, Any]] = []
                for lst in pred_lists:
                    for p in lst:
                        if isinstance(p, dict) and pred_conf(p) > 0:
                            all_preds.append(p)
                
                # Prefer wound-ish classes
                wound_preds = [p for p in all_preds if pred_class(p).lower() in ["wound", "abrasion", "cut", "laceration"]]
                candidates = wound_preds if wound_preds else all_preds
                
                # Get best prediction bbox
                roboflow_bbox = None
                roboflow_conf = 0.0
                if candidates:
                    img_w, img_h = pil_img.size
                    candidates_sorted = sorted(candidates, key=lambda p: (pred_conf(p), bbox_area_of_pred(p, img_w, img_h)), reverse=True)
                    best = candidates_sorted[0]
                    roboflow_conf = pred_conf(best)
                    roboflow_bbox = parse_bbox(best, img_w, img_h)
                    logger.info(f"✓ Roboflow detected wound with {roboflow_conf:.1%} confidence")
                
                # Save image temporarily for analysis
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_path = tmp_file.name
                    pil_img.save(tmp_path, format='JPEG', quality=95)
                
                # Create temp output directory for visual
                temp_output_dir = tempfile.mkdtemp()
                
                # Run comprehensive wound analysis (generates visual output)
                analysis_result = analyze_wound_image(
                    tmp_path,
                    pixels_per_cm=150.0,
                    save_visual=False,  # We'll create our own visual with Roboflow bbox
                    output_dir=temp_output_dir
                )
                
                # Create annotated image with Roboflow bounding box
                annotated_image_b64 = None
                if roboflow_bbox:
                    try:
                        import cv2
                        import numpy as np
                        # Load original image
                        img_np = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                        x1, y1, x2, y2 = roboflow_bbox
                        
                        # Draw green bounding box
                        cv2.rectangle(img_np, (x1, y1), (x2, y2), (0, 255, 0), 3)
                        
                        # Add measurements text
                        measurements = analysis_result.get("measurements", {})
                        length = measurements.get("length_cm", 0)
                        width = measurements.get("width_cm", 0)
                        area = measurements.get("area_cm2", 0)
                        text = f"LxW: {length:.1f}x{width:.1f} cm  |  Area: {area:.1f} cm^2"
                        
                        # Put text below the box
                        text_y = min(img_np.shape[0] - 10, y2 + 30)
                        cv2.putText(img_np, text, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                        
                        # Encode to base64
                        _, buffer = cv2.imencode('.jpg', img_np)
                        annotated_image_b64 = base64.b64encode(buffer).decode("utf-8")
                        logger.info(f"✓ Created annotated image with Roboflow bbox")
                    except Exception as e:
                        logger.error(f"Failed to create annotated image: {e}")
                
                # Clean up temp files
                try:
                    os.unlink(tmp_path)
                    if os.path.exists(temp_output_dir):
                        # Try to remove directory - may not be empty
                        try:
                            os.rmdir(temp_output_dir)
                        except:
                            import shutil
                            shutil.rmtree(temp_output_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Cleanup warning: {e}")
                
                # Check if wound was detected
                if not analysis_result.get("wound_detected", False):
                    return JSONResponse(
                        status_code=200,
                        content={
                            "ok": True,
                            "detected": False,
                            "confidence": analysis_result.get("confidence", 0.0),
                            "message": "No wound detected. Retake with better light and focus.",
                            "min_confidence": MIN_CONFIDENCE,
                            "analysis": analysis_result if debug else None,
                        },
                    )
                
                conf = analysis_result.get("confidence", 0.0)
                measurements = analysis_result.get("measurements", {})
                color_analysis = analysis_result.get("color_analysis", {})
                healing_assessment = analysis_result.get("healing_assessment", {})
                
                # Also get the heuristic assessment for additional context
                bbox = (0, 0, pil_img.width, pil_img.height)  # Default bbox
                heuristic_assessment = compute_wound_assessment(pil_img, bbox, None, conf=conf)
                
                # Combine comprehensive analysis with assessment
                return JSONResponse(
                    status_code=200,
                    content={
                        "ok": True,
                        "detected": True,
                        "confidence": conf,
                        "method": analysis_result.get("method", "Computer Vision"),
                        "annotated_image": annotated_image_b64,  # Base64 encoded annotated image
                        "measurements": {
                            "length_cm": measurements.get("length_cm", 0),
                            "width_cm": measurements.get("width_cm", 0),
                            "area_cm2": measurements.get("area_cm2", 0),
                            "perimeter_cm": measurements.get("perimeter_cm", 0),
                        },
                        "color_analysis": color_analysis,
                        "healing_assessment": healing_assessment,
                        "overall_assessment": analysis_result.get("overall_assessment", ""),
                        "recommendations": analysis_result.get("recommendations", {}),
                        "assessment": heuristic_assessment,  # Includes urgency and care tips
                        "pixels_per_cm": analysis_result.get("pixels_per_cm", 45.0),
                        "calibration": analysis_result.get("calibration", {}),
                        "min_confidence": MIN_CONFIDENCE,
                        "debug": analysis_result if debug else None,
                    },
                )
                
            except Exception as e:
                logger.warning(f"Comprehensive analysis failed ({e}), falling back to Roboflow only")
                # Fall through to original Roboflow workflow below
        
        # Original Roboflow workflow logic (fallback or when analyzer not available)
        rf_json = roboflow_workflow_infer(infer_bytes)
        pred_lists = extract_prediction_lists(rf_json)

        all_preds: List[Dict[str, Any]] = []
        for lst in pred_lists:
            for p in lst:
                if isinstance(p, dict) and pred_conf(p) > 0:
                    all_preds.append(p)

        # Prefer wound-ish classes if your model uses them; otherwise keep all
        wound_preds = [
            p for p in all_preds
            if pred_class(p).lower() in ["wound", "abrasion", "cut", "laceration"]
        ]
        candidates = wound_preds if wound_preds else all_preds

        if not candidates:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "detected": False,
                    "confidence": 0.0,
                    "message": "No predictions returned from the model.",
                    "min_confidence": MIN_CONFIDENCE,
                    "debug": rf_json if debug else None,
                },
            )

        img_w, img_h = pil_img.size

        def bbox_area_of(p: Dict[str, Any]) -> float:
            bb = parse_bbox(p, img_w, img_h)
            if not bb:
                return 0.0
            x1, y1, x2, y2 = bb
            return float((x2 - x1) * (y2 - y1))

        candidates_sorted = sorted(
            candidates,
            key=lambda p: (pred_conf(p), bbox_area_of(p)),
            reverse=True,
        )
        best = candidates_sorted[0]
        conf = pred_conf(best)

        if conf < MIN_CONFIDENCE:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "detected": False,
                    "confidence": conf,
                    "message": "Not confident enough. Retake with better light and focus.",
                    "min_confidence": MIN_CONFIDENCE,
                    "debug": rf_json if debug else None,
                },
            )

        bbox = parse_bbox(best, img_w, img_h)
        poly = parse_polygon_points(best)

        if not bbox:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "detected": True,
                    "confidence": conf,
                    "message": "Prediction found but bbox missing. Check workflow output format.",
                    "min_confidence": MIN_CONFIDENCE,
                    "debug": rf_json if debug else None,
                },
            )

        assessment = compute_wound_assessment(pil_img, bbox, poly, conf=conf)

        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "detected": True,
                "confidence": conf,
                "class": pred_class(best),
                "bbox": {"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]},
                "assessment": assessment,
                "min_confidence": MIN_CONFIDENCE,
                "debug": rf_json if debug else None,
            },
        )

    except Exception as e:
        logger.exception("Predict failed")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ===== FOLLOW-UP CHAT ENDPOINT =====

class ChatRequest(BaseModel):
    question: str
    wound_context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None  # [{"role":"user","content":"..."},...]


def _build_wound_summary(ctx: Optional[Dict]) -> str:
    """Convert the predict response into a compact plain-text summary for the system prompt."""
    if not ctx:
        return "No wound analysis data available."
    lines = ["== Patient Wound Analysis Summary =="]
    m = ctx.get("measurements") or {}
    if m:
        lines.append(f"Wound size: {m.get('length_cm', '?')} cm long x {m.get('width_cm', '?')} cm wide, area {m.get('area_cm2', '?')} cm²")
    ha = ctx.get("healing_assessment") or {}
    if ha:
        lines.append(f"Healing stage: {ha.get('healing_stage', '?')}, progress: {ha.get('healing_progress', '?')}, severity: {ha.get('severity', '?')}")
        ir = ha.get("infection_risk") or {}
        if ir:
            lines.append(f"Infection risk: {ir.get('level', '?')} ({ir.get('score', '?')}%)")
        st = ha.get("stitches") or {}
        if st:
            lines.append(f"Closure: {'Stitches needed' if st.get('need_stitches') else 'Heals naturally'} — {st.get('recommendation', '')}")
        htp = ha.get("healing_time_prediction") or {}
        if htp:
            lines.append(f"Estimated healing: {htp.get('predicted_days_min', '?')}–{htp.get('predicted_days_max', '?')} days")
        concerns = ha.get("concerns") or []
        if concerns:
            lines.append("Concerns: " + "; ".join(concerns))
    ca = ctx.get("color_analysis") or {}
    if ca:
        lines.append(f"Color description: {ca.get('color_description', '?')}")
        cper = ca.get("color_percentages") or {}
        if cper:
            lines.append("Color breakdown: " + ", ".join(f"{k} {v:.0f}%" for k, v in cper.items()))
    rec = ctx.get("recommendations") or {}
    ic = rec.get("immediate_care") or []
    if ic:
        lines.append("Immediate care: " + "; ".join(ic[:3]))
    oa = ctx.get("overall_assessment") or ""
    if oa:
        lines.append(f"Clinical summary: {oa}")
    return "\n".join(lines)


def _extract_wound_facts(ctx: Optional[Dict]) -> Dict:
    """Pull every useful field out of the predict response into a flat dict."""
    if not ctx:
        return {}
    m   = ctx.get("measurements") or {}
    ha  = ctx.get("healing_assessment") or {}
    ca  = ctx.get("color_analysis") or {}
    rec = ctx.get("recommendations") or {}
    cper = ca.get("color_percentages") or {}
    ir   = ha.get("infection_risk") or {}
    st   = ha.get("stitches") or {}
    htp  = ha.get("healing_time_prediction") or {}
    sr   = ha.get("scar_risk") or {}
    hi   = ha.get("health_indicators") or {}

    pink      = float(cper.get("pink", 0))
    red       = float(cper.get("red", 0))
    brown     = float(cper.get("brown", 0))
    black     = float(cper.get("black", 0))
    yellow    = float(cper.get("yellow", 0))
    area      = float(m.get("area_cm2") or 0)
    length    = float(m.get("length_cm") or 0)
    width     = float(m.get("width_cm") or 0)

    # Derive wound type from color evidence
    if pink > 30:
        wound_type = "surface abrasion / scrape"
    elif red > 35:
        wound_type = "actively bleeding or granulating wound"
    elif black > 20:
        wound_type = "wound with necrotic (dead) tissue"
    elif yellow > 20:
        wound_type = "wound with possible slough or early infection"
    elif brown > 40:
        wound_type = "scabbing or healing wound"
    else:
        wound_type = "open wound"

    return {
        "wound_type":      wound_type,
        "area":            area,
        "length":          length,
        "width":           width,
        "stage":           (ha.get("healing_stage") or "inflammatory").lower(),
        "progress":        (ha.get("healing_progress") or "unknown").lower(),
        "severity":        (ha.get("severity") or "moderate").lower(),
        "infection_level": (ir.get("level") or "unknown").lower(),
        "infection_score": int(ir.get("score") or 0),
        "need_stitches":   bool(st.get("need_stitches", False)),
        "stitches_rec":    st.get("recommendation", ""),
        "days_min":        int(htp.get("predicted_days_min") or 0),
        "days_max":        int(htp.get("predicted_days_max") or 0),
        "heal_confidence": (htp.get("confidence") or "").lower(),
        "scar_risk":       (sr.get("risk") or "unknown").lower(),
        "scar_score":      int(sr.get("score") or 0),
        "scar_tips":       sr.get("tips") or [],
        "color_desc":      ca.get("color_description") or "",
        "pink": pink, "red": red, "brown": brown,
        "black": black, "yellow": yellow,
        "concerns":        ha.get("concerns") or [],
        "healing_inds":    ha.get("healing_indicators") or [],
        "immediate_care":  rec.get("immediate_care") or [],
        "ongoing_care":    rec.get("ongoing_care") or [],
        "warning_signs":   rec.get("warning_signs") or [],
        "overall":         ctx.get("overall_assessment") or "",
        "has_infection_signs": bool(hi.get("signs_of_infection")),
        "healthy_pink":    bool(hi.get("healthy_pink_present")),
        "necrotic":        bool(hi.get("necrotic_tissue")),
    }


def _smart_answer(question: str, f: Dict) -> str:
    """
    Generate a personalised, data-driven answer to any wound care question
    using the extracted wound facts.  No Ollama needed.
    """
    q = question.lower()
    no_data = not f

    # Helper: size description
    def size_str():
        if f.get("area"):
            s = f"{f['area']:.1f} cm²"
            if f.get("length") and f.get("width"):
                s += f" ({f['length']:.1f} × {f['width']:.1f} cm)"
            return s
        return "an unknown size"

    # ── WHAT IS THE WOUND / DESCRIBE / TYPE ──────────────────────────────────
    if any(w in q for w in ["what is", "what's", "what type", "what kind", "describe", "tell me about",
                             "what wound", "kind of wound", "type of wound", "explain"]):
        if no_data:
            return "No wound analysis data is available. Please run an analysis first."
        parts = [
            f"Based on the image analysis, your wound appears to be a **{f['wound_type']}** with an estimated area of {size_str()}.",
            f"It is currently in the **{f['stage']} stage** of healing with **{f['severity']} severity** and healing progress classified as **{f['progress']}**.",
        ]
        if f["concerns"]:
            parts.append("The analysis flagged these concerns: " + "; ".join(f["concerns"]) + ".")
        if f["pink"] > 30:
            parts.append("The high proportion of pink tissue is a positive sign — it indicates the wound surface is relatively shallow and active epithelial (skin repair) cells are present.")
        elif f["yellow"] > 20:
            parts.append("The yellow tissue detected may represent slough (dead tissue) or early infection — this warrants close monitoring.")
        elif f["black"] > 20:
            parts.append("The dark/black tissue is a concern as it may indicate necrotic (dead) tissue — consider seeking professional evaluation.")
        if f["need_stitches"]:
            parts.append(f"⚠️ The analysis recommends closure: {f['stitches_rec']}")
        else:
            parts.append("✅ This wound is assessed as suitable for natural healing with proper home care.")
        parts.append("If anything looks or feels worse over the next 24–48 hours, please consult a healthcare professional.")
        return " ".join(parts)

    # ── STITCHES / SUTURES / CLOSURE ─────────────────────────────────────────
    if any(w in q for w in ["stitch", "suture", "closure", "sew", "glue", "close the wound"]):
        if no_data:
            return ("Stitches are generally needed when a wound is deeper than ~0.5 cm, longer than 2–3 cm with edges that won't stay together, "
                    "or won't stop bleeding after 10 minutes of firm pressure. Please run a wound analysis for a specific recommendation.")
        if f["need_stitches"]:
            return (f"Yes — based on your wound analysis, closure is recommended. {f['stitches_rec']} "
                    "Please seek medical attention promptly. Wounds closed within 6–8 hours generally heal with better outcomes.")
        else:
            return (f"Good news — based on your analysis ({f['wound_type']}, {size_str()}), stitches are not needed. "
                    f"{f['stitches_rec']} "
                    "Focus on keeping the wound clean and moist to support natural healing.")

    # ── INFECTION ─────────────────────────────────────────────────────────────
    if any(w in q for w in ["infect", "infected", "pus", "smell", "odour", "odor", "fever",
                             "swollen", "swelling", "warm", "hot", "red around"]):
        if no_data:
            return ("Signs of infection include increasing redness, warmth, swelling, pus, foul odour, or fever. "
                    "If any of these appear, seek medical care promptly.")
        level = f["infection_level"]
        score = f["infection_score"]
        base = f"Your wound analysis rated infection likelihood as **{level} ({score}%)**. "
        if level in ("high", "severe") or f["has_infection_signs"]:
            return (base + "This is concerning. Watch closely for: increasing redness spreading from the wound edges, warmth, swelling, "
                    "cloudy/yellow discharge, foul odour, or fever above 38°C (100.4°F). "
                    "If any of these are present or worsen, seek medical care today — infected wounds often need antibiotics. "
                    "Do NOT use hydrogen peroxide; rinse gently with saline only.")
        elif level == "moderate":
            return (base + "Monitor the wound carefully over the next 24–48 hours. "
                    "Keep it clean with saline rinse once or twice daily and watch for worsening redness, swelling, or discharge. "
                    "If you notice pus, increasing pain, or a fever, seek medical attention promptly.")
        else:
            return (base + "The infection risk appears low based on the current image. "
                    "Continue daily cleaning with saline and keep the wound moist with petroleum jelly under a non-adherent dressing. "
                    "If redness, warmth, or swelling increases over the next few days, consult a healthcare professional.")

    # ── CLEANING / WASHING ────────────────────────────────────────────────────
    if any(w in q for w in ["clean", "wash", "rinse", "saline", "antiseptic", "disinfect", "hydrogen peroxide", "iodine"]):
        parts = ["Clean your wound gently **once or twice daily** using sterile saline or clean running water — lukewarm temperature is fine."]
        parts.append("**Avoid hydrogen peroxide, iodine, and alcohol** on open wounds; these kill the new cells trying to heal the wound and slow recovery significantly.")
        if not no_data and f["wound_type"] == "surface abrasion / scrape":
            parts.append(f"For a surface abrasion like yours ({size_str()}), a gentle rinse to remove debris is ideal — don't scrub.")
        parts.append("After rinsing, pat dry with a clean cloth, then apply a thin layer of plain petroleum jelly before covering with a dressing.")
        return " ".join(parts)

    # ── DRESSING / BANDAGE / COVER ────────────────────────────────────────────
    if any(w in q for w in ["dressing", "bandage", "cover", "plaster", "wrap", "pad"]):
        parts = ["Use a **non-adherent dressing** (e.g., Telfa pad or a hydrocolloid dressing) over a thin layer of petroleum jelly."]
        parts.append("Change the dressing **daily**, or immediately if it becomes wet, dirty, or soaked through.")
        if not no_data and f["area"] > 5:
            parts.append(f"Given the size of your wound ({size_str()}), a larger dressing pad may be needed to fully cover the area — ensure the dressing extends at least 1 cm beyond the wound edges on all sides.")
        parts.append("A moist wound heals significantly faster than a dry one — the petroleum jelly under the dressing maintains the right moisture level and prevents the dressing from sticking to new tissue.")
        return " ".join(parts)

    # ── SCAR / SCARRING ───────────────────────────────────────────────────────
    if any(w in q for w in ["scar", "scarring", "mark", "discolor", "discolour"]):
        if no_data:
            return ("Scarring depends on wound depth, location, genetics, and care quality. "
                    "Keep the wound moist, avoid picking scabs, and use SPF 30+ on the healed area for 6–12 months.")
        risk = f["scar_risk"]
        score = f["scar_score"]
        parts = [f"Based on your analysis, your scar risk is rated **{risk} ({score}%)**."]
        if f["scar_tips"]:
            parts.append("Recommended scar prevention steps: " + " | ".join(f["scar_tips"][:3]) + ".")
        else:
            if risk in ("high", "severe"):
                parts.append("To minimise scarring: keep the wound moist throughout healing, never pick scabs, and consider silicone gel sheets once the skin fully closes.")
            else:
                parts.append("To minimise any scarring: keep the wound moist, avoid sun exposure on the healing area, and once healed apply SPF 30+ sunscreen daily for 6–12 months.")
        if f["pink"] > 30:
            parts.append("The presence of healthy pink tissue is encouraging — it suggests active skin regeneration which generally results in better cosmetic outcomes.")
        return " ".join(parts)

    # ── PAIN / PAINKILLERS ────────────────────────────────────────────────────
    if any(w in q for w in ["pain", "hurt", "painful", "sore", "painkiller", "ibuprofen",
                             "paracetamol", "acetaminophen", "tylenol", "advil", "naproxen"]):
        parts = ["**Acetaminophen (paracetamol / Tylenol)** and **ibuprofen (Advil / Nurofen)** are both effective for wound pain."]
        parts.append("Ibuprofen has the added benefit of reducing inflammation — helpful in the early days.")
        parts.append("Follow label dosing carefully; avoid ibuprofen if you have stomach ulcers, kidney issues, or are pregnant.")
        if not no_data and f["severity"] in ("severe", "critical"):
            parts.append(f"Given that your wound is classified as **{f['severity']} severity**, persistent or worsening pain could indicate infection or deeper tissue damage — seek medical attention if pain is not improving after 48 hours.")
        else:
            parts.append("If pain suddenly worsens after initially improving, this can be a sign of infection — monitor and seek care if this happens.")
        return " ".join(parts)

    # ── HEALING TIME ──────────────────────────────────────────────────────────
    if any(w in q for w in ["how long", "heal", "healing time", "days", "weeks", "recovery", "when will"]):
        if no_data:
            return ("Healing time depends on wound size, depth, location, age, and overall health. "
                    "Small surface wounds: 1–2 weeks. Larger or deeper wounds: 3–8+ weeks. "
                    "Keeping the wound clean and moist significantly speeds recovery.")
        if f["days_min"] and f["days_max"]:
            parts = [f"Based on your wound analysis, the estimated healing time is **{f['days_min']}–{f['days_max']} days** (confidence: {f['heal_confidence']})."]
        else:
            parts = ["A specific healing estimate was not generated for your wound."]
        parts.append(f"This is a {f['wound_type']} ({size_str()}) in the **{f['stage']} stage**.")
        if f["stage"] == "inflammatory":
            parts.append("Inflammatory stage usually lasts 3–5 days — expect some redness and swelling which is normal.")
        elif f["stage"] == "proliferative":
            parts.append("The wound is in the proliferative (tissue-building) stage — good progress. New tissue is actively forming.")
        elif f["stage"] == "remodeling":
            parts.append("The wound is in the remodeling stage, which is the final phase — the surface has likely closed and the underlying tissue is strengthening.")
        if f["concerns"]:
            parts.append("Note: healing may be affected by: " + "; ".join(f["concerns"][:2]) + ".")
        parts.append("Consistent daily wound care (clean + moist + protected) will keep the healing on track.")
        return " ".join(parts)

    # ── CARE STEPS / WHAT SHOULD I DO / TREATMENT ────────────────────────────
    if any(w in q for w in ["what should i do", "how do i treat", "treatment", "care", "manage",
                             "steps", "help", "advice", "recommend", "next step"]):
        if no_data:
            return ("General wound care: 1) Clean once or twice daily with saline. 2) Apply petroleum jelly. "
                    "3) Cover with a non-adherent dressing. 4) Change daily. 5) Watch for infection signs. "
                    "Please run a wound analysis for personalised advice.")
        parts = [f"Here is a personalised care plan for your **{f['wound_type']}** ({size_str()}):"]
        steps = []
        # From analysis immediate care
        for s in f["immediate_care"][:3]:
            steps.append(s)
        # Fill gaps from wound type
        if not any("clean" in s.lower() or "saline" in s.lower() for s in steps):
            steps.append("Clean gently once or twice daily with sterile saline or clean water.")
        if not any("moist" in s.lower() or "petroleum" in s.lower() for s in steps):
            steps.append("Apply a thin layer of petroleum jelly and cover with a non-adherent dressing.")
        if not any("dress" in s.lower() or "change" in s.lower() for s in steps):
            steps.append("Change the dressing daily or when soiled.")
        parts.append("\n" + "\n".join(f"• {s}" for s in steps))
        if f["need_stitches"]:
            parts.append(f"\n⚠️ Important: {f['stitches_rec']}")
        if f["infection_level"] in ("moderate", "high"):
            parts.append(f"\n⚠️ Infection risk is {f['infection_level']} ({f['infection_score']}%) — watch closely for worsening redness, warmth, or discharge.")
        parts.append("\nIf in doubt at any point, please consult a healthcare professional.")
        return " ".join(parts)

    # ── DOCTOR / HOSPITAL / URGENT ────────────────────────────────────────────
    if any(w in q for w in ["doctor", "hospital", "er ", "emergency", "urgent", "go in", "seek", "professional"]):
        if no_data:
            return ("Seek medical attention if: the wound won't stop bleeding after 10 minutes of firm pressure, "
                    "it is very deep or gaping, you see signs of infection (pus, fever, spreading redness), "
                    "or you are unsure about tetanus vaccination.")
        urgency_parts = []
        if f["need_stitches"]:
            urgency_parts.append(f"your wound analysis recommends closure — {f['stitches_rec']}")
        if f["infection_level"] in ("high", "severe") or f["has_infection_signs"]:
            urgency_parts.append(f"infection signs were detected (risk: {f['infection_level']}, {f['infection_score']}%)")
        if f["necrotic"]:
            urgency_parts.append("necrotic (dead) tissue was detected, which needs professional assessment")
        if urgency_parts:
            return ("Based on your analysis, you should seek medical attention because: " +
                    "; ".join(urgency_parts) + ". Please do not delay — contact your nearest clinic or urgent care centre.")
        else:
            return (f"Your wound ({f['wound_type']}, {size_str()}) does not currently show immediate red-flag indicators in the analysis. "
                    "However, always seek medical care if: bleeding won't stop, pain worsens significantly, you develop a fever, "
                    "or you see spreading redness or pus in the coming days.")

    # ── GENERIC / ANYTHING ELSE — full contextual summary ────────────────────
    if no_data:
        return ("I don't have analysis data to work from yet. Please run a wound scan first, "
                "then I can give you specific answers about your wound. In general: keep wounds clean, moist, and covered.")

    # Build a comprehensive personalised response using all available data
    parts = [f"Based on your wound analysis, here's what I can tell you about your **{f['wound_type']}** ({size_str()}):"]

    parts.append(f"\n**Healing status:** {f['stage']} stage, {f['severity']} severity, progress is {f['progress']}.")

    if f["days_min"] and f["days_max"]:
        parts.append(f"**Estimated healing time:** {f['days_min']}–{f['days_max']} days.")

    if f["infection_level"] not in ("unknown", "low"):
        parts.append(f"**Infection risk:** {f['infection_level']} ({f['infection_score']}%) — continue monitoring.")

    if f["need_stitches"]:
        parts.append(f"**Closure:** ⚠️ {f['stitches_rec']}")
    else:
        parts.append("**Closure:** ✅ This wound is expected to heal naturally with proper care.")

    if f["concerns"]:
        parts.append("**Concerns noted:** " + "; ".join(f["concerns"][:2]) + ".")

    if f["immediate_care"]:
        parts.append("**Key care steps:** " + " | ".join(f["immediate_care"][:3]) + ".")

    parts.append("\nIf in doubt about anything specific, please consult a healthcare professional.")
    return "\n".join(parts)


def _ensure_ollama_running():
    """Try to start the Ollama daemon if it is not already running."""
    import subprocess, time
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            return True  # already up
    except Exception:
        pass
    # Not running — try to launch it
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(4)   # give the daemon time to initialise
        return True
    except Exception as e:
        logger.warning(f"[Chat] Could not start Ollama: {e}")
        return False


@app.post("/chat")
async def chat(req: ChatRequest):
    """Answer any question using the local AI model, grounded in the patient's wound data."""
    question = req.question.strip()
    if not question:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Question cannot be empty."})

    wound_summary = _build_wound_summary(req.wound_context)

    system_prompt = (
        "You are WoundSync AI, a first-aid and wound-care assistant built into a medical app. "
        "Your SOLE purpose is to help users understand and care for their wounds at home. "
        "IMPORTANT RULES you must follow without exception:\n"
        "1. ALWAYS answer wound care questions such as how to clean a wound, how to bandage it, signs of infection, healing time, and when to see a doctor. This is your primary job — never refuse these.\n"
        "2. Give specific, step-by-step first-aid instructions using plain language.\n"
        "3. If the user's wound analysis is provided below, reference it directly (e.g. 'Since your wound is classified as a laceration...').\n"
        "4. You MAY answer general medical, health, or science questions using your knowledge.\n"
        "5. At the end of serious answers add: 'If symptoms worsen, see a healthcare professional.'\n"
        "6. NEVER say 'I cannot provide medical advice' for basic first-aid topics — that refusal is harmful in this context.\n\n"
        f"{wound_summary}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in (req.history or []):
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    # ── Try Ollama (AI model) ─────────────────────────────────────────────────
    _ensure_ollama_running()
    try:
        import ollama
        model_resp = ollama.list()
        available = [m.model if hasattr(m, 'model') else m.get('name', '')
                     for m in (model_resp.models if hasattr(model_resp, 'models') else model_resp.get('models', []))]
        # llama3.2 handles chat/system-prompts correctly; meditron is clinical
        # notes only and echoes the system prompt — use it last resort only
        PREFERRED = ["llama3.2:3b", "llama3:8b", "llama3.2", "llama3", "mistral", "phi3", "gemma", "meditron:7b", "meditron"]
        model_name = next((p for p in PREFERRED if any(a.startswith(p.split(":")[0]) for a in available)),
                          available[0] if available else None)
        if not model_name:
            raise RuntimeError("No models installed in Ollama")
        logger.info(f"[Chat] Using Ollama model: {model_name}")

        # meditron doesn't honour the system role — fold context into user turn
        if "meditron" in model_name.lower():
            messages_to_send = []
            for msg in messages:
                if msg["role"] == "system":
                    # inject as a prefixed user message
                    messages_to_send.append({
                        "role": "user",
                        "content": f"[Context for your answers]\n{msg['content']}\n\nPlease keep this context in mind for all your responses."
                    })
                    messages_to_send.append({"role": "assistant", "content": "Understood. I will use this context to answer your questions."})
                else:
                    messages_to_send.append(msg)
        else:
            messages_to_send = messages
        resp = ollama.chat(
            model=model_name,
            messages=messages_to_send,
            options={"temperature": 0.5, "top_p": 0.9, "num_predict": 1024},
        )
        answer = resp.message.content if hasattr(resp, "message") else resp["message"]["content"]
        return JSONResponse(content={"ok": True, "answer": answer.strip(), "source": "ai", "model": model_name})
    except Exception as ollama_err:
        logger.warning(f"[Chat] Ollama failed ({ollama_err}), using context-aware fallback")

    # ── Context-aware smart fallback (no AI available) ────────────────────────
    facts = _extract_wound_facts(req.wound_context)
    answer = _smart_answer(question, facts)
    return JSONResponse(content={"ok": True, "answer": answer, "source": "analysis-based"})


# ===== WOUND PROFILE MANAGEMENT ENDPOINTS =====

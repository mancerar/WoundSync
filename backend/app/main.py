import base64
import io
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

import numpy as np
import requests
from fastapi import FastAPI, File, UploadFile, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from pydantic import BaseModel
from sqlalchemy.orm import Session

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


@app.get("/health")
def health():
    return {"ok": True}


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

# ===== WOUND PROFILE MANAGEMENT ENDPOINTS =====

import base64
import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from fastapi import FastAPI, File, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw

# --- load .env automatically (prevents "Missing env vars" issues) ---
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger("woundsync-backend")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="WoundSync Backend")

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


MIN_CONFIDENCE = _env_float("MIN_CONFIDENCE", 0.35)
MAX_IMAGE_SIDE = _env_int("MAX_IMAGE_SIDE", 1024)

# Conservative demo-safe defaults
# Prevents "zoomed in => urgent" unless user checks danger flags
CLOSEUP_SKIN_FRAC = _env_float("CLOSEUP_SKIN_FRAC", 0.78)
PAPERCUT_MINOR_NORM_MAX = _env_float("PAPERCUT_MINOR_NORM_MAX", 0.038)  # thin
PAPERCUT_MASK_AREA_MAX = _env_float("PAPERCUT_MASK_AREA_MAX", 0.004)     # small
BLEED_DELTA_STRONG = _env_float("BLEED_DELTA_STRONG", 0.06)
BLEED_DELTA_MED = _env_float("BLEED_DELTA_MED", 0.03)


def preprocess_image(image_bytes: bytes, max_side: int = 1024) -> Tuple[Image.Image, bytes]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return img, buf.getvalue()


def roboflow_workflow_infer(image_bytes: bytes) -> Dict[str, Any]:
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    workspace = os.getenv("ROBOFLOW_WORKSPACE", "").strip()
    workflow_id = os.getenv("ROBOFLOW_WORKFLOW_ID", "").strip()

    # Workflows run on serverless
    api_url = os.getenv("ROBOFLOW_API_URL", "https://serverless.roboflow.com").strip().rstrip("/")

    if not api_key or not workspace or not workflow_id:
        raise RuntimeError(
            "Missing Roboflow env vars. Need ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_WORKFLOW_ID."
        )

    url = f"{api_url}/infer/workflows/{workspace}/{workflow_id}"

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "api_key": api_key,
        "inputs": {"image": {"type": "base64", "value": b64}},
    }

    r = requests.post(url, json=payload, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"Roboflow error {r.status_code}: {r.text}")
    return r.json()


def _is_pred_list(lst: Any) -> bool:
    if not isinstance(lst, list) or not lst:
        return False
    if not isinstance(lst[0], dict):
        return False
    for d in lst[:5]:
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


def parse_bbox(p: Dict[str, Any], img_w: int, img_h: int) -> Optional[Tuple[int, int, int, int]]:
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


def skin_fraction_rgb(arr: np.ndarray) -> float:
    """
    Cheap skin detector in YCbCr.
    Not medical-grade. Just for "is this a close-up of skin" gating.
    """
    # rgb uint8 -> ycbcr
    r = arr[..., 0].astype(np.float32)
    g = arr[..., 1].astype(np.float32)
    b = arr[..., 2].astype(np.float32)

    y  =  0.299 * r + 0.587 * g + 0.114 * b
    cb = -0.168736 * r - 0.331264 * g + 0.5 * b + 128
    cr =  0.5 * r - 0.418688 * g - 0.081312 * b + 128

    skin = (cb >= 77) & (cb <= 127) & (cr >= 133) & (cr <= 173) & (y >= 40)
    return float(skin.mean())


def color_features(rgb_pixels: np.ndarray) -> Dict[str, float]:
    if rgb_pixels.size == 0:
        return {"redness": 0.0, "bleed": 0.0, "yellow": 0.0, "dark": 0.0}

    r = rgb_pixels[:, 0].astype(np.int32)
    g = rgb_pixels[:, 1].astype(np.int32)
    b = rgb_pixels[:, 2].astype(np.int32)

    redish = (r > g + 25) & (r > b + 25) & (r > 90)
    bleeding = (r > 165) & (r > g + 55) & (r > b + 55)

    yellowish = (r > 160) & (g > 150) & (b < 130)

    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    dark = lum < 70

    n = float(len(r))
    return {
        "redness": float(redish.sum() / n),
        "bleed": float(bleeding.sum() / n),
        "yellow": float(yellowish.sum() / n),
        "dark": float(dark.sum() / n),
    }


def mask_bbox(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.where(mask == 1)
    if len(xs) < 10:
        return None
    x1 = int(xs.min())
    x2 = int(xs.max()) + 1
    y1 = int(ys.min())
    y2 = int(ys.max()) + 1
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def compute_assessment(
    img: Image.Image,
    bbox: Tuple[int, int, int, int],
    poly: Optional[List[Tuple[int, int]]],
    ctx: Dict[str, bool],
) -> Dict[str, Any]:
    img_w, img_h = img.size
    arr = np.array(img.convert("RGB"))
    img_area = float(img_w * img_h)

    raw_mask = make_mask(img_w, img_h, bbox, poly)

    # Use mask bbox for geometry (prevents sloppy bbox from causing fake "big wound")
    mbb = mask_bbox(raw_mask)
    if not mbb:
        mbb = bbox
    mx1, my1, mx2, my2 = mbb
    mw = mx2 - mx1
    mh = my2 - my1

    # Ring around wound to compare against (skin baseline)
    pad = int(round(0.35 * max(mw, mh)))
    ex1 = max(0, mx1 - pad)
    ey1 = max(0, my1 - pad)
    ex2 = min(img_w, mx2 + pad)
    ey2 = min(img_h, my2 + pad)

    ring = np.zeros((img_h, img_w), dtype=np.uint8)
    ring[ey1:ey2, ex1:ex2] = 1
    ring[raw_mask == 1] = 0

    wound_pixels = arr[raw_mask == 1]
    ring_pixels = arr[ring == 1]
    global_pixels = arr.reshape(-1, 3)

    wound_cf = color_features(wound_pixels)
    ring_cf = color_features(ring_pixels)
    global_cf = color_features(global_pixels)

    mask_area = float(raw_mask.sum())
    mask_area_ratio = float(mask_area / (img_area + 1e-6))
    bbox_area = float((mx2 - mx1) * (my2 - my1))
    fill_ratio = float(mask_area / (bbox_area + 1e-6))

    elongation = float(max(mw, mh) / (min(mw, mh) + 1e-6))
    minor_norm = float(min(mw, mh) / (min(img_w, img_h) + 1e-6))
    major_norm = float(max(mw, mh) / (min(img_w, img_h) + 1e-6))

    skin_frac = skin_fraction_rgb(arr)
    closeup = skin_frac >= CLOSEUP_SKIN_FRAC

    # Make bleeding + redness relative to surrounding skin (fixes pink finger skin)
    bleed_delta = max(0.0, wound_cf["bleed"] - ring_cf["bleed"])
    redness_spread = max(0.0, ring_cf["redness"] - global_cf["redness"])

    # Basic wound type
    looks_like_cut = (elongation >= 2.6 and fill_ratio <= 0.55) or (elongation >= 3.1)
    looks_like_scrape = (not looks_like_cut) and (fill_ratio >= 0.45 and mask_area_ratio >= 0.004)

    if looks_like_cut:
        wound_type = "cut"
        summary = "This looks like a cut / laceration."
    elif looks_like_scrape:
        wound_type = "scrape"
        summary = "This looks like a scrape / abrasion."
    else:
        wound_type = "uncertain"
        summary = "Wound detected, but the type is unclear from the image."

    # Danger flags (user-provided)
    bleeding_not_stop = ctx.get("bleeding_not_stop", False)
    numbness_weakness = ctx.get("numbness_weakness", False)
    bite_dirty = ctx.get("bite_dirty", False)
    on_hand_face_joint = ctx.get("on_hand_face_joint", False)
    high_risk = ctx.get("high_risk", False)

    why: List[str] = []
    photo_note = "Best photo: bright lighting, no blur, wound centered, minimal glare."

    # Severity score (conservative)
    score = 0.0

    # Strong overrides
    if bleeding_not_stop:
        score += 4.0
        why.append("You indicated bleeding that won’t stop after 10 minutes of pressure")
    if numbness_weakness:
        score += 4.0
        why.append("You indicated numbness or weakness near the injury")

    # Geometry-based depth/gape proxy (use minor width, not overall zoom)
    if minor_norm >= 0.070:
        score += 2.8
        why.append("Wound looks relatively wide / may gape open")
    elif minor_norm >= 0.050:
        score += 1.8
        why.append("Wound width looks moderate")

    # Dark core proxy (weak)
    if wound_cf["dark"] >= 0.22 and looks_like_cut:
        score += 1.2
        why.append("Color pattern suggests deeper tissue shadow (weak signal)")

    # Bleeding proxy (relative to ring)
    if bleed_delta >= BLEED_DELTA_STRONG:
        score += 2.0
        why.append("Color looks consistent with active bleeding (relative to surrounding skin)")
    elif bleed_delta >= BLEED_DELTA_MED:
        score += 1.0
        why.append("Color may indicate some bleeding (relative to surrounding skin)")

    # Surrounding redness (localized vs entire photo)
    if redness_spread >= 0.08:
        score += 0.8
        why.append("Surrounding redness looks notable compared to the rest of the photo")
    elif redness_spread >= 0.05:
        score += 0.4
        why.append("Some surrounding redness detected")

    # Contamination risk
    if bite_dirty:
        score += 1.4
        why.append("Bite / dirty or contaminated wound increases risk")
    if high_risk:
        score += 0.6
        why.append("Higher infection risk increases caution")

    # Location should NOT auto-escalate to urgent
    if on_hand_face_joint:
        score += 0.6
        why.append("You indicated face/hand/joint location (more likely to need evaluation)")

    # Close-up cap to prevent papercut panic
    # If it looks like a thin small cut AND user did not hit danger flags,
    # don't allow "urgent" purely off image.
    papercut_like = (minor_norm <= PAPERCUT_MINOR_NORM_MAX) and (mask_area_ratio <= PAPERCUT_MASK_AREA_MAX) and (fill_ratio <= 0.55)

    if closeup:
        photo_note = "This looks like a close-up photo. For better calibration, take one zoomed-out photo showing more surrounding area."
        why.append("Photo appears to be a close-up (scale is harder to estimate from zoom)")

        if papercut_like and (not bleeding_not_stop) and (not numbness_weakness):
            # hard cap: can't be urgent from image-only in this case
            score = min(score, 1.6)
            why.append("Thin small cut pattern: urgency capped unless danger symptoms are selected")

    # Decide urgency
    if score >= 3.2:
        urgency = "urgent"
    elif score >= 1.7:
        urgency = "soon"
    else:
        urgency = "home"

    # Build output guidance (safe + demo-friendly)
    disclaimer = "Not a diagnosis. Image-only guidance can be wrong. If you’re worried, get checked in person."

    next_steps: List[str] = []
    tips: List[str] = []
    watch_for: List[str] = []

    if urgency == "urgent":
        next_steps.append("Urgent care recommended today.")
        next_steps.append("If the cut separates when you gently pull the edges, is deep, or won’t stay closed, it may need closure (stitches/skin glue/steri-strips).")
        tips.extend([
            "If bleeding: apply firm, steady pressure with clean gauze/cloth for 10 minutes without checking.",
            "Rinse with clean running water. Use mild soap around the area (don’t scrub inside the wound).",
            "Cover with a non-stick dressing. Keep it protected until you’re seen.",
            "If dirty or tetanus status is unclear, ask about a tetanus booster.",
        ])
        watch_for.extend([
            "Bleeding that won’t stop after 10 minutes of firm pressure",
            "Wound edges gaping open, deep tissue visible, or numbness/weakness",
            "Rapidly spreading redness, worsening pain, fever, or thick drainage",
        ])
    elif urgency == "soon":
        next_steps.append("Get checked soon (same day or next day) if symptoms worsen or the wound won’t stay closed.")
        tips.extend([
            "Rinse with clean water. Clean gently with mild soap around the wound.",
            "Apply a thin layer of petroleum jelly and cover with a non-stick dressing.",
            "Change the dressing daily (or if wet/dirty). Avoid picking at scabs.",
            "Take a follow-up photo in 24 hours in similar lighting to compare.",
        ])
        watch_for.extend([
            "Redness spreading outward day to day",
            "Pain increasing instead of improving",
            "Swelling, warmth, bad smell, or cloudy drainage",
        ])
    else:
        next_steps.append("Looks suitable for basic home care if symptoms are mild.")
        tips.extend([
            "Rinse with clean water. Use mild soap around the area.",
            "Apply a thin layer of petroleum jelly and cover with a non-stick dressing.",
            "Change the dressing daily (or if wet/dirty). Keep it clean and protected.",
        ])
        watch_for.extend([
            "Redness spreading, increasing pain, swelling, warmth",
            "Drainage, fever, or the wound not improving over a few days",
        ])

    if wound_type == "cut":
        tips.append("Cuts over joints/hands/face or from bites/dirty objects usually deserve a clinician check.")
    if wound_type == "scrape":
        tips.append("Scrapes usually heal faster when kept moist + covered (not dried out).")
    if bleed_delta >= BLEED_DELTA_MED:
        tips.append("If actively bleeding, prioritize pressure + dressing first, ointment after.")

    return {
        "summary": summary,
        "urgency": urgency,  # home | soon | urgent
        "wound_type": wound_type,
        "photo_note": photo_note,
        "why_flagged": why,
        "disclaimer": disclaimer,
        "next_steps": next_steps,
        "tips": tips,
        "watch_for": watch_for,
        "signals": {
            "closeup": closeup,
            "skin_frac": round(skin_frac, 3),
            "mask_area_ratio": round(mask_area_ratio, 4),
            "fill_ratio": round(fill_ratio, 3),
            "elongation": round(elongation, 2),
            "minor_norm": round(minor_norm, 3),
            "major_norm": round(major_norm, 3),
            "bleed_delta": round(bleed_delta, 3),
            "redness_spread": round(redness_spread, 3),
            "wound_color": {k: round(v, 3) for k, v in wound_cf.items()},
            "ring_color": {k: round(v, 3) for k, v in ring_cf.items()},
        },
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/predict")
async def predict(
    image: UploadFile = File(...),
    debug: bool = Query(False),

    # context flags from UI
    bleeding_not_stop: bool = Query(False),
    numbness_weakness: bool = Query(False),
    bite_dirty: bool = Query(False),
    on_hand_face_joint: bool = Query(False),
    high_risk: bool = Query(False),
):
    try:
        image_bytes = await image.read()
        pil_img, infer_bytes = preprocess_image(image_bytes, max_side=MAX_IMAGE_SIDE)

        rf_json = roboflow_workflow_infer(infer_bytes)
        pred_lists = extract_prediction_lists(rf_json)

        all_preds: List[Dict[str, Any]] = []
        for lst in pred_lists:
            for p in lst:
                if isinstance(p, dict) and pred_conf(p) > 0:
                    all_preds.append(p)

        wound_preds = [p for p in all_preds if pred_class(p).lower() in ["wound", "abrasion", "cut", "laceration"]]
        candidates = wound_preds if wound_preds else all_preds

        if not candidates:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "detected": False,
                    "confidence": 0.0,
                    "message": "No predictions returned from the workflow.",
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
                    "message": "Not confident enough. Retake the photo (brighter, closer, no blur, less glare).",
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

        ctx = {
            "bleeding_not_stop": bleeding_not_stop,
            "numbness_weakness": numbness_weakness,
            "bite_dirty": bite_dirty,
            "on_hand_face_joint": on_hand_face_joint,
            "high_risk": high_risk,
        }

        assessment = compute_assessment(pil_img, bbox, poly, ctx)

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

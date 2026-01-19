"""Roboflow cloud inference adapter for wound segmentation.

This module provides a thin wrapper around the Roboflow Inference SDK to
call a hosted segmentation model and convert predictions into a binary
mask suitable for the WoundAnalyzer pipeline.

Configuration is supplied via environment variables (see app.config):
- ROBOFLOW_API_KEY
- ROBOFLOW_MODEL_ID  (e.g., "your-workspace/your-model/1")
- ROBOFLOW_API_URL   (defaults to https://serverless.roboflow.com)

Returns mask as uint8 array with values {0,255} at the original image size.
"""
from __future__ import annotations

from typing import Tuple, List
import base64

import numpy as np
import cv2

try:
    # inference-sdk is optional; imported only when used
    from inference_sdk import InferenceHTTPClient  # type: ignore
except Exception:  # pragma: no cover
    InferenceHTTPClient = None  # type: ignore


def _decode_mask_from_base64_png(b64png: str, target_size: Tuple[int, int]) -> np.ndarray:
    data = base64.b64decode(b64png)
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros((target_size[1], target_size[0]), dtype=np.uint8)
    if (img.shape[1], img.shape[0]) != target_size:
        img = cv2.resize(img, target_size, interpolation=cv2.INTER_NEAREST)
    # Binarize
    _, bin_img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    return bin_img.astype(np.uint8)


def _mask_from_polygons(preds: List[dict], target_size: Tuple[int, int]) -> np.ndarray:
    w, h = target_size
    mask = np.zeros((h, w), dtype=np.uint8)
    polys = []
    for p in preds:
        # Roboflow segmentation predictions often expose "points" for polygons
        pts = p.get("points") or p.get("segments") or p.get("polygon")
        if not pts:
            continue
        arr = np.array(pts, dtype=np.float32)
        # Some formats are list of dicts {x:..., y:...}
        if arr.ndim == 1 and len(pts) and isinstance(pts[0], dict):
            arr = np.array([[pt.get("x", 0), pt.get("y", 0)] for pt in pts], dtype=np.float32)
        if arr.size < 6:
            continue
        # Clamp and convert to int
        arr[:, 0] = np.clip(arr[:, 0], 0, w - 1)
        arr[:, 1] = np.clip(arr[:, 1], 0, h - 1)
        polys.append(arr.astype(np.int32))
    if polys:
        cv2.fillPoly(mask, polys, 255)
    return mask


def _mask_from_boxes(preds: List[dict], target_size: Tuple[int, int]) -> np.ndarray:
    """Build a mask from detection-style predictions with x,y,width,height.

    Roboflow detection typically uses center coordinates (x,y) with width/height.
    """
    w, h = target_size
    mask = np.zeros((h, w), dtype=np.uint8)
    for p in preds:
        if all(k in p for k in ("x", "y", "width", "height")):
            cx = float(p.get("x", 0.0))
            cy = float(p.get("y", 0.0))
            bw = float(p.get("width", 0.0))
            bh = float(p.get("height", 0.0))
            x1 = int(max(0, round(cx - bw / 2)))
            y1 = int(max(0, round(cy - bh / 2)))
            x2 = int(min(w - 1, round(cx + bw / 2)))
            y2 = int(min(h - 1, round(cy + bh / 2)))
            if x2 > x1 and y2 > y1:
                cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
    return mask


class RoboflowSegmenter:
    """Lightweight segmenter using Roboflow serverless inference."""

    def __init__(self, api_key: str, model_id: str, api_url: str = "https://serverless.roboflow.com"):
        if InferenceHTTPClient is None:
            raise ImportError("inference-sdk is not installed. Add it to requirements and install.")
        self.api_key = api_key
        self.model_id = model_id
        self.api_url = api_url
        self.client = InferenceHTTPClient(api_url=api_url, api_key=api_key)

    def segment(self, image_path: str) -> Tuple[np.ndarray, dict]:
        # Read image for size
        img = cv2.imread(image_path)
        if img is None:
            h, w = 0, 0
        else:
            h, w = img.shape[:2]
        target = (w, h)

        result = self.client.infer(image_path, model_id=self.model_id)
        info = {"method": "roboflow", "raw_keys": list(result.keys())}

        # Try direct mask first (some deployments can return mask as base64 png)
        b64_mask = result.get("mask") or result.get("image")  # "image" may be overlay; try anyway
        if isinstance(b64_mask, str) and len(b64_mask) > 100:
            mask = _decode_mask_from_base64_png(b64_mask, target)
            if cv2.countNonZero(mask) > 0:
                return mask, info

        # Otherwise, build from polygons first, then fall back to boxes
        preds = result.get("predictions") or result.get("segments") or []
        mask = _mask_from_polygons(preds, target)
        if cv2.countNonZero(mask) == 0 and preds:
            mask = _mask_from_boxes(preds, target)
        return mask, info
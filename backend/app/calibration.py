import json
from pathlib import Path
from typing import Optional

CALIBRATION_FILE = Path(__file__).resolve().parent / "calibration.json"


def get_ppcm_from_calibration(image_width: int, image_height: int) -> Optional[float]:
    """Return pixels-per-cm ONLY if there is an exact resolution match in calibration.json.

    The "default" value is intentionally NOT returned here — it is a last-resort
    fallback handled in wound_analyzer after all other estimation methods fail.
    This prevents the default from overriding the smarter blended estimator.
    """
    if not CALIBRATION_FILE.exists():
        return None
    try:
        data = json.loads(CALIBRATION_FILE.read_text())
        by_res = data.get("by_resolution", {})
        key = f"{image_width}x{image_height}"
        if key in by_res:
            return float(by_res[key])
    except Exception:
        return None
    return None


def get_default_ppcm() -> float:
    """Return the default px/cm from calibration.json, or 120.0 if not set."""
    if not CALIBRATION_FILE.exists():
        return 120.0
    try:
        data = json.loads(CALIBRATION_FILE.read_text())
        return float(data.get("default", 120.0))
    except Exception:
        return 120.0

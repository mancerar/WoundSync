import json
from pathlib import Path
from typing import Optional

CALIBRATION_FILE = Path(__file__).resolve().parent / "calibration.json"


def get_ppcm_from_calibration(image_width: int, image_height: int) -> Optional[float]:
    """Return pixels-per-cm from a calibration.json if present.

    The file format is:
    {
        "by_resolution": {
            "699x183": 62.0,
            "<width>x<height>": <ppcm>
        },
        "default": 60.0
    }
    """
    if not CALIBRATION_FILE.exists():
        return None
    try:
        data = json.loads(CALIBRATION_FILE.read_text())
        by_res = data.get("by_resolution", {})
        key = f"{image_width}x{image_height}"
        if key in by_res:
            return float(by_res[key])
        default_ppcm = data.get("default")
        if default_ppcm is not None:
            return float(default_ppcm)
    except Exception:
        return None
    return None

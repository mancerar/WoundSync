import cv2
import numpy as np

# Assumed scale: ~45 pixels per centimetre approximates a phone camera
# held 30 cm away with no zoom. Adjust once a real calibration method exists.
ASSUMED_PIXELS_PER_CM = 45


def estimated_centimetres(area_px: int, width_px: int, height_px: int) -> dict:
    if not area_px or not width_px or not height_px:
        return {}

    pixels_per_cm = ASSUMED_PIXELS_PER_CM
    cm_width = width_px / pixels_per_cm
    cm_height = height_px / pixels_per_cm
    cm_area = area_px / (pixels_per_cm ** 2)

    return {
        "assumed_pixels_per_cm": pixels_per_cm,
        "estimated_wound_area_cm2": cm_area,
        "estimated_wound_width_cm": cm_width,
        "estimated_wound_height_cm": cm_height,
    }


def measure_wound(path: str) -> dict:
    """Return wound metrics (pixels plus assumed centimetre estimates)."""
    image = cv2.imread(path)
    if image is None:
        return {}

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = np.ones((5, 5), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {}

    largest = max(contours, key=cv2.contourArea)
    image_area = image.shape[0] * image.shape[1]
    area = int(cv2.contourArea(largest))

    if image_area and area > 0.9 * image_area:
        inverted = cv2.bitwise_not(cleaned)
        contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {}
        largest = max(contours, key=cv2.contourArea)

    area = int(cv2.contourArea(largest))
    x, y, width, height = cv2.boundingRect(largest)

    wound_metrics = {
        "wound_area_px": area,
        "wound_width_px": int(width),
        "wound_height_px": int(height),
    }

    wound_metrics.update(estimated_centimetres(area, int(width), int(height)))

    return wound_metrics

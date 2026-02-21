"""
Wound measurement inference module.

This module provides wound segmentation and measurement capabilities using
computer vision techniques. For now, it uses traditional CV methods as a 
placeholder until the deep learning model training is complete.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
from .calibration import get_ppcm_from_calibration
from .config import get_roboflow_config
from .calibration import get_ppcm_from_calibration


class WoundAnalyzer:
    """Analyzes wound images to extract measurements and characteristics."""
    
    def __init__(self, pixels_per_cm: float = 45.0, auto_calibrate: bool = True, assumed_wound_width_cm: float = 0.3):
        """
        Initialize the wound analyzer.
        
        Args:
            pixels_per_cm: Assumed conversion factor from pixels to centimeters
        """
        self.pixels_per_cm = pixels_per_cm
        self.auto_calibrate = auto_calibrate
        # Typical incision-like wound thickness in centimeters (dataset prior). Adjust as needed.
        self.assumed_wound_width_cm = max(0.05, float(assumed_wound_width_cm))
        # Human-friendly method label, overridden by ML analyzer
        self.method_name = "Traditional Computer Vision"
    
    def analyze_wound(self, image_path: str, save_visual: bool = True, output_dir: str = "output") -> Dict:
        """
        Analyze a wound image and return comprehensive measurements and characteristics.
        
        Args:
            image_path: Path to the wound image
            
        Returns:
            Dictionary containing complete wound analysis results
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "Could not load image"}
            
            # Get wound segmentation mask
            mask = self._segment_wound(image)
            
            # Auto-calibrate pixel-to-cm from dataset calibration / wound thickness if enabled
            ppcm_used = self.pixels_per_cm
            calib_info = {"mode": "default", "ppcm": ppcm_used}
            if self.auto_calibrate:
                # 0) Try explicit calibration profile if present
                calib_ppcm = get_ppcm_from_calibration(image.shape[1], image.shape[0])
                if calib_ppcm is not None:
                    ppcm_used = float(np.clip(calib_ppcm, 10.0, 800.0))
                    calib_info = {"mode": "calibration.json", "ppcm": ppcm_used}

                est_ppcm = self._estimate_pixels_per_cm_from_mask(mask, self.assumed_wound_width_cm)
                prior_ppcm = self._ppcm_prior_from_image_size(image)
                if est_ppcm is not None and prior_ppcm is not None:
                    # Blend prior (dataset-level) with thickness estimate (image-level)
                    # Weighted geometric mean favors prior for stability
                    blended = float(np.exp(0.7 * np.log(prior_ppcm) + 0.3 * np.log(est_ppcm)))
                    blended = float(np.clip(blended, 20.0, 400.0))
                    # If calibration.json already gave a value, keep it, else use blended
                    if calib_info.get("mode") != "calibration.json":
                        ppcm_used = blended
                        calib_info = {"mode": "blended", "ppcm": ppcm_used, "prior": prior_ppcm, "from_width_px": est_ppcm, "assumed_width_cm": self.assumed_wound_width_cm}
                elif prior_ppcm is not None:
                    if calib_info.get("mode") != "calibration.json":
                        ppcm_used = prior_ppcm
                        calib_info = {"mode": "prior", "ppcm": ppcm_used}
                elif est_ppcm is not None:
                    if calib_info.get("mode") != "calibration.json":
                        ppcm_used = est_ppcm
                        calib_info = {"mode": "width-from-image", "ppcm": ppcm_used, "assumed_width_cm": self.assumed_wound_width_cm}

            # First calculate measurements from the mask using calibrated ppcm
            measurements = self._calculate_measurements(mask, pixels_per_cm=ppcm_used)

            # Determine detection using adaptive criteria (handles small, thin wounds)
            wound_area = cv2.countNonZero(mask)
            total_area = mask.shape[0] * mask.shape[1]
            area_pct = (wound_area / max(1, total_area))

            width_px = measurements.get("width_px", 0)
            height_px = measurements.get("height_px", 0)
            long_edge = max(width_px, height_px)
            short_edge = max(1, min(width_px, height_px))
            aspect_ratio = long_edge / short_edge

            # Base detection on either: a minimum absolute pixel area, a tiny relative area, or an elongated linear feature
            min_abs_px = max(30, int(0.00005 * total_area))  # at least a few dozen pixels, or 0.005% of image
            area_detect = wound_area >= min_abs_px or area_pct > 0.0005
            elongated_detect = (aspect_ratio >= 6 and long_edge >= 40)
            wound_detected = bool((wound_area > 0) and (area_detect or elongated_detect))

            # Confidence blends area strength and elongation evidence
            area_conf = min(area_pct / 0.03, 1.0)  # 3% coverage -> 100%
            elong_conf = min(max(long_edge - 40, 0) / 120, 1.0) if elongated_detect else 0.0  # 40..160px
            confidence = max(area_conf, 0.6 * elong_conf) if wound_detected else 0.0
            
            # Analyze wound color/characteristics
            color_analysis = self._analyze_color(image, mask)
            
            # Generate healing assessment
            healing_assessment = self._assess_healing(measurements, color_analysis)
            
            # Enhanced color analysis
            enhanced_color_analysis = self._enhanced_color_analysis(image, mask)
            
            # Generate visual output if requested
            visual_output_path = None
            if save_visual and wound_detected:
                visual_output_path = self._create_visual_output(image_path, image, mask, output_dir, pixels_per_cm=ppcm_used)
            
            return {
                "wound_detected": wound_detected,
                "confidence": confidence,
                "method": getattr(self, "method_name", "Traditional Computer Vision"),
                "measurements": measurements,
                "color_analysis": {**color_analysis, **enhanced_color_analysis},
                "healing_assessment": healing_assessment,
                "recommendations": healing_assessment.get("recommendations", {}),
                "overall_assessment": healing_assessment.get("overall_assessment", ""),
                "pixels_per_cm": ppcm_used,
                "calibration": calib_info,
                "technical_details": {
                    "wound_area_pixels": int(wound_area),
                    "total_image_pixels": int(total_area),
                    "wound_percentage": round((wound_area / total_area) * 100, 2)
                },
                "visual_output": visual_output_path
            }
            
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    def _enhanced_color_analysis(self, image: np.ndarray, mask: np.ndarray) -> Dict:
        """Enhanced color analysis with percentage breakdown."""
        wound_pixels = image[mask > 0]
        
        if len(wound_pixels) == 0:
            return {
                "color_percentages": {"background": 100.0},
                "health_indicators": {}
            }
        
        # Convert to HSV for better analysis
        wound_hsv = cv2.cvtColor(wound_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV)
        
        # Define color ranges in HSV
        color_ranges = {
            "red": [(0, 50, 50), (10, 255, 255), (170, 50, 50), (180, 255, 255)],
            "pink": [(0, 20, 100), (20, 100, 255)],
            "yellow": [(20, 50, 50), (30, 255, 255)],
            "green": [(40, 50, 50), (80, 255, 255)],
            "brown": [(10, 50, 20), (20, 255, 200)],
            "black": [(0, 0, 0), (180, 255, 50)]
        }
        
        # Calculate color percentages
        color_percentages = {}
        total_pixels = len(wound_pixels)
        
        for color_name, ranges in color_ranges.items():
            count = 0
            for i in range(0, len(ranges), 2):
                lower = np.array(ranges[i])
                upper = np.array(ranges[i + 1])
                mask_color = cv2.inRange(wound_hsv, lower, upper)
                count += cv2.countNonZero(mask_color)
            
            percentage = (count / total_pixels) * 100
            if percentage > 0.5:  # Only include colors that make up more than 0.5%
                color_percentages[color_name] = round(percentage, 1)
        
        # Calculate remaining as "other"
        accounted = sum(color_percentages.values())
        if accounted < 100:
            color_percentages["other"] = round(100 - accounted, 1)
        
        # Health indicators based on colors
        health_indicators = {
            "healthy_pink_present": color_percentages.get("pink", 0) > 20,
            "excessive_redness": color_percentages.get("red", 0) > 60,
            "signs_of_infection": color_percentages.get("yellow", 0) > 15 or color_percentages.get("green", 0) > 5,
            "necrotic_tissue": color_percentages.get("black", 0) > 10 or color_percentages.get("brown", 0) > 30
        }
        
        return {
            "color_percentages": color_percentages,
            "health_indicators": health_indicators
        }
    
    def _segment_wound(self, image: np.ndarray) -> np.ndarray:
        """Segment wound from background using hybrid CV methods tuned for thin red incisions.

        Goal: capture the entire elongated red wound (not just a small patch) by combining
        a redness score map, multi-orientation morphological bridging, and hull expansion.
        """
        h, w = image.shape[:2]
        image_area = float(h * w)

        # Convert to multiple color spaces
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 1) Detect red hues in HSV (two ranges wrap around 0/180)
        # constrain by saturation/value to avoid skin (allow darker reds with lower V)
        lower_red1 = np.array([0, 80, 10]); upper_red1 = np.array([12, 255, 200])
        lower_red2 = np.array([168, 80, 10]); upper_red2 = np.array([180, 255, 200])
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        # 2) Enhance red vs skin using LAB a-channel (red-green axis)
        a_channel = lab[:, :, 1]
        a_blur = cv2.GaussianBlur(a_channel, (5, 5), 0)
        a_mean, a_std = float(a_blur.mean()), float(a_blur.std() + 1e-6)
        thresh_a = np.clip(a_mean + 0.35 * a_std, 118, 170)  # slightly more permissive
        _, mask_lab = cv2.threshold(a_blur, thresh_a, 255, cv2.THRESH_BINARY)

        # 3) Edge emphasis to capture thin linear wounds
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_eq = clahe.apply(gray)
        edges = cv2.Canny(gray_eq, 50, 140)
        edges_dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

        # 4) Build a continuous redness score map to favor the entire red band
        b, g, r = cv2.split(image)
        rg = cv2.subtract(r, g)
        rg = cv2.max(rg, 0)
        rg = cv2.GaussianBlur(rg, (5, 5), 0)
        rg_norm = cv2.normalize(rg.astype(np.float32), None, 0.0, 1.0, cv2.NORM_MINMAX)

        a_pos = cv2.max(a_blur.astype(np.int16) - 128, 0).astype(np.uint8)
        a_norm = cv2.normalize(a_pos.astype(np.float32), None, 0.0, 1.0, cv2.NORM_MINMAX)

        red_focus = cv2.dilate(mask_red, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
        red_focus_f = (red_focus / 255.0).astype(np.float32)

        redness_score = 0.55 * rg_norm + 0.65 * a_norm + 0.8 * red_focus_f
        redness_score = cv2.GaussianBlur(redness_score, (7, 7), 0)

        # Adaptive threshold via high percentile to capture the whole band
        flat = redness_score.reshape(-1)
        p90 = float(np.percentile(flat, 90))
        t = max(p90, float(redness_score.mean() + 0.5 * redness_score.std()))
        score_mask = (redness_score >= t).astype(np.uint8) * 255

        # Combine with LAB and edges but prioritize score continuity inside red focus
        combined = cv2.bitwise_or(score_mask, cv2.bitwise_and(mask_lab, red_focus))
        combined = cv2.bitwise_or(combined, cv2.bitwise_and(edges_dilated, red_focus))

        if cv2.countNonZero(combined) == 0:
            combined = cv2.bitwise_or(mask_red, mask_lab)

        # Morphological cleanup with multi-orientation bridging (H, V, and diagonals)
        k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
        k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 11))
        diag1 = np.zeros((9, 9), np.uint8); np.fill_diagonal(diag1, 1)
        diag2 = np.flipud(diag1)
        m0 = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_h, iterations=2)
        m1 = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_v, iterations=2)
        m2 = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, diag1, iterations=1)
        m3 = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, diag2, iterations=1)
        combined = cv2.bitwise_or(cv2.bitwise_or(m0, m1), cv2.bitwise_or(m2, m3))
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)

        border = max(3, int(0.01 * min(h, w)))
        combined[:border, :] = 0
        combined[-border:, :] = 0
        combined[:, :border] = 0
        combined[:, -border:] = 0

        # Keep only significant/elongated components
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros((h, w), dtype=np.uint8)

        # Prefer the longest red-supported component by its min-area-rect long edge
        best_contour = None
        best_score = -1.0
        for cnt in contours:
            if cv2.contourArea(cnt) < 15:
                continue
            area = cv2.contourArea(cnt)
            area_ratio = float(area) / float(image_area)
            # Skip components that occupy too much of the frame
            if area_ratio > 0.35:
                continue
            rect = cv2.minAreaRect(cnt)
            (_, _), (rw, rh), _ = rect
            long_edge = max(rw, rh)
            if long_edge < 0.1 * w:  # require some continuity
                continue
            contour_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(contour_mask, [cnt], -1, 255, -1)
            red_overlap = cv2.countNonZero(cv2.bitwise_and(red_focus, contour_mask))
            ratio = red_overlap / max(1, cv2.countNonZero(contour_mask))
            # Build a stronger red-core: red focus AND high saturation AND LAB support
            s_mask = cv2.inRange(hsv[:, :, 1], 140, 255)
            red_core = cv2.bitwise_and(red_focus, cv2.bitwise_and(s_mask, mask_lab))
            red_core_overlap = cv2.countNonZero(cv2.bitwise_and(red_core, contour_mask))
            core_ratio = red_core_overlap / max(1, cv2.countNonZero(contour_mask))

            # Require stronger redness to reject skin regions
            if (ratio < 0.08 and red_overlap < 300) and (core_ratio < 0.05 and red_core_overlap < 150):
                continue

            # Scoring: favor redness support and continuity, penalize oversized area
            elong = long_edge / float(w)
            score = 1.6 * ratio + 1.2 * core_ratio + 0.8 * elong - 0.8 * min(area_ratio / 0.2, 1.0)
            if score > best_score:
                best_score = score
                best_contour = cnt

        if best_contour is not None:
            hull = cv2.convexHull(best_contour)
            cv2.drawContours(mask, [hull], -1, 255, -1)

            if len(hull) >= 3:
                rect = cv2.minAreaRect(hull)
                (cx, cy), (rect_w, rect_h), angle = rect
                long_edge = max(rect_w, rect_h)
                short_edge = max(1.0, min(rect_w, rect_h))

                pad_major = max(3.0, 0.04 * long_edge)
                pad_minor = 1.0

                if rect_w >= rect_h:
                    inflated_size = (rect_w + pad_major, rect_h + pad_minor)
                else:
                    inflated_size = (rect_w + pad_minor, rect_h + pad_major)

                inflated_rect = ((cx, cy), inflated_size, angle)
                box = cv2.boxPoints(inflated_rect)
                box = np.intp(np.clip(box, [0, 0], [w - 1, h - 1]))
                cv2.fillPoly(mask, [box], 255)

            # Skip ellipse thickening to avoid inflating width
        else:
            # Use Hough line as a fallback to capture long incisions
            lines = cv2.HoughLinesP(
                edges_dilated, 1, np.pi / 180, threshold=60,
                minLineLength=int(0.25 * w), maxLineGap=20
            )
            if lines is not None and len(lines) > 0:
                best_line = None
                best_score = -1.0
                for l in lines[:, 0, :]:
                    x1, y1, x2, y2 = map(int, l)
                    length = float(np.hypot(x2 - x1, y2 - y1))
                    test = np.zeros((h, w), dtype=np.uint8)
                    cv2.line(test, (x1, y1), (x2, y2), 255, thickness=5)
                    overlap = cv2.countNonZero(cv2.bitwise_and(test, red_focus))
                    support = overlap / max(1.0, length)
                    score = support * 0.7 + (length / (w + 1e-3)) * 0.3
                    if score > best_score:
                        best_score = score
                        best_line = (x1, y1, x2, y2, length)
                if best_line is not None:
                    x1, y1, x2, y2, length = best_line
                    thickness = int(max(6, min(16, 0.02 * max(h, w))))
                    cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=thickness)
            else:
                # As a last resort, keep merged combined regions
                min_area = max(1, int(0.0001 * image_area))  # 0.01% of image
                for cnt in contours:
                    if cv2.contourArea(cnt) < min_area:
                        continue
                    cv2.drawContours(mask, [cnt], -1, 255, -1)

        # Fallback: if mask is empty, try Otsu thresholding as last resort
        if cv2.countNonZero(mask) == 0:
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = np.ones((3, 3), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)
            # Assume darker-than-skin is wound in this fallback
            if cv2.countNonZero(cleaned) > 0.8 * image_area:
                cleaned = cv2.bitwise_not(cleaned)
            contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_contour = self._select_best_contour(
                contours=contours,
                hsv_image=hsv,
                red_mask=red_focus,
                image_shape=(h, w),
            )
            mask = np.zeros((h, w), dtype=np.uint8)
            if best_contour is not None:
                hull = cv2.convexHull(best_contour)
                cv2.drawContours(mask, [hull], -1, 255, -1)

                if len(hull) >= 3:
                    rect = cv2.minAreaRect(hull)
                    (cx, cy), (rect_w, rect_h), angle = rect
                    long_edge = max(rect_w, rect_h)
                    short_edge = max(1.0, min(rect_w, rect_h))

                    pad_major = max(8.0, 0.25 * long_edge)
                    pad_minor = max(10.0, 0.9 * short_edge)

                    if rect_w >= rect_h:
                        inflated_size = (rect_w + pad_major, rect_h + pad_minor)
                    else:
                        inflated_size = (rect_w + pad_minor, rect_h + pad_major)

                    inflated_rect = ((cx, cy), inflated_size, angle)
                    box = cv2.boxPoints(inflated_rect)
                    box = np.intp(np.clip(box, [0, 0], [w - 1, h - 1]))
                    cv2.fillPoly(mask, [box], 255)

                # Skip ellipse thickening in fallback as well
            else:
                mask = cleaned

            # Remove border-touching or oversized components from the fallback mask
            if cv2.countNonZero(mask) > 0:
                cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cleaned_mask = np.zeros_like(mask)
                for cnt in cnts:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    touches = (x <= 1 or y <= 1 or x + cw >= w - 1 or y + ch >= h - 1)
                    area = cv2.contourArea(cnt)
                    area_ratio = area / float(h * w)
                    if (touches and area > 0.01 * (h * w)) or area_ratio > 0.35:
                        continue
                    cv2.drawContours(cleaned_mask, [cnt], -1, 255, -1)
                mask = cleaned_mask

        if cv2.countNonZero(mask) > 0:
            refine_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, refine_kernel, iterations=1)

        return mask
    
    def _create_visual_output(self, image_path: str, image: np.ndarray, mask: np.ndarray, output_dir: str, pixels_per_cm: Optional[float] = None) -> str:
        """Create visual output that highlights only the wound region.

        Changes from prior behavior:
        - Remove the large green bounding box
        - Draw only the wound hull outline and a subtle semi-transparent fill
        - Keep compact text with area near the wound
    This makes the overlay appear strictly "around the wound" as requested, and now also draws a tight rotated box.
        """
        import os
        from datetime import datetime
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create a copy of the original image for annotation
        annotated_image = image.copy()
        
        # Find contours from the mask (select the best red-supported wound contour)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            red_mask = cv2.inRange(hsv, np.array([0, 80, 10]), np.array([12, 255, 200]))
            red_mask |= cv2.inRange(hsv, np.array([168, 80, 10]), np.array([180, 255, 200]))

            # Filter out large border-hugging contours
            h_img, w_img = annotated_image.shape[:2]
            filtered = []
            for c in contours:
                x0, y0, cw, ch = cv2.boundingRect(c)
                touches = (x0 <= 1 or y0 <= 1 or x0 + cw >= w_img - 1 or y0 + ch >= h_img - 1)
                area = cv2.contourArea(c)
                area_ratio = area / float(h_img * w_img)
                # Prefer elongated, incision-like shapes; drop tiny patches
                rect_c = cv2.minAreaRect(c)
                (_, _), (rw_c, rh_c), _ = rect_c
                long_edge_c = max(rw_c, rh_c)
                short_edge_c = max(1.0, min(rw_c, rh_c))
                aspect_c = (long_edge_c / short_edge_c)
                long_edge_min = max(0.12 * w_img, 60.0)
                # Remove border-hugging large regions and any oversized component
                if (touches and area > 0.01 * (h_img * w_img)) or area_ratio > 0.35:
                    continue
                # Remove small, non-elongated specks that can trick redness score
                if (long_edge_c < long_edge_min) and (area_ratio < 0.003) and (aspect_c < 5.0):
                    continue
                filtered.append(c)
            if not filtered:
                filtered = contours

            best = self._select_best_contour(filtered, hsv, red_mask, (h_img, w_img))
            if best is None:
                best = max(filtered, key=cv2.contourArea)

            hull = cv2.convexHull(best)
            x, y, w, h = cv2.boundingRect(hull)

            # Draw outline only (no fill) to avoid any large tinted regions
            hull_area = cv2.contourArea(hull)
            hull_ratio = hull_area / float(h_img * w_img)

            # Draw the hull outline only (no bounding rectangle)
            cv2.polylines(annotated_image, [hull], isClosed=True, color=(0, 255, 0), thickness=3)

            # Also draw a rotated min-area rectangle tightly around the wound
            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect)
            box = np.intp(box)
            cv2.polylines(annotated_image, [box], isClosed=True, color=(0, 200, 255), thickness=2)

            # Add compact measurements text near the wound
            ppcm = float(pixels_per_cm or self.pixels_per_cm)
            area_cm2 = (cv2.contourArea(hull) / (ppcm ** 2))
            # Use rotated rect edges for length/width in centimeters
            (_, _), (rw, rh), _ = rect
            length_cm = max(rw, rh) / ppcm
            width_cm = max(1e-6, min(rw, rh)) / ppcm
            measurements_text = f"LxW: {length_cm:.1f}x{width_cm:.1f} cm  |  Area: {area_cm2:.1f} cm^2"
            text_x = max(0, x)
            text_y = min(annotated_image.shape[0] - 10, y + h + 20)
            cv2.putText(annotated_image, measurements_text, (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Generate output filename
        input_filename = Path(image_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"wound_analysis_{input_filename}_{timestamp}.png"
        output_path = os.path.join(output_dir, output_filename)
        
        # Save annotated image
        cv2.imwrite(output_path, annotated_image)
        
        # Avoid non-ASCII emoji for broader terminal compatibility
        print(f"Visual output saved: {output_path}")
        
        return output_path

    def _select_best_contour(
        self,
        contours: list,
        hsv_image: np.ndarray,
        red_mask: np.ndarray,
        image_shape: Tuple[int, int]
    ) -> Optional[np.ndarray]:
        """Select the contour that most likely represents the wound region."""

        if not contours:
            return None

        h, w = image_shape
        image_area = float(h * w)
        best_score = -1.0
        best_contour = None

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area <= 0:
                continue

            area_ratio = area / image_area
            if area_ratio > 0.45:
                # Skip contours consuming most of the frame (likely background)
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw <= 2 or ch <= 2:
                continue

            # Skip contours that hug the image border unless they are tiny
            touches_border = (x <= 1 or y <= 1 or (x + cw) >= (w - 1) or (y + ch) >= (h - 1))
            if touches_border and area_ratio > 0.02:
                continue

            contour_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(contour_mask, [cnt], -1, 255, -1)

            wound_pixels = cv2.countNonZero(contour_mask)
            if wound_pixels < 20:
                continue

            red_overlap = cv2.countNonZero(cv2.bitwise_and(red_mask, contour_mask))
            red_ratio = red_overlap / max(wound_pixels, 1)

            # Stronger red-core (HSV red + high saturation)
            s_mask = cv2.inRange(hsv_image[:, :, 1], 100, 255)
            red_core = cv2.bitwise_and(red_mask, s_mask)
            red_core_overlap = cv2.countNonZero(cv2.bitwise_and(red_core, contour_mask))
            red_core_ratio = red_core_overlap / max(wound_pixels, 1)

            # Require redness; allow tiny segments only if very elongated later
            if (red_ratio < 0.07 and red_overlap < 200) and (red_core_ratio < 0.05 and red_core_overlap < 120) and area_ratio > 0.004:
                continue

            sat_mean = cv2.mean(hsv_image[:, :, 1], mask=contour_mask)[0] / 255.0
            val_mean = cv2.mean(hsv_image[:, :, 2], mask=contour_mask)[0] / 255.0

            perimeter = max(cv2.arcLength(cnt, True), 1.0)
            compactness = (4.0 * np.pi * area) / (perimeter * perimeter)
            compactness = float(np.clip(compactness, 0.0, 1.0))

            long_edge = max(cw, ch)
            short_edge = max(1, min(cw, ch))
            aspect_ratio = long_edge / short_edge
            elongation = min(aspect_ratio, 10.0) / 10.0

            # Min-area-rect based geometry for more reliable length/width
            rect = cv2.minAreaRect(cnt)
            (_, _), (rw, rh), _ = rect
            m_long = max(rw, rh)
            m_short = max(1.0, min(rw, rh))
            m_aspect = float(m_long / m_short)
            min_long_thresh = max(0.12 * w, 60.0)

            # Drop tiny, non-elongated patches early (still allow if sufficiently large area)
            if (m_long < min_long_thresh) and (area_ratio < 0.003) and (m_aspect < 5.0):
                continue

            area_preference = 1.0 - min(area_ratio / 0.12, 1.0)
            area_bonus = min(area_ratio / 0.02, 1.0)

            score = (
                1.6 * red_ratio
                + 1.0 * red_core_ratio
                + 0.6 * sat_mean
                + 0.6 * min(m_aspect / 10.0, 1.0)  # prefer elongated
                + 0.6 * min(m_long / (0.35 * w), 1.0)  # prefer longer spans up to 35% of width
                + 0.2 * elongation
                + 0.3 * compactness
                + 0.3 * area_preference
                + 0.2 * area_bonus
            )

            if val_mean < 0.18:
                score *= 0.6

            if score > best_score:
                best_score = score
                best_contour = cnt

        return best_contour
    
    def _calculate_measurements(self, mask: np.ndarray, pixels_per_cm: Optional[float] = None) -> Dict:
        """Calculate wound measurements from segmentation mask.

        pixels_per_cm: Optional override for per-image calibration.
        """
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return {
                "area_px": 0,
                "width_px": 0,
                "height_px": 0,
                "area_cm2": 0.0,
                "width_cm": 0.0,
                "height_cm": 0.0,
                "length_cm": 0.0
            }
        
        largest = max(contours, key=cv2.contourArea)
        
        # Basic measurements
        area_px = cv2.contourArea(largest)
        x, y, w, h = cv2.boundingRect(largest)
        
        # Calculate more precise length (major axis)
        if len(largest) >= 5:
            ellipse = cv2.fitEllipse(largest)
            major_axis = max(ellipse[1])  # Length of major axis
            minor_axis = min(ellipse[1])  # Length of minor axis
            length_px = major_axis
            width_px = minor_axis
        else:
            length_px = max(w, h)
            width_px = min(w, h)

        # Convert to centimeters using provided calibration (or default)
        ppcm = float(pixels_per_cm or self.pixels_per_cm)
        area_cm2 = area_px / (ppcm ** 2)
        width_cm = width_px / ppcm
        height_cm = h / ppcm
        length_cm = length_px / ppcm

        # Thin-wound override: for highly elongated shapes, assume a clinical width
        # and compute length, area from pixel area and estimated core thickness.
        # This stabilizes measurements when absolute scale is missing.
        measurement_mode = "calibrated"
        # Use ellipse axes for a more reliable aspect ratio when available
        if len(largest) >= 5:
            ellipse = cv2.fitEllipse(largest)
            ax_long = max(ellipse[1])
            ax_short = max(1e-3, min(ellipse[1]))
            aspect = ax_long / ax_short
        else:
            short_edge_px = min(w, h)
            long_edge_px = max(w, h)
            aspect = (long_edge_px / max(1, short_edge_px))
        if aspect >= 6.0 or (aspect >= 3.0 and width_cm > 1.0):
            thickness_px = self._estimate_core_thickness_px(mask)
            if thickness_px is not None and thickness_px > 0:
                width_cm_alt = self.assumed_wound_width_cm
                length_cm_alt = (area_px * width_cm_alt) / float(thickness_px ** 2)
                area_cm2_alt = length_cm_alt * width_cm_alt
                # Use alt values only if they are within reasonable bounds
                if 0.05 <= width_cm_alt <= 1.0 and 0.2 <= length_cm_alt <= 25.0:
                    width_cm = float(width_cm_alt)
                    length_cm = float(length_cm_alt)
                    area_cm2 = float(area_cm2_alt)
                    measurement_mode = "thin-wound-approx"

        return {
            "area_px": int(area_px),
            "width_px": int(width_px),
            "height_px": int(h),
            "area_cm2": round(area_cm2, 2),
            "width_cm": round(width_cm, 2),
            "height_cm": round(height_cm, 2),
            "length_cm": round(length_cm, 2),
            "measurement_mode": measurement_mode
        }

    def _ppcm_prior_from_image_size(self, image: np.ndarray) -> Optional[float]:
        """Dataset prior: estimate px/cm from image width.

        Assumption: images around 700 px wide map to ~60 px/cm in this dataset.
        Scales linearly by width. Clamped to [20, 200] px/cm to avoid extremes.
        """
        try:
            h, w = image.shape[:2]
            if w <= 0:
                return None
            # First: exact match from calibration file (if present)
            ppcm_cal = get_ppcm_from_calibration(w, h)
            if ppcm_cal is not None:
                return float(ppcm_cal)
            base_ppcm = 60.0
            ppcm = base_ppcm * (w / 700.0)
            return float(np.clip(ppcm, 20.0, 200.0))
        except Exception:
            return None

    def _estimate_pixels_per_cm_from_mask(self, mask: np.ndarray, assumed_wound_width_cm: float) -> Optional[float]:
        """Estimate pixels-per-cm from the wound mask using distance transform thickness.

        Strategy:
        - Compute distance transform on the binary mask (city-block approximation via 3x3 kernel)
        - Local thickness ≈ 2 * distance at mask interior points
        - Use a robust central quantile (25–40 percentile) to avoid inflated regions from expansion
        - pixels_per_cm = median_thickness_px / assumed_wound_width_cm
        - Clamp to a sensible range to avoid extreme scales
        """
        try:
            if mask is None or mask.size == 0 or cv2.countNonZero(mask) < 50:
                return None

            median_thickness_px = self._estimate_core_thickness_px(mask)
            if not np.isfinite(median_thickness_px) or median_thickness_px <= 0:
                return None

            ppcm = float(median_thickness_px / max(assumed_wound_width_cm, 1e-3))
            # Clamp to reasonable image scales
            ppcm = float(np.clip(ppcm, 20.0, 400.0))
            return ppcm
        except Exception:
            return None

    def _estimate_core_thickness_px(self, mask: np.ndarray) -> Optional[float]:
        """Estimate the core (local) wound thickness in pixels using distance transform quantiles."""
        try:
            mask_u8 = (mask > 0).astype(np.uint8) * 255
            dist = cv2.distanceTransform(mask_u8, cv2.DIST_L2, 3)
            nonzero = dist[dist > 0.5]
            if nonzero.size < 30:
                return None
            thickness_px = nonzero * 2.0
            q_low = np.percentile(thickness_px, 10)
            q_high = np.percentile(thickness_px, 25)
            core_band = thickness_px[(thickness_px >= q_low) & (thickness_px <= q_high)]
            if core_band.size < 10:
                core_band = thickness_px
            return float(np.median(core_band))
        except Exception:
            return None
    
    def _analyze_color(self, image: np.ndarray, mask: np.ndarray) -> Dict:
        """Analyze color characteristics of the wound area."""
        # Extract wound pixels
        wound_pixels = image[mask > 0]
        
        if len(wound_pixels) == 0:
            return {
                "dominant_color": [0, 0, 0],
                "color_description": "unknown",
                "redness_level": 0.0,
                "darkness_level": 0.0
            }
        
        # Calculate average color
        avg_color = np.mean(wound_pixels, axis=0)
        
        # Convert to HSV for better color analysis
        avg_color_hsv = cv2.cvtColor(np.uint8([[avg_color]]), cv2.COLOR_BGR2HSV)[0, 0]
        
        # Analyze color characteristics
        hue = avg_color_hsv[0]
        saturation = avg_color_hsv[1] / 255.0
        brightness = avg_color_hsv[2] / 255.0
        
        # Determine color description
        if hue < 10 or hue > 170:  # Red range
            if saturation > 0.3:
                color_desc = "red/inflamed"
            else:
                color_desc = "pink/healing"
        elif 10 <= hue < 30:  # Yellow/orange range
            color_desc = "yellow/infected"
        elif 30 <= hue < 85:  # Green range
            color_desc = "green/infected"
        else:  # Blue/purple range
            color_desc = "dark/necrotic"
        
        # Calculate metrics
        redness_level = saturation if (hue < 10 or hue > 170) else 0.0
        darkness_level = 1.0 - brightness
        
        return {
            "dominant_color": [int(c) for c in avg_color],
            "color_description": color_desc,
            "redness_level": round(redness_level, 2),
            "darkness_level": round(darkness_level, 2)
        }
    
    def _assess_healing(self, measurements: Dict, color_analysis: Dict) -> Dict:
        """Assess wound healing status and provide comprehensive treatment guidance."""
        # Comprehensive healing assessment
        concerns = []
        healing_indicators = []
        severity = "mild"
        healing_stage = "inflammatory"
        healing_progress = "normal"
        
        # Size-based assessment
        area_cm2 = measurements.get("area_cm2", 0)
        length_cm = measurements.get("length_cm", 0)
        width_cm = measurements.get("width_cm", 0)

        # --- Small wound safety gate ---
        SMALL_WOUND_AREA_CM2 = 1.0
        SMALL_WOUND_LENGTH_CM = 2.5

        is_small_wound = (
            area_cm2 < SMALL_WOUND_AREA_CM2 and
            length_cm < SMALL_WOUND_LENGTH_CM
        )
        
        if area_cm2 > 15:
            concerns.append("Very large wound area requiring specialized care")
            severity = "severe"
            healing_stage = "chronic"
        elif area_cm2 > 8:
            concerns.append("Large wound area - extended healing time expected")
            severity = "moderate"
        elif area_cm2 > 3:
            concerns.append("Moderate wound size")
            if severity == "mild":
                severity = "moderate"
        
        # Aspect ratio assessment
        if length_cm > 0 and width_cm > 0:
            aspect_ratio = max(length_cm, width_cm) / min(length_cm, width_cm)
            if aspect_ratio > 3:
                concerns.append("Irregular wound shape may complicate healing")
        
        # Color-based healing assessment
        color_desc = color_analysis.get("color_description", "")
        redness = color_analysis.get("redness_level", 0)
        darkness = color_analysis.get("darkness_level", 0)
        
        # Determine healing stage and progress
        if "pink" in color_desc or "healing" in color_desc:
            healing_indicators.append("Healthy pink coloration")
            healing_stage = "proliferative"
            healing_progress = "good"
        
        elif "red" in color_desc:
            healing_stage = "inflammatory"

            if redness > 0.8:
                concerns.append("Marked inflammation observed")

                # Only escalate to severe if NOT a small wound
                if not is_small_wound:
                    severity = "severe"
                    healing_progress = "delayed"
                else:
                    healing_progress = "normal"

            elif redness > 0.5:
                healing_indicators.append("Moderate inflammation - normal healing response")
            else:
                healing_indicators.append("Mild inflammation")
        
        if "yellow" in color_desc or "infected" in color_desc:
            concerns.append("Yellow discoloration suggests possible infection")
            severity = "severe"
            healing_progress = "impaired"
        
        if "green" in color_desc:
            concerns.append("Green coloration indicates bacterial infection")
            severity = "severe"
            healing_progress = "infected"
        
        if "dark" in color_desc or "necrotic" in color_desc or darkness > 0.7:
            concerns.append("Dark tissue suggests necrosis or poor circulation")
            severity = "severe"
            healing_progress = "compromised"
        
        # Generate comprehensive recommendations
        recommendations = self._generate_treatment_recommendations(
            severity, healing_stage, concerns, color_desc=color_analysis.get("color_description", "")
        )

        # Predict healing time window
        healing_prediction = self._predict_healing_time(measurements, severity, healing_stage, color_analysis)

        # Infection likelihood and stitches/closure assessment
        infection_risk = self._estimate_infection_risk(measurements, severity, healing_stage, color_analysis)
        stitches = self._assess_stitches_need(measurements, severity, healing_stage, color_analysis)
        scar_risk = self._estimate_scar_risk(measurements, severity, healing_stage, color_analysis)
        
        return {
            "healing_stage": healing_stage,
            "healing_progress": healing_progress,
            "severity": severity,
            "concerns": concerns,
            "healing_indicators": healing_indicators,
            "recommendations": recommendations,
            "healing_time_prediction": healing_prediction,
            "infection_risk": infection_risk,
            "stitches": stitches,
            "scar_risk": scar_risk,
            "overall_assessment": self._generate_overall_assessment(severity, healing_stage, area_cm2)
        }
    
    def _generate_treatment_recommendations(self, severity: str, healing_stage: str, concerns: list, color_desc: str = "") -> Dict:
        """Generate detailed treatment recommendations."""
        immediate_care = []
        ongoing_care = []
        warning_signs = []
        follow_up = ""
        medications = {
            "healing_aids": [],
            "pain_management": [],
            "cautions": []
        }
        
        # Basic wound care for all wounds
        immediate_care.extend([
            "Clean hands thoroughly before wound care",
            "Gently clean wound with saline solution or clean water",
            "Pat dry with clean, sterile gauze"
        ])
        
        # Severity-specific immediate care
        if severity == "severe":
            immediate_care.extend([
                "Seek immediate medical attention",
                "Do not delay professional evaluation",
                "Take photos to track changes"
            ])
            follow_up = "Consult healthcare provider within 24 hours"
        elif severity == "moderate":
            immediate_care.extend([
                "Apply appropriate wound dressing",
                "Monitor closely for changes"
            ])
            follow_up = "Consult healthcare provider within 48-72 hours"
        else:
            immediate_care.extend([
                "Apply clean, dry dressing",
                "Keep wound elevated if possible"
            ])
            follow_up = "Monitor for 3-5 days, seek care if no improvement"
        
        # Stage-specific ongoing care
        if healing_stage == "inflammatory":
            ongoing_care.extend([
                "Change dressing daily or when soiled",
                "Keep wound moist but not waterlogged",
                "Avoid picking at scabs or debris",
                "Take anti-inflammatory medication if recommended by doctor"
            ])
        elif healing_stage == "proliferative":
            ongoing_care.extend([
                "Continue moist wound healing environment",
                "Change dressing every 2-3 days unless soiled",
                "Gently massage around wound edges to promote circulation",
                "Ensure adequate nutrition and hydration"
            ])
        elif healing_stage == "chronic":
            ongoing_care.extend([
                "Strict adherence to wound care protocol",
                "Regular debridement may be necessary",
                "Address underlying health conditions",
                "Consider advanced wound care products"
            ])
        
        # Universal ongoing care
        ongoing_care.extend([
            "Maintain good nutrition with adequate protein",
            "Stay hydrated",
            "Avoid smoking and excessive alcohol",
            "Protect wound from further trauma"
        ])

        # Medications and products (OTC/general guidance)
        medications["healing_aids"].extend([
            "Sterile saline for gentle cleaning (avoid hydrogen peroxide or iodine unless directed)",
            "Plain petroleum jelly to keep the wound moist and prevent scab cracking",
            "Non-adherent dressing (e.g., Telfa) with gauze or a hydrocolloid pad for shallow wounds",
        ])
        # Optional: topical antibiotic for short-term in contaminated minor cuts
        if severity in ("mild", "moderate"):
            medications["healing_aids"].append("Optional: brief use of an OTC topical antibiotic if risk of contamination and no allergy—discontinue if irritation occurs")

        # Pain management (OTC)
        medications["pain_management"].extend([
            "Acetaminophen for pain (follow label dosing; avoid if liver disease unless cleared)",
            "Ibuprofen or naproxen for pain/swelling if not pregnant and no bleeding/stomach/kidney issues",
        ])
        medications["cautions"].extend([
            "If signs of infection (increasing redness, warmth, pus, fever), seek medical care promptly",
            "Allergies or chronic conditions may limit OTC options; when unsure, consult a clinician"
        ])
        
        # Warning signs to monitor
        warning_signs.extend([
            "Increasing pain, redness, or swelling",
            "Pus or unusual discharge",
            "Foul odor from wound",
            "Red streaking from wound site",
            "Fever or feeling unwell",
            "Wound becoming larger or deeper",
            "No improvement after 5-7 days"
        ])
        
        # Concern-specific warnings
        if any("infection" in concern.lower() for concern in concerns):
            warning_signs.extend([
                "Spreading warmth around wound",
                "Yellow or green discharge",
                "Swollen lymph nodes"
            ])
        
        return {
            "immediate_care": immediate_care,
            "ongoing_care": ongoing_care,
            "warning_signs": warning_signs,
            "follow_up": follow_up,
            "medications": medications
        }

    def _predict_healing_time(self, measurements: Dict, severity: str, stage: str, color_analysis: Dict) -> Dict:
        """Predict a rough healing-time window (days) based on simple heuristics.

        This is an estimate only and not a medical diagnosis. Factors considered:
        - Area and length (larger/longer wounds take more time)
        - Healing stage (proliferative typically shorter than inflammatory/chronic)
        - Severity and color indicators (very red/yellow may indicate longer course)
        """
        area = float(measurements.get("area_cm2", 0.0) or 0.0)
        length = float(measurements.get("length_cm", 0.0) or 0.0)
        redness = float(color_analysis.get("redness_level", 0.0) or 0.0)  # 0..1

        # Base window by size
        if area < 0.5 and length < 2.0:
            base = (3, 7)
        elif area < 2.0 and length < 5.0:
            base = (7, 14)
        elif area < 6.0:
            base = (14, 28)
        else:
            base = (21, 42)

        # Stage adjustments
        if stage == "proliferative":
            base = (max(2, int(base[0] * 0.8)), int(base[1] * 0.9))
        elif stage == "chronic":
            base = (int(base[0] * 1.2), int(base[1] * 1.5))

        # Severity adjustments
        if severity == "severe":
            base = (int(base[0] * 1.3), int(base[1] * 1.6))
        elif severity == "moderate":
            base = (int(base[0] * 1.1), int(base[1] * 1.2))

        # Redness/inflammation weight
        if redness > 0.7:
            base = (int(base[0] * 1.1), int(base[1] * 1.25))
        elif redness < 0.2:
            base = (max(2, int(base[0] * 0.9)), int(base[1] * 0.95))

        # Confidence heuristic
        span = base[1] - base[0]
        confidence = "high" if span <= 7 else "medium" if span <= 14 else "low"
        return {
            "predicted_days_min": int(base[0]),
            "predicted_days_max": int(base[1]),
            "confidence": confidence,
            "notes": "Estimate only; varies with age, comorbidities, and wound care adherence."
        }

    def _estimate_infection_risk(self, measurements: Dict, severity: str, stage: str, color_analysis: Dict) -> Dict:
        """Compute a simple infection-likelihood score based on color cues and size.

        Heuristic combining redness, yellow/green percentages, darkness, stage, and size.
        Returns score 0-100 and qualitative level.
        """
        factors = []
        area = float(measurements.get("area_cm2", 0.0) or 0.0)
        redness = float(color_analysis.get("redness_level", 0.0) or 0.0)  # 0..1
        darkness = float(color_analysis.get("darkness_level", 0.0) or 0.0)  # 0..1
        cper = color_analysis.get("color_percentages", {})
        yellow = float(cper.get("yellow", 0.0) or 0.0)
        green = float(cper.get("green", 0.0) or 0.0)

        score = 0.0
        score += redness * 45.0
        if yellow > 0:
            score += min(yellow * 1.2, 25.0)
            factors.append("yellow coloration")
        if green > 0:
            score += min(green * 3.0, 25.0)
            factors.append("green coloration")
        if darkness > 0.7:
            score += 10.0
            factors.append("dark/necrotic tissue")
        if area > 3:
            score += 8.0
        if area > 8:
            score += 7.0
        if severity == "severe":
            score += 7.0
        if stage == "inflammatory":
            score += 4.0

        score = float(np.clip(score, 0.0, 100.0))
        if score < 30:
            level = "low"
        elif score < 60:
            level = "moderate"
        elif score < 80:
            level = "high"
        else:
            level = "very high"

        return {"score": int(round(score)), "level": level, "factors": factors}

    def _assess_stitches_need(self, measurements: Dict, severity: str, stage: str, color_analysis: Dict) -> Dict:
        """Heuristic assessment if wound may need stitches/closure.

        Uses length/width thresholds and inflammation to suggest closure.
        """
        length = float(measurements.get("length_cm", 0.0) or 0.0)
        width = float(measurements.get("width_cm", 0.0) or 0.0)
        redness = float(color_analysis.get("redness_level", 0.0) or 0.0)
        reasons = []

        SMALL_WOUND_AREA_CM2 = 1.0
        SMALL_WOUND_LENGTH_CM = 2.5
        area = float(measurements.get("area_cm2", 0.0) or 0.0)

        if area < SMALL_WOUND_AREA_CM2 and length < SMALL_WOUND_LENGTH_CM:
            return {
                "need_stitches": False,
                "recommendation": "Small superficial wound — stitches not indicated",
                "reasons": ["Small size without gaping"]
            }

        # Slightly raised thresholds with a "require both" primary condition
        L_REQ = 3.0
        W_REQ = 0.6
        W_EXTREME = 0.8

        need = False
        if (length >= L_REQ and width >= W_REQ):
            need = True; reasons.append(f"length ≥ {L_REQ} cm AND width ≥ {W_REQ} cm")
        elif width >= W_EXTREME:
            need = True; reasons.append(f"gaping width ≥ {W_EXTREME} cm")
        elif (length >= 2.0 and width >= 0.4 and redness > 0.6):
            need = True; reasons.append("gaping with notable inflammation")
        elif severity == "severe":
            need = True; reasons.append("severe presentation")

        recommendation = "May heal naturally with proper care" if not need else "Likely requires sutures/closure—seek medical evaluation within 6–8 hours"
        return {"need_stitches": bool(need), "recommendation": recommendation, "reasons": reasons}

    def _estimate_scar_risk(self, measurements: Dict, severity: str, stage: str, color_analysis: Dict) -> Dict:
        """Estimate scar risk and provide preventive care tips."""
        length = float(measurements.get("length_cm", 0.0) or 0.0)
        width = float(measurements.get("width_cm", 0.0) or 0.0)
        area = float(measurements.get("area_cm2", 0.0) or 0.0)
        redness = float(color_analysis.get("redness_level", 0.0) or 0.0)
        darkness = float(color_analysis.get("darkness_level", 0.0) or 0.0)

        score = 0.0
        score += min(length / 5.0, 1.0) * 40.0
        score += min(width / 1.0, 1.0) * 25.0
        score += min(area / 8.0, 1.0) * 15.0
        score += redness * 10.0
        score += (1.0 if stage == "chronic" else 0.0) * 10.0
        score += (1.0 if severity == "severe" else 0.0) * 10.0
        if darkness > 0.6:
            score += 10.0

        score = float(np.clip(score, 0.0, 100.0))
        if score < 35:
            level = "low"
        elif score < 70:
            level = "moderate"
        else:
            level = "high"

        tips = [
            "Keep moist during early healing (petroleum jelly + non-adherent dressing)",
            "Avoid tension across the wound; protect from stretching",
            "After closure/epithelialization: consider silicone gel/sheets for 6–8 weeks",
            "Sun protection (SPF 30+) for at least 3–6 months to reduce hyperpigmentation",
            "Gentle massage around edges after closure to improve pliability"
        ]

        return {"risk": level, "score": int(round(score)), "tips": tips}
    
    def _generate_overall_assessment(self, severity: str, healing_stage: str, area_cm2: float) -> str:
        """Generate overall clinical assessment."""
        size_desc = "small" if area_cm2 < 2 else "moderate" if area_cm2 < 8 else "large"
        
        assessment = f"This is a {size_desc} wound ({area_cm2:.1f} cm²) in the {healing_stage} stage of healing. "
        
        if severity == "mild":
            assessment += "The wound shows signs of normal healing progression. Continue current care routine and monitor for improvement."
        elif severity == "moderate":
            assessment += "The wound requires close monitoring and may benefit from professional wound care guidance."
        else:
            assessment += "This wound requires immediate professional medical attention due to size, appearance, or signs of complications."
        
        return assessment


def analyze_wound_image(image_path: str, pixels_per_cm: float = 45.0, save_visual: bool = True, output_dir: str = "output") -> Dict:
    """
    Convenience function to analyze a wound image.
    
    Args:
        image_path: Path to the wound image
        pixels_per_cm: Conversion factor from pixels to centimeters
        save_visual: Whether to save visual output with bounding boxes
        output_dir: Directory to save visual outputs
        
    Returns:
        Dictionary containing complete wound analysis
    """
    # Prefer Roboflow (cloud) if configured, else local ML checkpoint, else CV analyzer
    rf = get_roboflow_config()
    default_model_path = (Path(__file__).resolve().parents[1] / "models" / "tiny_wound_model.pt")
    if rf.get("api_key") and rf.get("model_id"):
        try:
            analyzer = RoboflowWoundAnalyzer(pixels_per_cm=pixels_per_cm)
        except Exception:
            # If Roboflow init fails, fall back to local model / CV
            analyzer = MLWoundAnalyzer(model_path=str(default_model_path), pixels_per_cm=pixels_per_cm) if default_model_path.exists() else WoundAnalyzer(pixels_per_cm=pixels_per_cm)
    elif default_model_path.exists():
        analyzer = MLWoundAnalyzer(model_path=str(default_model_path), pixels_per_cm=pixels_per_cm)
    else:
        analyzer = WoundAnalyzer(pixels_per_cm=pixels_per_cm)
    result = analyzer.analyze_wound(image_path, save_visual=save_visual, output_dir=output_dir)
    
    # Auto-print results to console
    _print_analysis_results(image_path, result)
    
    return result


def _print_analysis_results(image_path: str, result: Dict) -> None:
    """Print analysis results to console."""
    from pathlib import Path
    
    print("\n" + "="*60)
    print("WOUNDSYNC - AUTOMATIC ANALYSIS RESULTS")
    print("="*60)
    print(f"Image: {Path(image_path).name}")
    
    # 1. Detection Status
    print(f"\n[1] WOUND DETECTION:")
    print(f"    Status: {'DETECTED' if result.get('wound_detected') else 'NOT DETECTED'}")
    print(f"    Confidence: {result.get('confidence', 0)*100:.0f}%")
    print(f"    Method: {result.get('method', 'Unknown')}")
    
    # 2. Measurements
    measurements = result.get('measurements', {})
    if measurements:
        print(f"\n[2] MEASUREMENTS:")
        print(f"    Length: {measurements.get('length_cm')} cm")
        print(f"    Width: {measurements.get('width_cm')} cm")
        print(f"    Area: {measurements.get('area_cm2')} cm²")
        print(f"    Height: {measurements.get('height_cm')} cm")
        if 'measurement_mode' in measurements:
            print(f"    Mode: {measurements.get('measurement_mode')}")
    
    # 3. Color Analysis
    color_analysis = result.get('color_analysis', {})
    if color_analysis:
        print(f"\n[3] COLOR ANALYSIS:")
        dominant_color = color_analysis.get('dominant_color', [0, 0, 0])
        print(f"    Dominant Color (RGB): {dominant_color}")
        print(f"    Description: {color_analysis.get('color_description')}")
        print(f"    Redness Level: {color_analysis.get('redness_level', 0)*100:.1f}%")
        
        color_percentages = color_analysis.get('color_percentages', {})
        if color_percentages:
            print(f"    Color Distribution:")
            for color, percentage in color_percentages.items():
                print(f"      - {color.title()}: {percentage}%")
    
    # 4. Healing Assessment
    healing = result.get('healing_assessment', {})
    if healing:
        print(f"\n[4] HEALING ASSESSMENT:")
        print(f"    Stage: {healing.get('healing_stage', 'Unknown').upper()}")
        print(f"    Progress: {healing.get('healing_progress', 'Unknown').upper()}")
        print(f"    Severity: {healing.get('severity', 'Unknown').upper()}")
        
        concerns = healing.get('concerns', [])
        if concerns:
            print(f"    Clinical Concerns:")
            for i, concern in enumerate(concerns, 1):
                print(f"      {i}. {concern}")
        
        indicators = healing.get('healing_indicators', [])
        if indicators:
            print(f"    Positive Signs:")
            for i, indicator in enumerate(indicators, 1):
                print(f"      {i}. {indicator}")

        # Added: Infection, stitches, scar risk
        inf = healing.get('infection_risk') or {}
        if inf:
            print(f"    Infection Likelihood: {inf.get('level','n/a').upper()} ({inf.get('score','n/a')}%)")
        stitch = healing.get('stitches') or {}
        if stitch:
            status = 'LIKELY NEEDS STITCHES' if stitch.get('need_stitches') else 'LIKELY HEALS NATURALLY'
            print(f"    Closure: {status}")
        scar = healing.get('scar_risk') or {}
        if scar:
            print(f"    Scar Risk: {scar.get('risk','n/a').upper()} ({scar.get('score','n/a')}%)")
            tips = scar.get('tips') or []
            if tips:
                print(f"      Tips: {tips[0]}")
    
    # 5. Treatment Summary
    recommendations = result.get('recommendations', {})
    if recommendations:
        print(f"\n[5] TREATMENT SUMMARY:")
        
        immediate_care = recommendations.get('immediate_care', [])
        if immediate_care and len(immediate_care) > 0:
            print(f"    Next Action: {immediate_care[0]}")
        
        follow_up = recommendations.get('follow_up', '')
        if follow_up:
            print(f"    Follow-up: {follow_up}")
        meds = recommendations.get('medications', {})
        if meds:
            print(f"    Medications:")
            if meds.get('healing_aids'):
                print(f"      - Healing aids: {', '.join(meds['healing_aids'][:3])}")
            if meds.get('pain_management'):
                print(f"      - Pain relief: {', '.join(meds['pain_management'][:2])}")
            if meds.get('cautions'):
                print(f"      - Cautions: {meds['cautions'][0]}")
    
    # 6. Clinical Summary
    overall = result.get('overall_assessment', '')
    if overall:
        print(f"\n[6] CLINICAL SUMMARY:")
        print(f"    {overall}")

    # 7. Healing Time Prediction
    hpred = result.get('healing_assessment', {}).get('healing_time_prediction')
    if hpred:
        print(f"\n[7] HEALING TIME PREDICTION:")
        print(f"    Estimated: {hpred.get('predicted_days_min')}–{hpred.get('predicted_days_max')} days (confidence: {hpred.get('confidence','n/a')})")
        note = hpred.get('notes')
        if note:
            print(f"    Note: {note}")

    # 8. Calibration
    calib = result.get('calibration', {})
    if calib:
        print(f"\n[8] CALIBRATION:")
        print(f"    Mode: {calib.get('mode', 'n/a')}")
        print(f"    Pixels per cm (ppcm): {calib.get('ppcm', 'n/a')}")
    
    print(f"\n" + "="*60)
    print("ANALYSIS COMPLETE - Results printed to console")
    print("="*60 + "\n")


# For future ML model integration
class MLWoundAnalyzer(WoundAnalyzer):
    """ML-based wound analyzer using a trained lightweight segmentation model.

    Falls back to traditional CV if the model file is missing or fails to load.
    """

    def __init__(self, model_path: Optional[str] = None, pixels_per_cm: float = 45.0, auto_calibrate: bool = True, assumed_wound_width_cm: float = 0.3):
        super().__init__(pixels_per_cm=pixels_per_cm, auto_calibrate=auto_calibrate, assumed_wound_width_cm=assumed_wound_width_cm)
        self.model_path = model_path or str((Path(__file__).resolve().parents[1] / "models" / "tiny_wound_model.pt").resolve())
        self.segmenter = None
        # Advertise ML method in printed results
        self.method_name = "ML Segmentation Model"

        try:
            from training.fast_inference import FastWoundSegmenter  # type: ignore
            if Path(self.model_path).exists():
                self.segmenter = FastWoundSegmenter(self.model_path)
            else:
                print(f"[ML] Model file not found at {self.model_path} — using CV fallback.")
        except Exception as e:
            print(f"[ML] Could not initialize ML segmenter: {e}. Using CV fallback.")
            self.segmenter = None

    def _segment_wound(self, image: np.ndarray) -> np.ndarray:
        """Use ML model for segmentation if available, otherwise fallback to CV."""
        try:
            if self.segmenter is not None:
                from PIL import Image
                import cv2
                h, w = image.shape[:2]
                # Convert OpenCV BGR image to PIL RGB
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                # Call the segmenter's internal ML path directly
                mask, _info = self.segmenter._ml_segment(pil_img, (w, h))  # pylint: disable=protected-access
                mask_u8 = (mask > 0).astype(np.uint8) * 255

                # Light post-processing: small close/open and border safety
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel, iterations=1)
                mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel, iterations=1)

                # Clear a 1% border to avoid frame-hugging artifacts
                border = max(3, int(0.01 * min(h, w)))
                mask_u8[:border, :] = 0
                mask_u8[-border:, :] = 0
                mask_u8[:, :border] = 0
                mask_u8[:, -border:] = 0

                # If ML returns empty, try CV fallback on this image
                if cv2.countNonZero(mask_u8) == 0:
                    cv_mask = super()._segment_wound(image)
                    if cv2.countNonZero(cv_mask) > 0:
                        # Update method label to reflect fallback
                        self.method_name = "Traditional Computer Vision (fallback)"
                        return cv_mask
                return mask_u8
        except Exception as e:
            print(f"[ML] Inference failed ({e}); falling back to CV.")

        # Fallback to traditional CV method
        return super()._segment_wound(image)


class RoboflowWoundAnalyzer(WoundAnalyzer):
    """Cloud inference via Roboflow Inference SDK (segmentation)."""

    def __init__(self, pixels_per_cm: float = 45.0, auto_calibrate: bool = True, assumed_wound_width_cm: float = 0.3):
        super().__init__(pixels_per_cm=pixels_per_cm, auto_calibrate=auto_calibrate, assumed_wound_width_cm=assumed_wound_width_cm)
        self.method_name = "Roboflow Cloud Model"
        cfg = get_roboflow_config()
        self.rf_cfg = cfg
        try:
            from .roboflow_inference import RoboflowSegmenter  # type: ignore
            if not cfg.get("api_key") or not cfg.get("model_id"):
                raise ValueError("Roboflow API key or model id missing")
            self.segmenter = RoboflowSegmenter(api_key=cfg["api_key"], model_id=cfg["model_id"], api_url=cfg.get("api_url", "https://serverless.roboflow.com"))
        except Exception as e:
            print(f"[Roboflow] Init failed: {e}. Falling back to CV.")
            self.segmenter = None

    def _segment_wound(self, image: np.ndarray) -> np.ndarray:
        try:
            if self.segmenter is not None:
                # We need a file path for the SDK call; write to a temporary PNG in memory or disk
                import tempfile
                import cv2
                import os
                h, w = image.shape[:2]
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    cv2.imwrite(tmp_path, image)
                    mask, info = self.segmenter.segment(tmp_path)  # returns uint8 mask at original size
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                mask_u8 = (mask > 0).astype(np.uint8) * 255
                # Clean-up similar to ML path
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel, iterations=1)
                mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel, iterations=1)
                border = max(3, int(0.01 * min(h, w)))
                mask_u8[:border, :] = 0
                mask_u8[-border:, :] = 0
                mask_u8[:, :border] = 0
                mask_u8[:, -border:] = 0

                if cv2.countNonZero(mask_u8) == 0:
                    # Cloud returned empty; try CV fallback
                    self.method_name = "Traditional Computer Vision (fallback)"
                    return super()._segment_wound(image)
                return mask_u8
        except Exception as e:
            print(f"[Roboflow] Inference failed ({e}); falling back to CV.")
        return super()._segment_wound(image)
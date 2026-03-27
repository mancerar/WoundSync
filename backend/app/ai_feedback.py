"""
AI-powered clinical feedback module for wound analysis.

Primary provider:
- Gemini 2.5 Flash (Google GenAI)

Fallback:
- None (AI-only mode for current setup)
"""

import json
import mimetypes
import os
import re
import base64
from pathlib import Path
from typing import Dict, List, Optional
import warnings

import requests

# Medical disclaimer constant
MEDICAL_DISCLAIMER = """
⚠️ IMPORTANT MEDICAL DISCLAIMER ⚠️

This analysis is for INFORMATIONAL and EDUCATIONAL purposes only.
It is NOT a medical diagnosis, treatment plan, or substitute for 
professional medical advice.

ALWAYS consult a qualified healthcare provider for:
- Any wound that is deep, large (>2cm), or won't stop bleeding
- Signs of infection (redness spreading, pus, fever, red streaks)
- Wounds from dirty objects, animal bites, or punctures
- Wounds that don't improve within 48-72 hours
- If you have diabetes, immune disorders, or take blood thinners

If unsure, seek medical care immediately. When in doubt, call your
doctor or visit urgent care/emergency department.

AI-generated content may contain errors. Use at your own risk.
"""

class AIFeedbackGenerator:
    """Generate clinical feedback using Gemini with safety overrides."""
    
    def __init__(self, use_ai: bool = True, model_name: Optional[str] = None):
        """
        Initialize AI feedback generator.
        
        Args:
            use_ai: Whether to attempt AI-powered feedback
            model_name: Specific Gemini model to use (defaults to GEMINI_MODEL or gemini-2.5-flash)
        """
        self.provider = "none"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/")

        self.use_ai = bool(use_ai)
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        if self.use_ai and self.gemini_api_key:
            self.provider = "gemini"
            print(f"[AI Feedback] Using Gemini model: {self.model_name}")
            return

        self.use_ai = False
        self.provider = "none"
        print("[AI Feedback] Gemini unavailable - AI-only mode has no fallback")
    
    def generate_full_assessment(self, wound_data: Dict) -> Dict:
        """
        Generate a complete wound assessment using AI.

        Returns a dict matching all fields the frontend expects.

        Returned structure:
          healing_stage, healing_progress, severity, concerns, healing_indicators,
          overall_assessment, infection_risk, healing_time_prediction, stitches,
          scar_risk, recommendations (immediate_care, ongoing_care, medications,
          warning_signs, follow_up), assessment_method
        """
        if not self.use_ai or self.provider != "gemini":
            raise RuntimeError("Gemini AI feedback is not configured. Set GEMINI_API_KEY and GEMINI_MODEL.")
        try:
            return self._get_ai_assessment(wound_data)
        except Exception as e:
            warnings.warn(f"AI assessment failed: {e}")
            raise

    # Keep old method name as alias for any existing callers
    def generate_clinical_assessment(self, wound_data: Dict) -> Dict:
        result = self.generate_full_assessment(wound_data)
        return {
            'assessment_method': result.get('assessment_method', 'AI-powered'),
            'clinical_feedback': result,
            'safety_overrides': self._apply_safety_overrides(wound_data),
            'disclaimer': MEDICAL_DISCLAIMER,
            'ai_available': True
        }
    
    def _get_ai_assessment(self, wound_data: Dict) -> Dict:
        return self._get_gemini_assessment(wound_data)

    def _get_gemini_assessment(self, wound_data: Dict) -> Dict:
        """
        Two-step image-grounded Gemini assessment:
          Step 1 - Complete analysis: AI analyzes image and provides all information
          Step 2 - Structured output: AI converts its analysis into JSON with measurements
        """
        print(f"[AI Feedback] === _get_gemini_assessment called ===")
        print(f"[AI Feedback] wound_data keys: {list(wound_data.keys())}")
        
        image_path = wound_data.get('image_path')
        print(f"[AI Feedback] Extracted image_path: {image_path}")
        
        if not image_path:
            raise ValueError("Gemini assessment requires image_path in wound_data")

        image_file = Path(image_path)
        if not image_file.exists() or not image_file.is_file():
            raise FileNotFoundError(f"Image not found for Gemini analysis: {image_path}")

        image_bytes = image_file.read_bytes()
        if not image_bytes:
            raise ValueError(f"Image file is empty: {image_path}")

        # ── STEP 1: Complete Analysis with image ──────────────────────────────
        analysis_prompt = self._build_vision_analysis_prompt(wound_data)
        print(f"[AI Feedback] Step 1: Gemini analyzing image for complete assessment...")
        print(f"[AI Feedback] Image path: {image_path}")
        print(f"[AI Feedback] Image file exists: {image_file.exists()}")
        print(f"[AI Feedback] Image file size: {len(image_bytes)} bytes")
        
        try:
            clinical_analysis = self._gemini_generate_text(
                prompt=analysis_prompt,
                image_path=str(image_file),
                max_tokens=1200,  # Increased from 800 for more detailed observations
                response_json=False,
            )
            print(f"[AI Feedback] Step 1 successful: {len(clinical_analysis)} characters")
            print(f"[AI Feedback] Step 1 observations (first 500 chars): {clinical_analysis[:500]}")
        except RuntimeError as e:
            error_msg = str(e)
            print(f"[AI Feedback] Gemini Step 1 failed: {error_msg}")
            raise RuntimeError(f"Gemini AI analysis failed: {error_msg}")

        print(f"[AI Feedback] Step 2: Converting to structured JSON...")

        # ── STEP 2: Convert the observations into structured JSON ─────────────────
        # CRITICAL: Pass the image to Step 2 so Gemini can extract accurate measurements
        json_prompt = self._build_json_from_analysis_prompt(clinical_analysis, wound_data)
        
        try:
            ai_text = self._gemini_generate_text(
                prompt=json_prompt,
                image_path=str(image_file),  # CRITICAL: Include image in Step 2
                max_tokens=3000,  # Increased from 1500 to prevent truncation
                response_json=True,
            )
            print(f"[AI Feedback] Step 2 successful: {len(ai_text)} characters")
            print(f"[AI Feedback] Step 2 raw JSON: {ai_text}")
        except RuntimeError as e:
            error_msg = str(e)
            print(f"[AI Feedback] Gemini Step 2 failed: {error_msg}")
            raise RuntimeError(f"Gemini AI structured output failed: {error_msg}")

        result = self._parse_ai_response(ai_text, wound_data)
        print(f"[AI Feedback] Gemini observations - measurements: {result.get('measurements', {})}")
        print(f"[AI Feedback] Gemini observations - injury type: {result.get('injury_classification', {})}")
        
        result['ai_reasoning'] = clinical_analysis
        
        # Apply rule engine to generate clinical recommendations from observations
        result = self._apply_clinical_rules(result)
        print(f"[AI Feedback] After rules - measurements: {result.get('measurements', {})}")
        
        result['assessment_method'] = 'AI-powered (Gemini + Clinical Rules)'
        
        # Ensure measurements and color_analysis are at the top level for frontend
        if 'measurements' not in result:
            result['measurements'] = {"length_cm": 0, "width_cm": 0, "area_cm2": 0}
        if 'color_analysis' not in result:
            result['color_analysis'] = {"color_description": "unknown", "color_percentages": {}}
            
        return result

    def _build_vision_analysis_prompt(self, wound_data: Dict) -> str:
        """Build a prompt for Gemini to provide OBSERVATIONS ONLY (no clinical recommendations)."""
        return """You are a medical imaging specialist analyzing a clinical photograph of a skin injury.

Provide OBJECTIVE OBSERVATIONS ONLY (no treatment recommendations):

1. MEASUREMENTS - Carefully estimate from the image:
   - Length in centimeters (longest dimension of the injury)
   - Width in centimeters (perpendicular to length, or average width for irregular shapes)
   - Area in square centimeters (length × width for rectangular shapes, or visual estimate for irregular shapes)
   - IMPORTANT: Be accurate with measurements. Reference guide:
     * Tiny cut/scrape: 0.5-1 cm
     * Small cut: 1-2 cm
     * Moderate laceration: 2-4 cm
     * Large laceration: 4-8 cm
     * Very large wound: >8 cm

2. DEPTH ASSESSMENT (CRITICAL for closure decisions):
   - Does it appear superficial (epidermis only) or deep (into dermis/subcutaneous tissue)?
   - Are the edges gaping (separated/open) or approximated (touching/closed)?
   - Can you see underlying tissue, fat, muscle, or deeper structures?
   - Is there visible tissue separation or a gap between wound edges?
   - Description of depth and edge characteristics

3. VISUAL CHARACTERISTICS:
   - Tissue colors present and their approximate percentages (red, pink, yellow, brown, black, green)
     * CRITICAL: Each pixel can only be ONE color - percentages MUST add up to exactly 100%
     * Colors are mutually exclusive - if a pixel is red, it cannot also be pink
     * Be specific and accurate: "red: 70%, pink: 20%, brown: 10%" (total = 100%)
     * INVALID: "red: 60%, pink: 50%" (total = 110% - impossible!)
   - Tissue types visible (blood, dermis, epithelial tissue, granulation tissue, slough, eschar, etc.)
   - Edge characteristics (clean/jagged, sharp/rounded, approximated/separated, etc.)
   - Surrounding skin appearance (normal, inflamed, discolored, etc.)

4. INJURY CLASSIFICATION:
   - Type: Be specific - laceration, abrasion, puncture, surgical incision, burn, ulcer, etc.
   - Freshness: 
     * Fresh = bright red blood, sharp edges, active bleeding, recent trauma
     * Healing = pink/yellow tissue, granulation, rounded edges, scab formation
   - Age estimate: Hours old (fresh blood), days old (scab/granulation), weeks old (scar tissue)

5. SIGNS PRESENT:
   - Inflammation indicators (redness, swelling, warmth)
   - Infection indicators (pus, purulent discharge, spreading erythema, green tissue, foul odor)
   - Healing indicators (granulation tissue, epithelialization, contraction, scab formation)
   - Concerning features (necrotic tissue, exposed structures, foreign material, bone/tendon visible)

BE SPECIFIC AND ACCURATE:
- Measurements must be realistic (don't say 0.0 cm)
- Color percentages must add up to ~100%
- Depth assessment is critical for determining if closure is needed
- Classify injury type accurately (laceration vs abrasion vs puncture makes a big difference)
- Fresh vs healing status affects all treatment decisions

Provide only factual observations. Do not make treatment recommendations or clinical judgments."""

    def _gemini_generate_text(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        max_tokens: int = 1000,
        response_json: bool = False,
    ) -> str:
        """Generate text with Gemini REST API and return plain text content."""
        if not self.gemini_api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

        url = f"{self.gemini_base_url}/models/{self.model_name}:generateContent?key={self.gemini_api_key}"

        parts: List[Dict] = [{"text": prompt}]
        if image_path:
            p = Path(image_path)
            if not p.exists() or not p.is_file():
                raise FileNotFoundError(f"Image not found for Gemini: {image_path}")
            mime_type, _ = mimetypes.guess_type(str(p))
            mime = mime_type or "image/jpeg"
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": b64,
                }
            })

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.2,  # Low temperature for consistent measurements while maintaining quality
                "topP": 0.95,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json" if response_json else "text/plain",
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
            ],
        }

        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        print(f"[AI Feedback] Gemini API response keys: {list(data.keys())}")
        
        candidates = data.get("candidates", [])
        if not candidates:
            # Check if there's a safety rating blocking the response
            prompt_feedback = data.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason")
            safety_ratings = prompt_feedback.get("safetyRatings", [])
            
            print(f"[AI Feedback] Gemini blocked - Block reason: {block_reason}")
            print(f"[AI Feedback] Gemini blocked - Safety ratings: {json.dumps(safety_ratings, indent=2)}")
            print(f"[AI Feedback] Gemini blocked - Full prompt feedback: {json.dumps(prompt_feedback, indent=2)}")
            
            if block_reason:
                raise RuntimeError(f"Gemini blocked the request: {block_reason}. Safety ratings: {safety_ratings}")
            raise RuntimeError("Gemini API returned no candidates")

        chunks: List[str] = []
        for cand in candidates:
            content = cand.get("content", {}) if isinstance(cand, dict) else {}
            for part in content.get("parts", []) if isinstance(content, dict) else []:
                text = part.get("text") if isinstance(part, dict) else None
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())

        if chunks:
            full_text = "\n".join(chunks)
            # Clean up any incomplete JSON
            if response_json and full_text:
                # Try to fix common JSON issues
                full_text = full_text.strip()
                # If it starts with { but doesn't end with }, try to find the last complete object
                if full_text.startswith('{') and not full_text.endswith('}'):
                    # Find the last complete closing brace
                    last_brace = full_text.rfind('}')
                    if last_brace > 0:
                        full_text = full_text[:last_brace + 1]
            return full_text

        raise RuntimeError("Gemini returned empty content")

    def _build_json_from_analysis_prompt(self, clinical_analysis: str, wound_data: Dict) -> str:
        """
        Step 2 prompt: convert Gemini's observations into structured JSON.
        Gemini provides observations only - rule engine will generate recommendations.
        """
        return f"""You previously analyzed this injury image and provided these observations:

"{clinical_analysis}"

Now, looking at the SAME IMAGE again, provide a complete JSON response with accurate measurements and observations.

CRITICAL MEASUREMENT INSTRUCTIONS:
1. LOOK AT THE IMAGE and measure BOTH length AND width
2. Length = longest dimension of the injury in centimeters
3. Width = perpendicular dimension (or average width for irregular shapes) in centimeters
4. Area = length × width (or visual estimate for irregular shapes) in square centimeters
5. DO NOT leave width as 0.0 - you MUST measure it from the image
6. DO NOT leave area as 0.0 - you MUST calculate it

CRITICAL COLOR INSTRUCTIONS:
1. Color percentages MUST add up to exactly 100%
2. If you see red=60%, pink=30%, then the remaining 10% should be distributed to other colors
3. DO NOT have overlapping colors (red=60%, pink=50% is impossible - they can't both be present)
4. Be accurate: if the wound is mostly red with some pink, use red=70%, pink=25%, other=5%

JSON FORMAT:

{{
  "measurements": {{
    "length_cm": 0.0,  // REQUIRED: Measure longest dimension from image
    "width_cm": 0.0,   // REQUIRED: Measure perpendicular dimension from image (NOT 0!)
    "area_cm2": 0.0    // REQUIRED: Calculate length × width (NOT 0!)
  }},
  "depth_assessment": {{
    "appears_deep": false,  // Does it look deep (into dermis) or superficial?
    "edges_gaping": false,  // Are the wound edges separated/gaping?
    "description": "brief description of depth and edge characteristics"
  }},
  "tissue_observations": {{
    "colors_present": {{"red": 0, "pink": 0, "yellow": 0, "brown": 0, "black": 0, "green": 0, "other": 0}},  // MUST add to EXACTLY 100% - each pixel can only be ONE color
    "tissue_types": ["list of tissue types you can see"],
    "edge_characteristics": "description of wound edges"
  }},
  "injury_classification": {{
    "type": "laceration|abrasion|puncture|surgical|burn|ulcer|other",
    "freshness": "fresh|healing",
    "estimated_age": "hours|days|weeks"
  }},
  "signs_observed": {{
    "inflammation": ["list any inflammation signs you see"],
    "infection": ["list any infection signs like pus, green tissue, spreading redness"],
    "healing": ["list any healing signs like granulation, epithelialization"],
    "concerning_features": ["list any concerning features like necrotic tissue, exposed structures"]
  }}
}}

VALIDATION CHECKLIST BEFORE RESPONDING:
✓ width_cm is NOT 0.0 (you measured it from the image)
✓ area_cm2 is NOT 0.0 (you calculated length × width)
✓ Color percentages add up to EXACTLY 100% (use a calculator: red + pink + yellow + brown + black + green + other = 100)
✓ Each pixel is counted ONCE (if 60% is red, then only 40% remains for all other colors combined)
✓ Colors are mutually exclusive (a pixel cannot be both "red" and "pink" - pick the dominant color)

EXAMPLE VALID COLOR PERCENTAGES:
- Mostly red wound: {{"red": 70, "pink": 20, "brown": 10}} = 100% ✓
- Pink healing wound: {{"pink": 60, "red": 25, "yellow": 10, "brown": 5}} = 100% ✓
- INVALID: {{"red": 60, "pink": 50, "brown": 20}} = 130% ✗ (impossible - colors overlap!)

Provide ONLY the JSON object, no additional text."""

    def _parse_ai_response(self, ai_text: str, wound_data: Dict) -> Dict:
        """Parse the AI JSON response into a structured dict."""
        try:
            # Try to parse as JSON
            parsed = json.loads(ai_text)
            print(f"[AI Feedback] Successfully parsed JSON response with {len(parsed)} fields")
            print(f"[AI Feedback] Parsed measurements: {parsed.get('measurements', {})}")
            
            # Validate and normalize color percentages
            tissue_obs = parsed.get('tissue_observations', {})
            colors = tissue_obs.get('colors_present', {})
            if colors:
                total = sum(colors.values())
                print(f"[AI Feedback] Color percentages total: {total}%")
                
                # If colors don't add up to 100%, normalize them
                if total > 0 and abs(total - 100) > 1:  # Allow 1% tolerance
                    print(f"[AI Feedback] Normalizing color percentages from {total}% to 100%")
                    normalized = {k: round((v / total) * 100, 1) for k, v in colors.items()}
                    # Ensure they add up to exactly 100% after rounding
                    normalized_total = sum(normalized.values())
                    if abs(normalized_total - 100) > 0.1:
                        # Adjust the largest color to make it exactly 100%
                        largest_color = max(normalized.keys(), key=lambda k: normalized[k])
                        normalized[largest_color] = round(normalized[largest_color] + (100 - normalized_total), 1)
                    tissue_obs['colors_present'] = normalized
                    print(f"[AI Feedback] Normalized colors: {normalized}")
            
            return parsed
        except json.JSONDecodeError as e:
            print(f"[AI Feedback] JSON parsing failed: {e}")
            print(f"[AI Feedback] Raw AI response length: {len(ai_text)} characters")
            print(f"[AI Feedback] Raw AI response (first 2000 chars): {ai_text[:2000]}")
            
            # Try to extract and fix incomplete JSON
            json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                print(f"[AI Feedback] Extracted JSON string length: {len(json_str)}")
                
                # Try to fix incomplete JSON by adding missing closing braces
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                open_brackets = json_str.count('[')
                close_brackets = json_str.count(']')
                
                print(f"[AI Feedback] Braces: {open_braces} open, {close_braces} close")
                print(f"[AI Feedback] Brackets: {open_brackets} open, {close_brackets} close")
                
                # Add missing closing brackets and braces
                if open_brackets > close_brackets:
                    json_str += ']' * (open_brackets - close_brackets)
                if open_braces > close_braces:
                    json_str += '}' * (open_braces - close_braces)
                
                try:
                    parsed = json.loads(json_str)
                    print(f"[AI Feedback] Fixed and parsed incomplete JSON with {len(parsed)} fields")
                    print(f"[AI Feedback] Fixed measurements: {parsed.get('measurements', {})}")
                    
                    # Validate and normalize color percentages for fixed JSON too
                    tissue_obs = parsed.get('tissue_observations', {})
                    colors = tissue_obs.get('colors_present', {})
                    if colors:
                        total = sum(colors.values())
                        if total > 0 and abs(total - 100) > 1:
                            normalized = {k: round((v / total) * 100, 1) for k, v in colors.items()}
                            normalized_total = sum(normalized.values())
                            if abs(normalized_total - 100) > 0.1:
                                largest_color = max(normalized.keys(), key=lambda k: normalized[k])
                                normalized[largest_color] = round(normalized[largest_color] + (100 - normalized_total), 1)
                            tissue_obs['colors_present'] = normalized
                    
                    return parsed
                except json.JSONDecodeError as e2:
                    print(f"[AI Feedback] Failed to fix incomplete JSON: {e2}")
                    print(f"[AI Feedback] Attempted fix (last 500 chars): {json_str[-500:]}")
            
            print(f"[AI Feedback] WARNING: Using empty observations - rule engine will use defaults")
            # Return minimal structure so rule engine can work
            return {
                "measurements": {"length_cm": 0, "width_cm": 0, "area_cm2": 0},
                "depth_assessment": {"appears_deep": False, "edges_gaping": False, "description": ""},
                "tissue_observations": {"colors_present": {}, "tissue_types": [], "edge_characteristics": ""},
                "injury_classification": {"type": "unknown", "freshness": "unknown", "estimated_age": "unknown"},
                "signs_observed": {"inflammation": [], "infection": [], "healing": [], "concerning_features": []}
            }
    
    def _apply_clinical_rules(self, gemini_observations: Dict) -> Dict:
        """
        Apply clinical rules to Gemini's observations to generate accurate recommendations.
        
        Takes raw observations from Gemini and applies evidence-based clinical guidelines
        to determine healing stage, infection risk, stitch needs, treatment plans, etc.
        """
        print(f"[Rule Engine] === Starting clinical rules application ===")
        print(f"[Rule Engine] Input observations keys: {list(gemini_observations.keys())}")
        
        # Extract Gemini's observations
        measurements = gemini_observations.get('measurements', {})
        depth = gemini_observations.get('depth_assessment', {})
        tissue = gemini_observations.get('tissue_observations', {})
        injury_class = gemini_observations.get('injury_classification', {})
        signs = gemini_observations.get('signs_observed', {})
        
        length_cm = float(measurements.get('length_cm', 0))
        width_cm = float(measurements.get('width_cm', 0))
        area_cm2 = float(measurements.get('area_cm2', 0))
        
        print(f"[Rule Engine] Extracted measurements: length={length_cm}, width={width_cm}, area={area_cm2}")
        
        appears_deep = depth.get('appears_deep', False)
        edges_gaping = depth.get('edges_gaping', False)
        
        print(f"[Rule Engine] Depth assessment: appears_deep={appears_deep}, edges_gaping={edges_gaping}")
        
        colors = tissue.get('colors_present', {})
        
        # Normalize color percentages if they don't add up to 100%
        if colors:
            total = sum(colors.values())
            print(f"[Rule Engine] Color percentages total: {total}%")
            
            if total > 0 and abs(total - 100) > 1:  # Allow 1% tolerance
                print(f"[Rule Engine] WARNING: Colors don't add to 100%, normalizing from {total}%")
                colors = {k: round((v / total) * 100, 1) for k, v in colors.items()}
                # Ensure exactly 100% after rounding
                normalized_total = sum(colors.values())
                if abs(normalized_total - 100) > 0.1:
                    largest_color = max(colors.keys(), key=lambda k: colors[k])
                    colors[largest_color] = round(colors[largest_color] + (100 - normalized_total), 1)
                print(f"[Rule Engine] Normalized colors: {colors}")
        
        red_pct = float(colors.get('red', 0))
        pink_pct = float(colors.get('pink', 0))
        yellow_pct = float(colors.get('yellow', 0))
        green_pct = float(colors.get('green', 0))
        black_pct = float(colors.get('black', 0))
        
        injury_type = injury_class.get('type', 'unknown')
        freshness = injury_class.get('freshness', 'unknown')
        age = injury_class.get('estimated_age', 'unknown')
        
        inflammation_signs = signs.get('inflammation', [])
        infection_signs = signs.get('infection', [])
        healing_signs = signs.get('healing', [])
        concerning_features = signs.get('concerning_features', [])
        
        # === RULE ENGINE: HEALING STAGE ===
        print(f"[Rule Engine] Healing stage assessment - freshness={freshness}, age={age}, red={red_pct}%, pink={pink_pct}%")
        print(f"[Rule Engine] Healing signs: {healing_signs}")
        print(f"[Rule Engine] Tissue types: {tissue.get('tissue_types', [])}")
        
        # Inflammatory stage: Fresh wounds, high redness, minimal healing tissue
        if freshness == 'fresh' or age == 'hours':
            # But check colors - if mostly pink, it's actually healing
            if pink_pct > 60 and red_pct < 30:
                healing_stage = 'proliferative'
                healing_progress = 'normal'
                print(f"[Rule Engine] Stage: proliferative (colors show healing despite 'fresh' classification)")
            else:
                healing_stage = 'inflammatory'
                healing_progress = 'normal'
                print(f"[Rule Engine] Stage: inflammatory (fresh wound)")
        elif red_pct > 80 and pink_pct < 15 and yellow_pct < 10:
            healing_stage = 'inflammatory'
            healing_progress = 'normal'
            print(f"[Rule Engine] Stage: inflammatory (high redness, minimal healing tissue)")
        # Proliferative stage: Granulation tissue, pink tissue, active healing
        elif pink_pct > 40 or 'granulation' in str(healing_signs).lower() or 'granulation' in str(tissue.get('tissue_types', [])).lower():
            healing_stage = 'proliferative'
            healing_progress = 'normal'
            print(f"[Rule Engine] Stage: proliferative (granulation/pink tissue)")
        elif yellow_pct > 20 and pink_pct > 20:
            healing_stage = 'proliferative'
            healing_progress = 'normal'
            print(f"[Rule Engine] Stage: proliferative (yellow + pink tissue)")
        # Remodeling stage: Scar tissue, weeks old
        elif 'scar' in str(healing_signs).lower() or age == 'weeks':
            healing_stage = 'remodeling'
            healing_progress = 'normal'
            print(f"[Rule Engine] Stage: remodeling (scar tissue/weeks old)")
        else:
            # Default to inflammatory for unclear cases
            healing_stage = 'inflammatory'
            healing_progress = 'normal'
            print(f"[Rule Engine] Stage: inflammatory (default)")
        
        # === RULE ENGINE: SEVERITY ===
        severity_score = 0
        
        print(f"[Rule Engine] Severity assessment - area={area_cm2}, length={length_cm}, type={injury_type}")
        
        # Size-based severity - use length if area is missing/zero
        effective_size = area_cm2 if area_cm2 > 0 else (length_cm * 0.5)  # Estimate area if missing
        
        if effective_size > 10:
            severity_score += 3
        elif effective_size > 5:
            severity_score += 2
        elif effective_size > 2:
            severity_score += 1
        
        # Length-based severity (important for lacerations)
        if length_cm >= 3.0:
            severity_score += 2
            print(f"[Rule Engine] +2 severity: length >= 3.0cm")
        elif length_cm >= 2.0:
            severity_score += 1
            print(f"[Rule Engine] +1 severity: length >= 2.0cm")
        
        # Depth and gaping significantly increase severity - but only for larger wounds
        # Small wounds (<0.5 cm²) don't get severity boost from gaping
        if appears_deep and area_cm2 >= 0.5:
            severity_score += 2
            print(f"[Rule Engine] +2 severity: wound appears deep")
        if edges_gaping and area_cm2 >= 0.5:
            severity_score += 2
            print(f"[Rule Engine] +2 severity: edges gaping")
        
        # Infection signs increase severity
        if len(infection_signs) > 2:
            severity_score += 2
        elif len(infection_signs) > 0:
            severity_score += 1
        
        # Concerning features increase severity
        if len(concerning_features) > 0:
            severity_score += 1
        
        # Fresh lacerations with high redness and significant length
        if injury_type == 'laceration' and freshness == 'fresh' and length_cm >= 2.5 and red_pct > 50:
            severity_score += 1
            print(f"[Rule Engine] +1 severity: fresh laceration >= 2.5cm with redness")
        
        print(f"[Rule Engine] Severity score: {severity_score}")
        
        if severity_score >= 5:
            severity = 'severe'
        elif severity_score >= 3:
            severity = 'moderate'
        else:
            severity = 'mild'
        
        print(f"[Rule Engine] Severity level: {severity}")
        
        # === RULE ENGINE: INFECTION RISK ===
        infection_score = 0
        infection_factors = []
        
        print(f"[Rule Engine] Infection assessment - colors: red={red_pct}%, yellow={yellow_pct}%, green={green_pct}%")
        print(f"[Rule Engine] Infection signs: {infection_signs}")
        print(f"[Rule Engine] Inflammation signs: {inflammation_signs}")
        
        # Green tissue is a STRONG infection indicator
        if green_pct > 5:
            infection_score += 40
            infection_factors.append('green tissue present')
        
        # Yellow tissue - context matters
        if yellow_pct > 30:
            infection_score += 25
            infection_factors.append('significant yellow tissue')
        elif yellow_pct > 15:
            infection_score += 10
            infection_factors.append('moderate yellow tissue')
        
        # Purulent discharge is CRITICAL
        if 'pus' in str(infection_signs).lower() or 'purulent' in str(infection_signs).lower():
            infection_score += 35
            infection_factors.append('purulent discharge')
        
        # Spreading redness is concerning
        if 'spreading' in str(infection_signs).lower() or 'erythema' in str(infection_signs).lower():
            infection_score += 20
            infection_factors.append('spreading redness')
        
        # Inflammation in fresh wounds is NORMAL, but still worth noting
        if freshness == 'fresh' and len(inflammation_signs) > 0:
            infection_score += 5  # Minimal score - fresh wounds have normal inflammation
            infection_factors.append('normal inflammatory response in fresh wound')
            print(f"[Rule Engine] Fresh wound with inflammation - normal healing response")
        
        # High redness in fresh wounds is NORMAL, not infection
        if red_pct > 70 and freshness == 'fresh':
            infection_score += 0  # Fresh wounds are naturally red - NOT infection
            print(f"[Rule Engine] High redness ({red_pct}%) but fresh wound - NOT counting as infection")
        elif red_pct > 70:
            infection_score += 15
            infection_factors.append('excessive redness in non-fresh wound')
        
        infection_score = min(infection_score, 100)
        
        print(f"[Rule Engine] Infection score: {infection_score}, factors: {infection_factors}")
        
        if infection_score < 30:
            infection_level = 'low'
        elif infection_score < 60:
            infection_level = 'moderate'
        else:
            infection_level = 'high'
        
        print(f"[Rule Engine] Infection level: {infection_level}")
        
        # === RULE ENGINE: STITCH ASSESSMENT ===
        need_stitches = False
        stitch_reasons = []
        
        print(f"[Rule Engine] Stitch assessment - injury_type={injury_type}, freshness={freshness}, length={length_cm}")
        print(f"[Rule Engine] Depth/gaping: appears_deep={appears_deep}, edges_gaping={edges_gaping}")
        print(f"[Rule Engine] Colors: red={red_pct}%, pink={pink_pct}%")
        
        # Validate freshness against color analysis
        # Fresh wounds should be mostly red (>50%), healing wounds are mostly pink
        color_based_freshness = freshness
        if pink_pct > 60 and red_pct < 30:
            color_based_freshness = 'healing'
            print(f"[Rule Engine] Overriding freshness to 'healing' based on colors (pink={pink_pct}%, red={red_pct}%)")
        elif red_pct > 70 and pink_pct < 20:
            color_based_freshness = 'fresh'
            print(f"[Rule Engine] Confirming freshness as 'fresh' based on colors (red={red_pct}%, pink={pink_pct}%)")
        
        # Fresh laceration criteria - AGGRESSIVE thresholds for proper wound closure
        if injury_type == 'laceration' and color_based_freshness == 'fresh':
            # Very aggressive criteria for fresh lacerations
            if length_cm >= 2.5:
                need_stitches = True
                stitch_reasons.append(f'fresh laceration {length_cm:.1f}cm requires closure')
                print(f"[Rule Engine] STITCHES NEEDED: length {length_cm}cm >= 2.5cm")
            elif length_cm >= 1.5 and (appears_deep or edges_gaping):
                need_stitches = True
                stitch_reasons.append(f'fresh laceration {length_cm:.1f}cm with depth/gaping')
                print(f"[Rule Engine] STITCHES NEEDED: length {length_cm}cm >= 1.5cm with depth/gaping")
            elif length_cm >= 1.0 and edges_gaping:
                need_stitches = True
                stitch_reasons.append(f'fresh laceration {length_cm:.1f}cm with gaping edges')
                print(f"[Rule Engine] STITCHES NEEDED: length {length_cm}cm >= 1.0cm with gaping")
            elif length_cm >= 0.8 and appears_deep and red_pct > 70:
                need_stitches = True
                stitch_reasons.append(f'fresh deep laceration {length_cm:.1f}cm with high redness')
                print(f"[Rule Engine] STITCHES NEEDED: length {length_cm}cm >= 0.8cm with depth+redness")
            elif appears_deep and edges_gaping:
                need_stitches = True
                stitch_reasons.append('deep wound with gaping edges requires closure')
                print(f"[Rule Engine] STITCHES NEEDED: deep + gaping")
            else:
                print(f"[Rule Engine] NO STITCHES: length={length_cm}, deep={appears_deep}, gaping={edges_gaping}, red={red_pct}%")
        
        # Puncture wounds - different criteria
        elif injury_type == 'puncture' and appears_deep:
            need_stitches = False  # Punctures usually shouldn't be closed (infection risk)
            stitch_reasons.append('puncture wounds typically should not be closed due to infection risk')
        
        # Other wound types with concerning depth
        elif injury_type in ['surgical', 'burn', 'ulcer']:
            need_stitches = False  # These have specialized closure needs
            stitch_reasons.append(f'{injury_type} wounds require specialized medical evaluation')
        
        # Already healing - too late for stitches
        if healing_stage in ['proliferative', 'remodeling']:
            need_stitches = False
            stitch_reasons = ['wound already healing - too late for primary closure']
        
        print(f"[Rule Engine] Stitch decision: need_stitches={need_stitches}, reasons={stitch_reasons}")
        
        if need_stitches:
            stitch_recommendation = f"This fresh laceration ({length_cm:.1f} cm) should be evaluated for closure within 6-8 hours. {' '.join(stitch_reasons)}"
        else:
            if stitch_reasons:
                stitch_recommendation = f"Stitches not needed. {' '.join(stitch_reasons)}"
            else:
                stitch_recommendation = "This injury can heal naturally with proper wound care."
        
        # === RULE ENGINE: HEALING TIME ===
        # Base healing time on area and severity
        if area_cm2 < 1 and severity == 'mild':
            healing_days = (3, 10)
        elif area_cm2 < 2 and severity == 'mild':
            healing_days = (5, 14)
        elif area_cm2 < 3:
            healing_days = (7, 14)
        elif area_cm2 < 5:
            healing_days = (10, 21)
        elif area_cm2 < 8:
            healing_days = (14, 28)
        else:
            healing_days = (21, 42)
        
        # Adjust for depth and gaping (delays healing) - but only for larger wounds
        # Small wounds (<0.5 cm²) heal quickly even if gaping
        if (appears_deep or edges_gaping) and area_cm2 >= 0.5:
            healing_days = (int(healing_days[0] * 1.3), int(healing_days[1] * 1.5))
        
        # Adjust for infection
        if infection_level == 'high':
            healing_days = (int(healing_days[0] * 1.5), int(healing_days[1] * 2))
        elif infection_level == 'moderate':
            healing_days = (int(healing_days[0] * 1.2), int(healing_days[1] * 1.5))
        
        # Adjust for wound type - only for larger gaping lacerations
        if injury_type == 'laceration' and not need_stitches and edges_gaping and area_cm2 >= 1.0:
            # Gaping lacerations without closure heal slower
            healing_days = (int(healing_days[0] * 1.4), int(healing_days[1] * 1.6))
        
        print(f"[Rule Engine] Healing time: {healing_days[0]}-{healing_days[1]} days")
        
        # === RULE ENGINE: SCAR RISK ===
        scar_score = 0
        
        # Length increases scar risk
        if length_cm > 5:
            scar_score += 35
        elif length_cm > 3:
            scar_score += 25
        elif length_cm > 1.5:
            scar_score += 15
        
        # Depth and gaping significantly increase scar risk
        if appears_deep:
            scar_score += 25
        if edges_gaping:
            scar_score += 20
        
        # Area increases scar risk
        if area_cm2 > 10:
            scar_score += 25
        elif area_cm2 > 5:
            scar_score += 15
        
        # Not getting stitches when needed increases scar risk
        if not need_stitches and (appears_deep or edges_gaping) and length_cm > 1.5:
            scar_score += 20
        
        # Infection increases scar risk
        if infection_level == 'high':
            scar_score += 15
        elif infection_level == 'moderate':
            scar_score += 10
        
        scar_score = min(scar_score, 100)
        
        print(f"[Rule Engine] Scar score: {scar_score}")
        
        if scar_score < 30:
            scar_level = 'low'
        elif scar_score < 65:
            scar_level = 'moderate'
        else:
            scar_level = 'high'
        
        print(f"[Rule Engine] Scar risk: {scar_level}")
        
        scar_tips = "Keep the wound moist during healing, protect from sun exposure after closure, and consider silicone sheets or scar massage once fully healed."
        
        # === BUILD FRONTEND-COMPATIBLE RESPONSE ===
        result = {
            'measurements': measurements,
            'color_analysis': {
                'color_description': self._generate_color_description(colors),
                'color_percentages': colors,
                'health_indicators': {
                    'healthy_pink_present': pink_pct > 20,
                    'excessive_redness': red_pct > 70 and freshness != 'fresh',
                    'signs_of_infection': infection_level in ['moderate', 'high'] or green_pct > 5,  # Only show warning for actual infection risk
                    'necrotic_tissue': black_pct > 10
                }
            },
            'healing_stage': healing_stage,
            'healing_progress': healing_progress,
            'severity': severity,
            'healing_indicators': self._format_healing_indicators(healing_signs),
            'concerns': self._format_concerns(concerning_features, infection_signs),
            'infection_risk': {
                'level': infection_level,
                'score': infection_score,
                'reasoning': f"{', '.join(infection_factors)}." if infection_factors else 'No significant infection indicators observed. Fresh wounds naturally show redness and inflammation as part of normal healing.'
            },
            'healing_time_prediction': {
                'predicted_days_min': healing_days[0],
                'predicted_days_max': healing_days[1],
                'confidence': 'medium',
                'notes': 'Estimate based on wound characteristics and healing stage'
            },
            'stitches': {
                'need_stitches': need_stitches,
                'recommendation': stitch_recommendation
            },
            'scar_risk': {
                'risk': scar_level,
                'score': scar_score,
                'tips': scar_tips
            },
            'recommendations': self._generate_treatment_recommendations_from_rules(
                severity, healing_stage, infection_level, need_stitches,
                injury_type, appears_deep, edges_gaping
            ),
            'overall_assessment': self._generate_clinical_summary(
                injury_type, freshness, length_cm, area_cm2, healing_stage, 
                severity, infection_level, need_stitches, appears_deep, edges_gaping
            ),
            'gemini_observations': gemini_observations  # Keep raw observations for debugging
        }
        
        print(f"[Rule Engine] === Final result ===")
        print(f"[Rule Engine] Measurements: {result['measurements']}")
        print(f"[Rule Engine] Severity: {result['severity']}")
        print(f"[Rule Engine] Infection: {result['infection_risk']['level']} ({result['infection_risk']['score']}%)")
        print(f"[Rule Engine] Stitches: {result['stitches']['need_stitches']}")
        
        return result
    
    def _generate_color_description(self, colors: Dict) -> str:
        """Generate a color description from percentages."""
        if not colors:
            return "unknown"
        
        sorted_colors = sorted(colors.items(), key=lambda x: x[1], reverse=True)
        if not sorted_colors or sorted_colors[0][1] < 1:
            return "unknown"
        
        primary = sorted_colors[0][0]
        primary_pct = sorted_colors[0][1]
        
        # More nuanced descriptions based on color combinations
        if primary == 'red':
            if primary_pct > 80:
                return 'bright red/fresh'
            elif colors.get('pink', 0) > 20:
                return 'red-pink/healing'
            else:
                return 'red/inflamed'
        elif primary == 'pink':
            if colors.get('red', 0) > 30:
                return 'pink-red/early healing'
            else:
                return 'pink/healing'
        elif primary == 'yellow':
            if colors.get('green', 0) > 5:
                return 'yellow-green/concerning'
            else:
                return 'yellow/slough'
        elif primary == 'brown':
            return 'brown/scab'
        elif primary == 'black':
            return 'dark/necrotic'
        elif primary == 'green':
            return 'green/infected'
        else:
            return f"{primary}"
    
    def _format_healing_indicators(self, healing_signs: List) -> str:
        """Format healing indicators into a conversational paragraph."""
        if not healing_signs or len(healing_signs) == 0:
            return "Wound is progressing through normal healing stages."
        
        # Convert list to string if needed
        if isinstance(healing_signs, list):
            signs_text = ', '.join(str(s) for s in healing_signs)
        else:
            signs_text = str(healing_signs)
        
        # Make it conversational
        if signs_text:
            return f"Positive healing signs observed: {signs_text}."
        return "Wound is progressing through normal healing stages."
    
    def _format_concerns(self, concerning_features: List, infection_signs: List) -> str:
        """Format concerns into a conversational paragraph."""
        all_concerns = []
        
        if concerning_features and len(concerning_features) > 0:
            if isinstance(concerning_features, list):
                # Filter out empty strings and "none" variations
                filtered = [str(c) for c in concerning_features if c and str(c).strip().lower() not in ['none', 'none observed', '']]
                all_concerns.extend(filtered)
            else:
                concern_str = str(concerning_features).strip()
                if concern_str and concern_str.lower() not in ['none', 'none observed']:
                    all_concerns.append(concern_str)
        
        if infection_signs and len(infection_signs) > 0:
            if isinstance(infection_signs, list):
                # Filter out empty strings and "none" variations
                filtered = [str(s) for s in infection_signs if s and str(s).strip().lower() not in ['none', 'none observed', '']]
                all_concerns.extend(filtered)
            else:
                sign_str = str(infection_signs).strip()
                if sign_str and sign_str.lower() not in ['none', 'none observed']:
                    all_concerns.append(sign_str)
        
        if not all_concerns:
            return "No significant concerns identified. Continue monitoring for changes."
        
        # Make it conversational
        concerns_text = ', '.join(all_concerns)
        return f"Concerns identified: {concerns_text}. Monitor closely and seek medical attention if these worsen."
    
    def _generate_treatment_recommendations_from_rules(
        self, severity: str, healing_stage: str, infection_level: str, need_stitches: bool,
        injury_type: str = 'unknown', appears_deep: bool = False, edges_gaping: bool = False
    ) -> Dict:
        """Generate treatment recommendations based on clinical rules."""
        
        # Immediate care - context-aware based on wound characteristics
        if need_stitches:
            immediate_care = "Seek medical attention within 6-8 hours for wound closure evaluation. Until then, apply gentle pressure with clean gauze to control bleeding, clean gently with saline if available, and cover with a sterile dressing."
            if edges_gaping:
                immediate_care += " Keep the wound edges as close together as possible without forcing them."
        elif severity == 'severe' or infection_level == 'high':
            immediate_care = "Seek immediate medical attention. Clean the wound gently with saline or clean water, cover with a sterile dressing, and avoid applying any ointments until evaluated by a healthcare provider."
        elif appears_deep or edges_gaping:
            immediate_care = "Clean the wound thoroughly with saline or clean water. Apply gentle pressure if bleeding. Cover with a sterile dressing and consider medical evaluation within 24 hours."
        else:
            immediate_care = "Gently clean the wound with mild soap and water or saline solution. Pat dry with clean gauze, apply a thin layer of antibiotic ointment, and cover with a sterile non-stick dressing."
        
        # Ongoing care - specific to wound type and stage
        if infection_level == 'high':
            ongoing_care = "Change dressing twice daily or when soiled. Monitor closely for worsening signs. Keep the wound elevated when possible and avoid getting it wet until infection clears."
        elif injury_type == 'laceration' and (appears_deep or edges_gaping):
            ongoing_care = "Change dressing daily. Keep wound edges approximated with butterfly strips if not sutured. Minimize movement of the affected area to promote healing. Monitor for signs of infection or dehiscence (wound opening)."
        elif healing_stage == 'inflammatory':
            ongoing_care = "Change dressing daily or when soiled. Keep the wound clean and moist. Avoid picking at scabs. Monitor for signs of infection or delayed healing."
        elif healing_stage == 'proliferative':
            ongoing_care = "Change dressing every 1-2 days. Continue moist wound healing. Protect new tissue from trauma. Monitor for continued improvement."
        else:
            ongoing_care = "Change dressing every 1-2 days or when soiled. Continue keeping the wound moist and protected. Gentle cleaning with each dressing change."
        
        # Medications
        if infection_level == 'high':
            healing_aids = "Prescription antibiotic ointment as directed by healthcare provider."
            pain_management = "Acetaminophen or ibuprofen as needed for pain, following package directions."
        else:
            healing_aids = "Over-the-counter antibiotic ointment or petroleum jelly to keep wound moist."
            pain_management = "Acetaminophen or ibuprofen as needed for discomfort."
        
        cautions = "Avoid hydrogen peroxide or alcohol as they can damage healing tissue. Do not use antibiotic ointment if allergic."
        
        # Warning signs - more specific based on wound characteristics
        warning_signs = "Watch for increasing redness, warmth, swelling, pus or foul-smelling discharge, red streaks extending from the wound, fever, or worsening pain."
        if appears_deep or edges_gaping:
            warning_signs += " Also watch for wound edges separating further or any signs of deeper tissue exposure."
        warning_signs += " Seek immediate medical attention if any of these develop."
        
        # Follow-up
        if need_stitches or severity == 'severe':
            follow_up = "Seek medical evaluation today or within 6-8 hours"
        elif infection_level == 'high':
            follow_up = "Seek medical evaluation within 24 hours"
        elif infection_level == 'moderate' or severity == 'moderate':
            follow_up = "Follow up with healthcare provider within 3-5 days if not improving"
        else:
            follow_up = "Monitor for 5-7 days. Seek care if no improvement or if concerning signs develop"
        
        return {
            'immediate_care': immediate_care,
            'ongoing_care': ongoing_care,
            'medications': {
                'healing_aids': healing_aids,
                'pain_management': pain_management,
                'cautions': cautions
            },
            'warning_signs': warning_signs,
            'follow_up': follow_up
        }
    
    def _generate_clinical_summary(
        self, injury_type: str, freshness: str, length_cm: float, area_cm2: float,
        healing_stage: str, severity: str, infection_level: str, need_stitches: bool,
        appears_deep: bool = False, edges_gaping: bool = False
    ) -> str:
        """Generate overall clinical summary based on rules."""
        
        # Use actual measurements if available
        if length_cm <= 0 or area_cm2 <= 0:
            size_desc = "small"
            length_cm = 0.5  # Default for display
            area_cm2 = 0.1
        else:
            size_desc = "small" if area_cm2 < 2 else "moderate-sized" if area_cm2 < 8 else "large"
        
        fresh_desc = "fresh" if freshness == 'fresh' else "healing"
        injury_display = injury_type if injury_type and injury_type != 'unknown' else "injury"
        
        summary = f"This is a {size_desc} {fresh_desc} {injury_display} ({length_cm:.1f} cm length, {area_cm2:.2f} cm² area) "
        summary += f"in the {healing_stage} stage. "
        
        # Add depth/gaping information if relevant
        if appears_deep and edges_gaping:
            summary += "The wound appears deep with gaping edges. "
        elif appears_deep:
            summary += "The wound appears to extend into deeper tissue layers. "
        elif edges_gaping:
            summary += "The wound edges are separated. "
        
        if need_stitches:
            summary += "Professional wound closure is recommended. "
        
        if infection_level == 'high':
            summary += "High infection risk requires immediate medical evaluation. "
        elif infection_level == 'moderate':
            summary += "Moderate infection risk - monitor closely for worsening signs. "
        else:
            summary += "Low infection risk with proper care. "
        
        if severity == 'severe':
            summary += "Seek immediate medical attention."
        elif severity == 'moderate':
            summary += "Close monitoring and proper wound care are essential."
        else:
            summary += "Should heal well with proper home care."
        
        return summary
    
    def _post_process_result(self, result: Dict, wound_data: Dict) -> Dict:
        """Post-process the AI result to correct obvious errors."""
        # Ensure all required fields exist
        if 'assessment_method' not in result:
            result['assessment_method'] = 'AI-powered (Gemini)'
        
        # Ensure recommendations structure exists
        if 'recommendations' not in result:
            result['recommendations'] = {}
        
        recs = result['recommendations']
        if 'immediate_care' not in recs:
            recs['immediate_care'] = []
        if 'ongoing_care' not in recs:
            recs['ongoing_care'] = []
        if 'medications' not in recs:
            recs['medications'] = {}
        if 'warning_signs' not in recs:
            recs['warning_signs'] = []
        if 'follow_up' not in recs:
            recs['follow_up'] = "Monitor for improvement"
        
        # Ensure medications structure
        meds = recs['medications']
        if 'healing_aids' not in meds:
            meds['healing_aids'] = []
        if 'pain_management' not in meds:
            meds['pain_management'] = []
        if 'cautions' not in meds:
            meds['cautions'] = []
        
        return result
    
    def detect_wound_with_gemini(self, image_path: str, image_width: int, image_height: int) -> Optional[Dict]:
        """
        Use Gemini to detect if a wound exists in an image when Roboflow fails.
        Does NOT provide bounding box - just confirms wound presence.
        
        Returns:
            Dict with 'detected' (bool), 'confidence' (float), 'class' (str)
            or None if no wound detected
        """
        if not self.use_ai or self.provider != "gemini":
            return None
        
        detection_prompt = """You are analyzing a clinical photograph to detect if there is a wound, injury, cut, laceration, abrasion, or any skin damage present.

TASK:
1. Determine if there is ANY visible wound, injury, or skin damage in this image
2. Look VERY CAREFULLY - wounds might be VERY SMALL (tiny cuts, scrapes, pink marks, red spots)
3. Estimate your confidence level (0-100%)
4. Classify the wound type

RESPONSE FORMAT (JSON only):
{
  "wound_detected": true,
  "confidence": 85,
  "wound_type": "abrasion",
  "reasoning": "Small pink healing wound visible on ankle area"
}

If NO wound is visible, respond with:
{
  "wound_detected": false,
  "confidence": 0,
  "wound_type": "none",
  "reasoning": "No visible wound or injury in the image"
}

IMPORTANT: Look for SMALL wounds - even tiny marks, scratches, or discoloration count.

Provide ONLY the JSON object, no additional text."""

        try:
            ai_text = self._gemini_generate_text(
                prompt=detection_prompt,
                image_path=image_path,
                max_tokens=500,  # Reduced since we don't need bounding box
                response_json=False,
            )
            
            print(f"[AI Feedback] Gemini detection raw response: {ai_text}")
            
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
            if not json_match:
                print(f"[AI Feedback] No JSON found in Gemini response")
                return None
            
            json_str = json_match.group(0)
            detection_result = json.loads(json_str)
            print(f"[AI Feedback] Gemini detection result: {detection_result}")
            
            if not detection_result.get('wound_detected', False):
                print(f"[AI Feedback] Gemini says no wound detected: {detection_result.get('reasoning', 'no reason given')}")
                return None
            
            confidence = detection_result.get('confidence', 0) / 100.0  # Convert to 0-1 range
            
            return {
                'detected': True,
                'confidence': confidence,
                'class': detection_result.get('wound_type', 'wound'),
                'reasoning': detection_result.get('reasoning', 'Wound detected by Gemini AI')
            }
            
        except json.JSONDecodeError as e:
            print(f"[AI Feedback] Gemini detection JSON parse error: {e}")
            print(f"[AI Feedback] Raw response was: {ai_text[:500]}")
            return None
        except Exception as e:
            print(f"[AI Feedback] Gemini detection failed: {e}")
            return None
            
        except json.JSONDecodeError as e:
            print(f"[AI Feedback] Gemini detection JSON parse error: {e}")
            print(f"[AI Feedback] Raw response was: {ai_text[:500]}")
            return None
        except Exception as e:
            print(f"[AI Feedback] Gemini detection failed: {e}")
            return None
    
    def _apply_safety_overrides(self, wound_data: Dict) -> Dict:
        """Apply safety overrides based on wound characteristics."""
        overrides = {}
        
        # Check for severe conditions that require immediate medical attention
        c = wound_data.get('color_analysis', {})
        cper = c.get('color_percentages', {})
        
        # High infection risk indicators
        if cper.get('green', 0) > 10 or cper.get('yellow', 0) > 30:
            overrides['infection_warning'] = "Seek medical attention - signs of possible infection"
        
        # Necrotic tissue indicators
        if cper.get('black', 0) > 15:
            overrides['necrotic_warning'] = "Seek medical attention - necrotic tissue present"
        
        # Large wound size
        m = wound_data.get('measurements', {})
        area = m.get('area_cm2', 0)
        if area > 10:
            overrides['size_warning'] = "Large wound - consider professional medical evaluation"
        
        return overrides

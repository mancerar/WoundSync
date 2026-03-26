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
          Step 1 - Free-text analysis: AI reasons through the image
                   using both the image and numeric measurements.
          Step 2 - Structured output: AI converts its analysis into JSON.
        """
        image_path = wound_data.get('image_path')
        if not image_path:
            raise ValueError("Gemini assessment requires image_path in wound_data")

        image_file = Path(image_path)
        if not image_file.exists() or not image_file.is_file():
            raise FileNotFoundError(f"Image not found for Gemini analysis: {image_path}")

        image_bytes = image_file.read_bytes()
        if not image_bytes:
            raise ValueError(f"Image file is empty: {image_path}")

        # ── STEP 1: Analysis (free text) ───────────────────────────────────────
        analysis_prompt = self._build_vision_analysis_prompt(wound_data)
        print(f"[AI Feedback] Step 1: Analyzing image...")
        
        try:
            clinical_analysis = self._gemini_generate_text(
                prompt=analysis_prompt,
                image_path=str(image_file),
                max_tokens=500,
                response_json=False,
            )
            print(f"[AI Feedback] Step 1 successful: {len(clinical_analysis)} characters")
        except RuntimeError as e:
            error_msg = str(e)
            print(f"[AI Feedback] Gemini Step 1 failed: {error_msg}")
            raise RuntimeError(f"Gemini AI analysis failed: {error_msg}")

        print(f"[AI Feedback] Step 2: Generating structured output...")

        # ── STEP 2: Convert the analysis into structured JSON ─────────────────
        json_prompt = self._build_json_from_analysis_prompt(clinical_analysis, wound_data)
        
        try:
            ai_text = self._gemini_generate_text(
                prompt=json_prompt,
                max_tokens=3000,  # Increased from 2000 to prevent truncation
                response_json=True,
            )
            print(f"[AI Feedback] Step 2 successful: {len(ai_text)} characters")
        except RuntimeError as e:
            error_msg = str(e)
            print(f"[AI Feedback] Gemini Step 2 failed: {error_msg}")
            raise RuntimeError(f"Gemini AI structured output failed: {error_msg}")
        
        print(f"[AI Feedback] Gemini JSON response length: {len(ai_text)} characters")
        print(f"[AI Feedback] First 300 chars: {ai_text[:300]}")

        result = self._parse_ai_response(ai_text, wound_data)
        result['ai_reasoning'] = clinical_analysis
        # Post-process: correct obvious AI errors using raw color data
        result = self._post_process_result(result, wound_data)
        return result

    def _build_vision_analysis_prompt(self, wound_data: Dict) -> str:
        """Build a simple, focused prompt for Gemini that avoids medical terminology."""
        return (
            "Describe what you see in this image. Focus on:\n"
            "1. The appearance and characteristics\n"
            "2. Color and texture observations\n"
            "3. Size and shape\n"
            "4. Any notable features\n\n"
            "Keep your response brief and descriptive."
        )

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
                "temperature": 0.3,
                "topP": 0.9,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json" if response_json else "text/plain",
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }

        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            # Check if there's a safety rating blocking the response
            prompt_feedback = data.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason")
            if block_reason:
                raise RuntimeError(f"Gemini blocked the request: {block_reason}")
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

    def _build_analysis_prompt(self, wound_data: Dict) -> str:
        """Step 1 prompt: ask the AI to reason through the wound in free text."""
        m = wound_data.get('measurements', {})
        c = wound_data.get('color_analysis', {})
        cper = c.get('color_percentages', {})

        length = m.get('length_cm', 0)
        width  = m.get('width_cm', 0)
        area   = m.get('area_cm2', 0)
        color_desc   = c.get('color_description', 'unknown')
        darkness_pct = c.get('darkness_level', 0) * 100
        yellow    = cper.get('yellow', 0)
        green     = cper.get('green', 0)
        red_pct   = cper.get('red', 0)
        pink_pct  = cper.get('pink', 0)
        brown_pct = cper.get('brown', 0)
        black_pct = cper.get('black', 0)

        return f"""You are an experienced wound care clinician. Analyze the wound data below and provide a comprehensive, structured wound assessment for the patient. Use your best clinical judgment based on the image and numeric data.

CRITICAL STITCH ASSESSMENT GUIDELINES:
- Lacerations > 0.8 cm with high red percentage (>50%) indicating fresh injury SHOULD recommend professional evaluation for closure
- Consider depth indicators (dark colors, visible tissue layers) even in smaller wounds
- Fresh lacerations with gaping edges often benefit from closure within 6-12 hours
- Do NOT dismiss closure needs based solely on small size - consider wound characteristics

COLOR ANALYSIS (pixel percentages):
Color description: {color_desc}
Red tissue: {red_pct:.1f}%
Pink tissue: {pink_pct:.1f}%
Yellow tissue: {yellow:.1f}%
Green tissue: {green:.1f}%
Brown/eschar: {brown_pct:.1f}%
Black tissue: {black_pct:.1f}%
Darkness level: {darkness_pct:.1f}%

SIZE MEASUREMENTS (estimate):
Length: {length:.2f} cm  |  Width: {width:.2f} cm  |  Area: {area:.2f} cm²

Please provide a detailed clinical assessment, including:
- Wound stage and what it means for the patient
- Infection risk and what factors contribute
- Severity and what makes it so
- Whether closure (stitches, staples, etc.) is needed, and why - BE SPECIFIC about wound characteristics that indicate need for closure
- Healing time prediction and what affects it
- Scar risk and how to reduce it
- Step-by-step immediate and daily care
- Medications or products that may help
- Warning signs to watch for
- A clinical summary in plain English

All information should be specific to this wound and image. For stitch assessment, consider the wound's fresh appearance, depth, gaping potential, and location - not just size."""

    def _build_json_from_analysis_prompt(self, clinical_analysis: str, wound_data: Dict) -> str:
        """
        Step 2 prompt: convert the analysis into structured JSON.
        """
        m = wound_data.get('measurements', {})
        c = wound_data.get('color_analysis', {})
        
        return f"""Based on this description: "{clinical_analysis}"

And these measurements:
- Size: {m.get('length_cm', 0):.1f} x {m.get('width_cm', 0):.1f} cm, Area: {m.get('area_cm2', 0):.2f} cm²
- Color: {c.get('color_description', 'unknown')}

Provide a JSON response with this structure:
{{
  "healing_stage": "inflammatory|proliferative|remodeling",
  "healing_progress": "normal|delayed|accelerated",
  "severity": "mild|moderate|severe",
  "healing_indicators": "single paragraph describing positive signs",
  "concerns": "single paragraph describing concerns",
  "infection_risk": {{"level": "low|moderate|high", "score": 0-100, "reasoning": "brief explanation"}},
  "healing_time_prediction": {{"predicted_days_min": 7, "predicted_days_max": 14, "confidence": "low|medium|high", "notes": "brief note"}},
  "stitches": {{"need_stitches": false, "recommendation": "conversational advice explaining why"}},
  "scar_risk": {{"risk": "low|moderate|high", "score": 0-100, "tips": "single paragraph with scar prevention tips"}},
  "recommendations": {{
    "immediate_care": "single paragraph with immediate care steps in conversational sentences",
    "ongoing_care": "single paragraph with daily care protocol in conversational sentences",
    "medications": {{
      "healing_aids": "single sentence listing healing aids",
      "pain_management": "single sentence listing pain management options",
      "cautions": "single sentence with cautions"
    }},
    "warning_signs": "single paragraph listing warning signs to watch for",
    "follow_up": "when to seek care"
  }},
  "overall_assessment": "2-3 sentence summary"
}}

IMPORTANT: Use conversational paragraphs and sentences, NOT bullet point arrays. Keep text brief and use plain language."""

    def _parse_ai_response(self, ai_text: str, wound_data: Dict) -> Dict:
        """Parse the AI JSON response into a structured dict."""
        try:
            # Try to parse as JSON
            parsed = json.loads(ai_text)
            print(f"[AI Feedback] Successfully parsed JSON response with {len(parsed)} fields")
            return parsed
        except json.JSONDecodeError as e:
            print(f"[AI Feedback] JSON parsing failed: {e}")
            print(f"[AI Feedback] Raw AI response (first 500 chars): {ai_text[:500]}")
            # If JSON parsing fails, try to extract JSON from the text
            json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    print(f"[AI Feedback] Extracted and parsed JSON with {len(parsed)} fields")
                    return parsed
                except json.JSONDecodeError:
                    print(f"[AI Feedback] Failed to parse extracted JSON")
                    pass
            
            print(f"[AI Feedback] Using fallback structure due to parsing failure")
            # Fallback: return a basic structure
            return {
                "healing_stage": "inflammatory",
                "healing_progress": "normal",
                "severity": "moderate",
                "concerns": [],
                "healing_indicators": [],
                "overall_assessment": ai_text[:500] if ai_text else "Unable to parse AI response",
                "infection_risk": {"level": "unknown", "score": 0},
                "healing_time_prediction": {
                    "predicted_days_min": 7,
                    "predicted_days_max": 14,
                    "confidence": "low",
                    "notes": "Estimate based on typical wound healing"
                },
                "stitches": {"need_stitches": False, "recommendation": "Monitor wound"},
                "scar_risk": {"risk": "moderate", "score": 50, "tips": []},
                "recommendations": {
                    "immediate_care": ["Clean wound gently", "Apply clean dressing"],
                    "ongoing_care": ["Change dressing daily", "Monitor for signs of infection"],
                    "medications": {
                        "healing_aids": [],
                        "pain_management": [],
                        "cautions": []
                    },
                    "warning_signs": ["Increasing redness", "Pus or discharge", "Fever"],
                    "follow_up": "Monitor for 3-5 days"
                },
                "assessment_method": "AI-powered (Gemini)"
            }
    
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

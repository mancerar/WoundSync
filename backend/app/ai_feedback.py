"""
AI-powered clinical feedback module for wound analysis.

Primary provider:
- Qwen2.5-VL-72B-Instruct via OpenAI-compatible API endpoint

Fallback provider:
- Local Ollama models

Falls back to rule-based heuristics if AI is unavailable.
"""

import base64
import importlib
import json
import mimetypes
import os
import re
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


def check_ollama_available() -> bool:
    """Check if Ollama is installed and available."""
    try:
        ollama = importlib.import_module("ollama")
        # Try to ping Ollama to see if it's running
        ollama.list()
        return True
    except Exception:
        return False


def get_available_models() -> List[str]:
    """Get list of available Ollama models."""
    try:
        ollama = importlib.import_module("ollama")
        response = ollama.list()
        models = []
        # Handle both old (dict) and new (object) SDK formats
        model_list = response.models if hasattr(response, 'models') else response.get('models', [])
        for m in model_list:
            # New SDK: model objects with .model or .name attribute
            if hasattr(m, 'model'):
                models.append(m.model)
            elif hasattr(m, 'name'):
                models.append(m.name)
            elif isinstance(m, dict):
                models.append(m.get('name') or m.get('model', ''))
        return [m for m in models if m]
    except Exception:
        return []


def select_best_medical_model() -> Optional[str]:
    """Select the best available medical model from Ollama."""
    available = get_available_models()
    
    # Priority order: instruction-following models first (meditron is good at
    # medical text but CANNOT follow JSON/structured output instructions)
    priority_order = [
        'llama3.2:3b',
        'llama3.2:1b',
        'llama3.1:8b',
        'llama3.1:latest',
        'llama3:latest',
        'mistral:7b',
        'biomistral:7b',
        'meditron:7b',   # last resort — poor instruction following
        'meditron:13b',
        'llama2:7b',
    ]
    
    for model in priority_order:
        # Check exact match or partial match (e.g., "meditron:7b-q4" matches "meditron:7b")
        for available_model in available:
            if model in available_model:
                return available_model
    
    # Return first available model as fallback
    return available[0] if available else None


class AIFeedbackGenerator:
    """Generate clinical feedback using Qwen-VL or Ollama with safety overrides."""
    
    def __init__(self, use_ai: bool = True, model_name: Optional[str] = None):
        """
        Initialize AI feedback generator.
        
        Args:
            use_ai: Whether to attempt AI-powered feedback (falls back to rules if unavailable)
            model_name: Specific model to use (auto-selects if None)
        """
        self.provider = "none"
        self.qwen_api_key = os.getenv("QWEN_VL_API_KEY", "").strip()
        self.qwen_base_url = os.getenv("QWEN_VL_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.qwen_site_url = os.getenv("QWEN_VL_SITE_URL", "").strip()
        self.qwen_site_name = os.getenv("QWEN_VL_SITE_NAME", "WoundSync").strip()

        qwen_model_from_env = os.getenv("QWEN_VL_MODEL", "").strip()
        default_qwen_model = qwen_model_from_env or "Qwen2.5-VL-72B-Instruct"

        self.use_ai = bool(use_ai)
        self.model_name = model_name

        # Provider priority: Qwen-VL API first, then Ollama, then rule-based fallback.
        if self.use_ai and self.qwen_api_key:
            self.provider = "qwen_vl_api"
            if not self.model_name:
                self.model_name = default_qwen_model
            print(f"[AI Feedback] Using Qwen-VL API model: {self.model_name}")
            return

        if self.use_ai and check_ollama_available():
            self.provider = "ollama"
            if not self.model_name:
                self.model_name = select_best_medical_model()

            if not self.model_name:
                warnings.warn("No Ollama models found. Install with: ollama pull llama3.2:3b")
                self.use_ai = False
                self.provider = "none"
            else:
                print(f"[AI Feedback] Using Ollama model: {self.model_name}")
            return

        self.use_ai = False
        self.provider = "none"
        print("[AI Feedback] AI provider unavailable - using rule-based fallback")
    
    def generate_full_assessment(self, wound_data: Dict) -> Optional[Dict]:
        """
        Generate a complete wound assessment using AI.

        Returns a dict matching all fields the frontend expects, or None if AI
        is unavailable/fails (caller should then use rule-based fallback).

        Returned structure:
          healing_stage, healing_progress, severity, concerns, healing_indicators,
          overall_assessment, infection_risk, healing_time_prediction, stitches,
          scar_risk, recommendations (immediate_care, ongoing_care, medications,
          warning_signs, follow_up), assessment_method
        """
        if not self.use_ai:
            return None
        try:
            return self._get_ai_assessment(wound_data)
        except Exception as e:
            warnings.warn(f"AI assessment failed: {e}")
            return None

    # Keep old method name as alias for any existing callers
    def generate_clinical_assessment(self, wound_data: Dict) -> Dict:
        result = self.generate_full_assessment(wound_data)
        if result:
            return {
                'assessment_method': result.get('assessment_method', 'AI-powered'),
                'clinical_feedback': result,
                'safety_overrides': self._apply_safety_overrides(wound_data),
                'disclaimer': MEDICAL_DISCLAIMER,
                'ai_available': True
            }
        return {
            'assessment_method': 'Rule-based heuristics',
            'clinical_feedback': self._get_rule_based_assessment(wound_data),
            'safety_overrides': self._apply_safety_overrides(wound_data),
            'disclaimer': MEDICAL_DISCLAIMER,
            'ai_available': False
        }
    
    def _get_ai_assessment(self, wound_data: Dict) -> Dict:
        if self.provider == "qwen_vl_api":
            return self._get_qwen_vl_assessment(wound_data)
        return self._get_ollama_assessment(wound_data)

    def _get_ollama_assessment(self, wound_data: Dict) -> Dict:
        """
        Two-step chain-of-thought assessment:
          Step 1 — Free-text clinical analysis: AI reasons through the wound
                   without any output format constraints.
          Step 2 — Structured output: AI converts its own analysis into JSON.

        This is significantly more accurate than asking for JSON directly because
        the model reasons first, then codifies — rather than generating reasoning
        and classification tokens simultaneously.
        """
        ollama = importlib.import_module("ollama")

        def _chat(messages, use_json_format=False, max_tokens=600):
            kwargs = dict(
                model=self.model_name,
                messages=messages,
                options={'temperature': 0.3, 'top_p': 0.9, 'num_predict': max_tokens}
            )
            if use_json_format:
                kwargs['format'] = 'json'
            resp = ollama.chat(**kwargs)
            if hasattr(resp, 'message'):
                return resp.message.content
            return resp['message']['content']

        # ── STEP 1: Clinical reasoning (free text) ───────────────────────────
        analysis_prompt = self._build_analysis_prompt(wound_data)
        print(f"[AI Feedback] Step 1: Analyzing wound...")
        clinical_analysis = _chat([{'role': 'user', 'content': analysis_prompt}], max_tokens=500)
        print(f"[AI Feedback] Step 2: Generating structured output...")

        # ── STEP 2: Convert the analysis into structured JSON ─────────────────
        json_prompt = self._build_json_from_analysis_prompt(clinical_analysis, wound_data)
        ai_text = _chat(
            [{'role': 'user', 'content': json_prompt}],
            use_json_format=True,
            max_tokens=800
        )

        result = self._parse_ai_response(ai_text, wound_data)
        result['ai_reasoning'] = clinical_analysis
        # Post-process: correct obvious AI errors using raw color data
        result = self._post_process_result(result, wound_data)
        return result

    def _get_qwen_vl_assessment(self, wound_data: Dict) -> Dict:
        """Get image-grounded assessment using Qwen2.5-VL via OpenAI-compatible API."""
        image_path = wound_data.get('image_path')
        if not image_path:
            raise ValueError("Qwen-VL requires image_path in wound_data")

        image_data_url = self._encode_image_to_data_url(image_path)

        # Step 1: vision-grounded clinical reasoning
        analysis_prompt = self._build_vision_analysis_prompt(wound_data)
        print("[AI Feedback] Qwen Step 1: image-grounded wound analysis...")
        clinical_analysis = self._qwen_chat(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            max_tokens=1000,
            response_json=False,
        )

        # Step 2: convert to strict JSON
        print("[AI Feedback] Qwen Step 2: structured JSON output...")
        json_prompt = self._build_json_from_analysis_prompt(clinical_analysis, wound_data)
        ai_text = self._qwen_chat(
            messages=[{"role": "user", "content": json_prompt}],
            max_tokens=1200,
            response_json=True,
        )

        result = self._parse_ai_response(ai_text, wound_data)
        result['ai_reasoning'] = clinical_analysis
        result = self._post_process_result(result, wound_data)
        return result

    def _build_vision_analysis_prompt(self, wound_data: Dict) -> str:
        """Build a vision-aware clinical prompt for Qwen-VL."""
        base_prompt = self._build_analysis_prompt(wound_data)
        return (
            "You are analyzing a real wound photograph. Use the image as primary evidence and "
            "the numeric measurements below as supporting evidence. If the image conflicts with "
            "the numeric summary, explain the conflict and prioritize what is visually clear in the image.\n\n"
            + base_prompt
        )

    def _encode_image_to_data_url(self, image_path: str) -> str:
        """Encode local image file as a data URL for multimodal API calls."""
        p = Path(image_path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Image not found for Qwen-VL analysis: {image_path}")

        mime_type, _ = mimetypes.guess_type(str(p))
        mime = mime_type or "image/jpeg"
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _qwen_chat(self, messages: List[Dict], max_tokens: int = 1000, response_json: bool = False) -> str:
        """Call Qwen-VL through an OpenAI-compatible chat/completions endpoint."""
        if not self.qwen_api_key:
            raise RuntimeError("Missing QWEN_VL_API_KEY")

        url = f"{self.qwen_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.qwen_api_key}",
            "Content-Type": "application/json",
        }
        if self.qwen_site_url:
            headers["HTTP-Referer"] = self.qwen_site_url
        if self.qwen_site_name:
            headers["X-Title"] = self.qwen_site_name

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": max_tokens,
        }
        if response_json:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Qwen API error {resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Qwen API returned no choices")

        msg = choices[0].get("message", {})
        content = msg.get("content", "")

        if isinstance(content, list):
            text_chunks = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_chunks.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_chunks.append(part)
            content = "\n".join(c for c in text_chunks if c)

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Qwen API returned empty content")
        return content

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

        # Pre-interpret the color data so the AI gets clear signals
        color_signals = []
        if red_pct > 40:
            color_signals.append(f"HIGH red tissue ({red_pct:.0f}%) — active granulation or bleeding present")
        elif red_pct > 15:
            color_signals.append(f"MODERATE red tissue ({red_pct:.0f}%) — some granulation activity")
        if pink_pct > 40:
            color_signals.append(f"HIGH pink tissue ({pink_pct:.0f}%) — healthy epithelialization occurring")
        elif pink_pct > 15:
            color_signals.append(f"MODERATE pink tissue ({pink_pct:.0f}%) — some healthy healing signs")
        if yellow > 20:
            color_signals.append(f"HIGH yellow/slough ({yellow:.0f}%) — moderate-to-high infection/slough risk")
        elif yellow > 8:
            color_signals.append(f"SOME yellow ({yellow:.0f}%) — possible fibrin slough, watch for infection")
        if green > 5:
            color_signals.append(f"GREEN tissue ({green:.0f}%) — strong indicator of bacterial colonisation, HIGH infection risk")
        elif green > 1:
            color_signals.append(f"TRACE green ({green:.0f}%) — possible early bacterial contamination")
        if brown_pct > 50:
            color_signals.append(f"DOMINANT brown/eschar ({brown_pct:.0f}%) — significant necrotic/dried tissue, wound is serious")
        elif brown_pct > 25:
            color_signals.append(f"HIGH brown ({brown_pct:.0f}%) — notable eschar/dried blood present")
        if black_pct > 10:
            color_signals.append(f"BLACK tissue ({black_pct:.0f}%) — necrotic (dead) tissue present, serious wound")
        if not color_signals:
            color_signals.append("Mixed color pattern — no single dominant tissue type")

        signals_text = "\n  ".join(f"→ {s}" for s in color_signals)

        # Size caveats
        size_notes = "Measurements are ESTIMATES — no physical reference object was in the image."
        if width < 0.3:
            size_notes += " Width under 0.3 cm is likely a calibration artifact; treat width as unreliable."
        if area > 20 or length > 10:
            size_notes += " Size appears unusually large — likely due to calibration error. Weight color data more heavily."

        return f"""You are an experienced wound care clinician. Analyze the wound data below and write a detailed clinical assessment.

COLOR ANALYSIS ─ USE PIXEL PERCENTAGES AS GROUND TRUTH:
⚠ IMPORTANT: The "color_description" label below is generated from a separate HSV hue analysis
and may NOT match the actual pixel percentages. For example, it may say "yellow/infected" even
if yellow% is 0. ALWAYS base your reasoning on the actual percentage numbers, not the label.
NEVER mention a color in your analysis unless its pixel percentage is ≥ 5%.

Color description (HSV-derived label, may be misleading): {color_desc}
Actual pixel measurements:
Red tissue pixels  : {red_pct:.1f}%   ← granulation tissue / active bleeding
Pink tissue pixels : {pink_pct:.1f}%  ← healthy new skin growing (epithelialization)
Yellow pixels      : {yellow:.1f}%   ← fibrin slough / possible infection material
Green pixels       : {green:.1f}%   ← bacterial contamination / infection sign
Brown/eschar pixels: {brown_pct:.1f}%  ← dried blood / dead (necrotic) tissue
Black pixels       : {black_pct:.1f}%  ← necrotic (dead) tissue
Darkness level     : {darkness_pct:.1f}%

PRE-INTERPRETED SIGNALS:
  {signals_text}

━━━ SIZE MEASUREMENTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Length: {length:.2f} cm  |  Width: {width:.2f} cm  |  Area: {area:.2f} cm²
{size_notes}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEVERITY CALIBRATION RULES (follow these strictly):
  • Brown/eschar > 50% OR black > 10%  → severity is at minimum MODERATE, likely SEVERE
  • Yellow > 20% OR green > 5%         → infection risk is at minimum MODERATE
  • Green > 5%                          → infection risk is HIGH or CRITICAL
  • Red > 40% with low yellow/green    → active wound, needs proper care
  • Healing time — minimum floors:
      - Necrotic (brown>50% or black>10%): at least 14-28 days
      - Infected (yellow>20% or green>5%): at least 10-21 days
      - Active red wound (red>40%):        at least 7-14 days
      - Healing pink wound:                3-10 days

LANGUAGE RULES:
  - Write in plain English the patient can understand.
  - Always explain clinical terms (e.g. "eschar (dead dry tissue)", "epithelialization (new skin growing)").
  - Write directly to the patient.

POSITIVE SIGNS RULE (CRITICAL):
  - Only list things that ARE PRESENT and good (e.g. "Pink tissue indicates new skin is growing")
  - NEVER list "X is not present" or "No X" as a positive sign — absence of something bad is NOT a positive sign
  - If there are no genuine positive signs, say "No positive healing signs currently observed"

Now think through each point:

1. WOUND STAGE — Based on the color signals above, what stage? What does this mean for the patient?
2. INFECTION RISK — Score 0-100. Which exact color signals drive this? Be specific.
3. SEVERITY — mild / moderate / severe. Apply the calibration rules above.
4. CLOSURE — Does this wound need stitches, staples, or steri-strips? Give clear patient instructions.
   IMPORTANT: A wound being infected or necrotic does NOT automatically mean "no stitches" — these are separate questions.
   - Infected/necrotic wounds STILL need medical evaluation for closure (delayed primary closure, debridement, or drainage).
   - If the wound looks deep, gaping (edges separated), or severe — ALWAYS recommend the patient go to an ER or urgent care.
   - ABRASIONS/AVULSIONS (surface wounds): if pink tissue dominates (>30%), this is a surface wound that does NOT need stitches — it needs moist wound care only.
   - Only say "no stitches needed" if the wound is genuinely shallow, a surface abrasion, or the edges are naturally touching.
5. HEALING TIME — Using the minimum floor rules above, what is realistic? What affects this?
6. SCAR RISK — low / moderate / high. What specific steps can reduce scarring?
7. TREATMENT — Step-by-step immediate care. Daily wound care routine in simple language. What products? What warning signs?
8. CLINICAL SUMMARY — 2-3 sentences, plain English, appropriate for a patient.

Base everything on THIS wound's specific data. No generic answers."""

    def _build_json_from_analysis_prompt(self, clinical_analysis: str, wound_data: Dict) -> str:
        """Step 2 prompt: convert the clinical analysis into structured JSON."""
        return f"""You performed the following clinical analysis of a wound:

{clinical_analysis}

Now convert your analysis above into this exact JSON structure. Every value must come directly from your analysis above.

CRITICAL RULES:
1. Plain English only — never bare jargon. Always explain clinical terms inline.
   ✓ "Gently rinse the wound with clean water or saline (salt water), pat dry, apply a thin layer of antibiotic ointment (like Polysporin or Neosporin), and cover with a clean bandage"
   ✗ "Wound irrigation and dressing application"
2. healing_indicators: ONLY include things that ARE PRESENT and POSITIVE (e.g. pink tissue growing, controlled inflammation, no pus seen). NEVER write "X is not present" — absence is not a positive sign.
3. concerns: list actual problems observed, not absences.
4. Healing time: respect the minimum floor rules you applied in your analysis — do not under-estimate.
5. Severity: use mild only for genuinely minor wounds; use moderate or severe if necrotic or infected tissue was identified.

{{
  "healing_stage": "<inflammatory|proliferative|remodeling|chronic>",
  "healing_progress": "<normal|good|delayed|impaired|infected|compromised>",
  "severity": "<mild|moderate|severe>",
  "concerns": ["<concern drawn from your analysis>"],
  "healing_indicators": ["<positive sign you identified, or empty array>"],
  "overall_assessment": "<your clinical summary paragraph from point 8>",
  "infection_risk": {{
    "level": "<low|moderate|high|critical>",
    "score": <0-100 integer from your infection scoring>,
    "factors": ["<specific factor you identified>"]
  }},
  "healing_time_prediction": {{
    "predicted_days_min": <integer>,
    "predicted_days_max": <integer>,
    "confidence": "<low|medium|high>",
    "notes": "<healing factors you identified>"
  }},
  "stitches": {{
    "need_stitches": <true|false>,
    "recommendation": "<your specific closure recommendation>",
    "reasons": ["<reason from your analysis>"]
  }},
  "scar_risk": {{
    "risk": "<low|moderate|high>",
    "score": <0-100 integer>,
    "tips": ["<scar tip 1 from your analysis>", "<tip 2>", "<tip 3>"]
  }},
  "recommendations": {{
    "immediate_care": ["<step 1 from your treatment plan>", "<step 2>", "<step 3>", "<step 4>"],
    "ongoing_care": ["<daily care step 1>", "<step 2>", "<step 3>"],
    "medications": {{
      "healing_aids": ["<product you recommended>", "<product 2>"],
      "pain_management": ["<pain option if applicable>"],
      "cautions": ["<caution specific to this wound>"]
    }},
    "warning_signs": ["<warning sign 1>", "<sign 2>", "<sign 3>", "<sign 4>"],
    "follow_up": "<your specific follow-up recommendation>"
  }}
}}"""
    
    def _build_clinical_prompt(self, wound_data: Dict) -> str:
        """Build a JSON-requesting prompt covering all frontend display fields."""
        m = wound_data.get('measurements', {})
        c = wound_data.get('color_analysis', {})
        cper = c.get('color_percentages', {})

        length = m.get('length_cm', 0)
        width  = m.get('width_cm', 0)
        area   = m.get('area_cm2', 0)
        color_desc  = c.get('color_description', 'unknown')
        redness_pct = c.get('redness_level', 0) * 100
        darkness_pct = c.get('darkness_level', 0) * 100
        yellow = cper.get('yellow', 0)
        green  = cper.get('green', 0)
        red_pct   = cper.get('red', 0)
        pink_pct  = cper.get('pink', 0)
        brown_pct = cper.get('brown', 0)

        # Flag if measurements look unrealistically large (camera calibration often wrong)
        measurements_note = ""
        if area > 20 or length > 10 or width > 8:
            measurements_note = (
                "NOTE: The pixel-to-cm calibration may be inaccurate (no physical reference "
                "scale in image). Treat size measurements as rough estimates only. "
                "Base severity, closure, and healing time primarily on COLOR analysis below."
            )
        elif area > 6 or length > 5:
            measurements_note = "Note: Wound appears large. Confirm measurements with a physical reference if possible."

        return f"""You are a wound care clinician. Analyze the following wound data and fill in the JSON below.

COLOR ANALYSIS (most reliable — based on pixel analysis):
- Wound color: {color_desc}
- Red tissue: {red_pct:.1f}%  (granulation/blood)
- Pink tissue: {pink_pct:.1f}%  (healthy healing)
- Yellow/slough: {yellow:.1f}%  (possible infection/necrosis)
- Green: {green:.1f}%  (bacterial infection indicator)
- Brown/eschar: {brown_pct:.1f}%  (dried blood/eschar)
- Redness level: {redness_pct:.1f}%
- Darkness: {darkness_pct:.1f}%

SIZE MEASUREMENTS (may be inaccurate, use as secondary reference only):
- Length: {length:.2f} cm, Width: {width:.2f} cm, Area: {area:.2f} cm²
{measurements_note}

CLINICAL ASSESSMENT RULES:
- Green tissue > 0% always means HIGH infection risk
- Yellow/slough > 20% means MODERATE-HIGH infection risk
- Pink > 30% with low yellow/green = healthy healing signs
- High darkness (necrotic tissue) = SEVERE staging
- Do NOT copy the placeholder values — replace ALL placeholders with your actual clinical assessment
- Every string in arrays must be specific to this wound, not generic text

Fill this JSON with your clinical assessment (replace every placeholder value):
{{
  "healing_stage": "<inflammatory|proliferative|remodeling|chronic>",
  "healing_progress": "<normal|good|delayed|impaired|infected|compromised>",
  "severity": "<mild|moderate|severe>",
  "concerns": ["<specific concern based on color data above>"],
  "healing_indicators": ["<positive signs seen, or empty array if none>"],
  "overall_assessment": "<2-3 sentence clinical summary specific to this wound's color and appearance>",
  "infection_risk": {{
    "level": "<low|moderate|high|critical>",
    "score": <0-100 integer>,
    "factors": ["<specific risk factors seen in this wound>"]
  }},
  "healing_time_prediction": {{
    "predicted_days_min": <integer>,
    "predicted_days_max": <integer>,
    "confidence": "<low|medium|high>",
    "notes": "<patient-specific factors affecting healing>"
  }},
  "stitches": {{
    "need_stitches": <true|false>,
    "recommendation": "<specific closure advice for this wound>",
    "reasons": ["<reason based on wound characteristics>"]
  }},
  "scar_risk": {{
    "risk": "<low|moderate|high>",
    "score": <0-100 integer>,
    "tips": [
      "<specific scar prevention tip 1>",
      "<specific scar prevention tip 2>",
      "<specific scar prevention tip 3>"
    ]
  }},
  "recommendations": {{
    "immediate_care": [
      "<immediate action tailored to this wound type>",
      "<immediate action 2>",
      "<immediate action 3>"
    ],
    "ongoing_care": [
      "<daily care step specific to this wound>",
      "<daily care step 2>",
      "<daily care step 3>"
    ],
    "medications": {{
      "healing_aids": ["<specific product suited to this wound>", "<product 2>"],
      "pain_management": ["<pain option if needed>"],
      "cautions": ["<specific caution for this wound type>"]
    }},
    "warning_signs": [
      "<warning sign most relevant to this wound's risk profile>",
      "<warning sign 2>",
      "<warning sign 3>",
      "<warning sign 4>"
    ],
    "follow_up": "<specific follow-up recommendation based on severity>"
  }}
}}"""
    
    def _parse_ai_response(self, ai_text: str, wound_data: Dict) -> Dict:
        """Parse AI JSON response into the full structured assessment dict."""
        # Strip markdown fences if present
        text = ai_text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        text = text.strip()

        # Try direct JSON parse first
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract the outermost {...} block
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if data is None:
            raise ValueError(f"Could not parse AI response as JSON. Response: {ai_text[:300]}")

        # Ensure all required keys exist with safe defaults
        data.setdefault('healing_stage', 'inflammatory')
        data.setdefault('healing_progress', 'normal')
        data.setdefault('severity', 'mild')
        data.setdefault('concerns', [])
        data.setdefault('healing_indicators', [])
        data.setdefault('overall_assessment', 'Wound analysis complete. Monitor for changes and consult a healthcare provider if concerned.')

        ir = data.setdefault('infection_risk', {})
        ir.setdefault('level', 'low')
        ir.setdefault('score', 10)
        ir.setdefault('factors', [])

        htp = data.setdefault('healing_time_prediction', {})
        htp.setdefault('predicted_days_min', 3)
        htp.setdefault('predicted_days_max', 14)
        htp.setdefault('confidence', 'medium')
        htp.setdefault('notes', 'Estimate only; varies with age, comorbidities, and wound care adherence.')

        st = data.setdefault('stitches', {})
        st.setdefault('need_stitches', False)
        st.setdefault('recommendation', 'Monitor wound for natural healing.')
        st.setdefault('reasons', [])

        sr = data.setdefault('scar_risk', {})
        sr.setdefault('risk', 'low')
        sr.setdefault('score', 20)
        sr.setdefault('tips', [
            'Keep wound moist with petroleum jelly and non-adherent dressing',
            'Avoid tension across the wound',
            'Sun protection SPF 30+ for 3-6 months'
        ])

        rec = data.setdefault('recommendations', {})
        rec.setdefault('immediate_care', ['Clean wound gently with sterile saline', 'Apply sterile dressing'])
        rec.setdefault('ongoing_care', ['Change dressing daily', 'Monitor for infection signs'])
        meds = rec.setdefault('medications', {})
        meds.setdefault('healing_aids', ['Sterile saline', 'Petroleum jelly', 'Non-adherent dressing'])
        meds.setdefault('pain_management', ['Acetaminophen for pain as directed'])
        meds.setdefault('cautions', ['Avoid hydrogen peroxide unless directed'])
        rec.setdefault('warning_signs', [
            'Increasing redness, warmth, or swelling',
            'Pus or unusual discharge',
            'Fever or feeling unwell'
        ])
        rec.setdefault('follow_up', 'Consult healthcare provider if no improvement within 48-72 hours.')

        # Normalize: AI sometimes returns strings instead of arrays for list fields.
        # Coerce any string value to a single-element list so .map() works in the frontend.
        def _ensure_list(val, fallback):
            if isinstance(val, list):
                return val
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            return fallback

        rec['immediate_care'] = _ensure_list(
            rec.get('immediate_care'),
            ['Clean wound gently with sterile saline', 'Apply sterile dressing']
        )
        rec['ongoing_care'] = _ensure_list(
            rec.get('ongoing_care'),
            ['Change dressing daily', 'Monitor for infection signs']
        )
        rec['warning_signs'] = _ensure_list(
            rec.get('warning_signs'),
            ['Increasing redness, warmth, or swelling', 'Pus or unusual discharge', 'Fever or feeling unwell']
        )
        meds['healing_aids'] = _ensure_list(
            meds.get('healing_aids'),
            ['Sterile saline', 'Petroleum jelly', 'Non-adherent dressing']
        )
        meds['pain_management'] = _ensure_list(
            meds.get('pain_management'),
            ['Acetaminophen for pain as directed']
        )
        meds['cautions'] = _ensure_list(
            meds.get('cautions'),
            ['Avoid hydrogen peroxide unless directed']
        )

        # Normalize top-level list fields
        data['concerns'] = _ensure_list(data.get('concerns'), [])
        data['healing_indicators'] = _ensure_list(data.get('healing_indicators'), [])

        # Also normalize nested list fields
        ir = data.get('infection_risk', {})
        if isinstance(ir, dict):
            ir['factors'] = _ensure_list(ir.get('factors'), [])

        st = data.get('stitches', {})
        if isinstance(st, dict):
            st['reasons'] = _ensure_list(st.get('reasons'), [])

        sr = data.get('scar_risk', {})
        if isinstance(sr, dict):
            sr['tips'] = _ensure_list(
                sr.get('tips'),
                ['Keep wound moist with petroleum jelly', 'Avoid tension across wound', 'Sun protection SPF 30+']
            )

        data['assessment_method'] = f'AI-powered ({self.model_name})'
        return data
    
    def _post_process_result(self, result: Dict, wound_data: Dict) -> Dict:
        """Correct obvious AI errors using raw color data as ground truth."""
        c = wound_data.get('color_analysis', {})
        cper = c.get('color_percentages', {})
        red_pct   = cper.get('red', 0)
        pink_pct  = cper.get('pink', 0)
        yellow    = cper.get('yellow', 0)
        green     = cper.get('green', 0)
        brown_pct = cper.get('brown', 0)
        black_pct = cper.get('black', 0)

        necrotic   = brown_pct > 30 or black_pct > 10
        infected   = yellow > 20 or green > 5
        active_red = red_pct > 40

        # ── 1. Strip false/hallucinated positive signs ──────────────────────
        indicators = result.get('healing_indicators', [])
        bad_phrases = ['not present', 'no red', 'no pink', 'no yellow', 'no green',
                       'no pus', 'absent', 'no sign', 'no active', 'no bleeding']
        # Also remove mentions of colors that are near-zero in the actual data
        def _color_not_present(s):
            s_lo = s.lower()
            if 'pink' in s_lo and pink_pct < 5:   return True
            if 'green' in s_lo and green < 5:      return True
            if 'yellow' in s_lo and yellow < 5:    return True
            if 'red' in s_lo and red_pct < 5:      return True
            return False
        indicators = [
            s for s in indicators
            if not any(bp in s.lower() for bp in bad_phrases)
            and not _color_not_present(s)
        ]

        # Add factually correct positive indicators based on raw data
        if pink_pct > 20 and not any('pink' in s.lower() for s in indicators):
            indicators.append(
                f'Pink tissue ({pink_pct:.0f}%) — new skin cells are actively growing'
            )
        if red_pct > 15 and not necrotic and not any('granulat' in s.lower() or 'red' in s.lower() for s in indicators):
            indicators.append(
                f'Red tissue ({red_pct:.0f}%) — active granulation (healing tissue building up)'
            )
        result['healing_indicators'] = indicators if indicators else []

        # ── 2. Strip hallucinated concerns about colors not present ─────────
        concerns = result.get('concerns', [])
        concerns = [
            s for s in concerns
            if not _color_not_present(s)
        ]
        result['concerns'] = concerns

        # ── 3. Enforce severity floors ──────────────────────────────────────
        severity = result.get('severity', 'mild').lower()
        if necrotic:
            # Heavy necrosis (>50% brown or >10% black) → SEVERE minimum
            if brown_pct > 50 or black_pct > 10:
                result['severity'] = 'severe'
                severity = 'severe'
            elif severity == 'mild':
                result['severity'] = 'moderate'
                severity = 'moderate'
        if infected and green > 5 and severity in ('mild', 'moderate'):
            result['severity'] = 'moderate'
            severity = 'moderate'

        # ── 4. Enforce infection risk floors ───────────────────────────────
        ir = result.get('infection_risk', {})
        if isinstance(ir, dict):
            level = ir.get('level', 'low').lower()
            if green > 5 and level in ('low',):
                ir['level'] = 'moderate'
            if infected and level == 'low':
                ir['level'] = 'moderate'
            if green > 10 and level in ('low', 'moderate'):
                ir['level'] = 'high'
            score = ir.get('score', 0)
            if infected and score < 40:
                ir['score'] = max(score, 45)
            if necrotic and score < 30:
                ir['score'] = max(score, 30)

        # ── 5. Enforce healing time minimums ──────────────────────────────
        htp = result.get('healing_time_prediction', {})
        if isinstance(htp, dict):
            mn = htp.get('predicted_days_min', 0)
            mx = htp.get('predicted_days_max', 0)
            if necrotic:
                if mn < 14: htp['predicted_days_min'] = 14
                if mx < 21: htp['predicted_days_max'] = 21
            elif infected:
                if mn < 10: htp['predicted_days_min'] = 10
                if mx < 18: htp['predicted_days_max'] = 18
            elif active_red:
                if mn < 7:  htp['predicted_days_min'] = 7
                if mx < 14: htp['predicted_days_max'] = 14

        # ── 6. Add necrotic/infection concerns if still missing ──────────────
        concerns = result.get('concerns', [])
        if necrotic and not any('necrotic' in s.lower() or 'eschar' in s.lower() or 'dead' in s.lower() for s in concerns):
            concerns.insert(0, f'Necrotic (dead/dark) tissue present ({brown_pct:.0f}% brown, {black_pct:.0f}% black) — this slows healing and increases infection risk')
        if infected and not any('infect' in s.lower() or 'yellow' in s.lower() or 'green' in s.lower() for s in concerns):
            concerns.insert(0, f'Signs of potential infection: yellow ({yellow:.0f}%) or green ({green:.0f}%) tissue present')
        result['concerns'] = concerns

        # ── 7. Fix stitches logic ────────────────────────────────────────────
        st = result.get('stitches', {})
        if isinstance(st, dict):
            severity = result.get('severity', 'mild').lower()
            # Priority 1: pink > 30% dominant → ABRASION/SURFACE WOUND — no stitches needed.
            # Pink dominance overrides severity rating for closure decision.
            is_abrasion = pink_pct > 30
            # Priority 2: deep/necrotic wound (not abrasion) that is severe → needs eval.
            # Only flag as needing closure if it's genuinely a deep wound.
            is_deep_severe = (
                not is_abrasion and (
                    severity == 'severe' or
                    brown_pct > 50 or
                    black_pct > 15
                )
            )
            if is_abrasion:
                # Surface wound — moist care, NOT closure
                st['need_stitches'] = False
                st['recommendation'] = (
                    'This appears to be a surface abrasion wound. Keep it clean and moist '
                    '(saline rinse, petroleum jelly, non-adherent dressing). Stitches are '
                    'not needed for surface abrasions. Seek medical attention if the wound '
                    'is large (> 5 cm), very deep, or does not improve within a few days.'
                )
            elif is_deep_severe and not st.get('need_stitches', False):
                st['need_stitches'] = True
                st['recommendation'] = (
                    'This wound has significant tissue damage. Go to an emergency room or '
                    'urgent care clinic — a doctor needs to assess whether it requires stitches, '
                    'staples, or professional wound cleaning. Do not attempt to close it yourself.'
                )
                st.setdefault('reasons', [])
                if not any('evaluat' in r.lower() or 'medical' in r.lower() for r in st['reasons']):
                    st['reasons'].insert(0, 'Significant tissue damage — in-person medical evaluation required')

        return result

    def _get_rule_based_assessment(self, wound_data: Dict) -> Dict:
        """Fallback rule-based assessment when AI is unavailable."""
        measurements = wound_data.get('measurements', {})
        color_analysis = wound_data.get('color_analysis', {})
        
        area = float(measurements.get('area_cm2', 0))
        length = float(measurements.get('length_cm', 0))
        width = float(measurements.get('width_cm', 0))
        redness = float(color_analysis.get('redness_level', 0))
        yellow = float(color_analysis.get('color_percentages', {}).get('yellow', 0))
        green = float(color_analysis.get('color_percentages', {}).get('green', 0))
        
        # Infection risk
        infection_score = redness * 45 + min(yellow * 1.2, 25) + min(green * 3, 25)
        if infection_score < 30:
            infection_level = "low"
        elif infection_score < 60:
            infection_level = "moderate"
        else:
            infection_level = "high"
        
        # Closure needs
        needs_closure = (length >= 3.0 and width >= 0.6) or width >= 0.8
        
        # Healing time estimate
        if area < 0.5:
            healing_days = "3-7 days"
        elif area < 2.0:
            healing_days = "7-14 days"
        elif area < 6.0:
            healing_days = "14-28 days"
        else:
            healing_days = "21-42 days"
        
        return {
            'infection_risk': f'Level: {infection_level}\nBased on color and size analysis',
            'closure_recommendation': f'Medical closure needed: {"Yes" if needs_closure else "No"}\nBased on wound dimensions',
            'immediate_care': [
                'Clean hands thoroughly before wound care',
                'Gently clean wound with saline or clean water',
                'Apply appropriate sterile dressing'
            ],
            'red_flags': [
                'Increasing redness, warmth, or swelling',
                'Pus or unusual discharge',
                'Fever or feeling unwell'
            ],
            'healing_estimate': f'Expected range: {healing_days}',
            'treatment_recommendations': 'Keep clean, change dressing daily, monitor for infection signs',
            'raw_response': 'Generated by rule-based heuristics'
        }
    
    def _apply_safety_overrides(self, wound_data: Dict) -> List[str]:
        """
        Apply hard safety rules that always trigger medical recommendations.
        These override any AI or rule-based assessments.
        """
        overrides = []
        
        measurements = wound_data.get('measurements', {})
        color_analysis = wound_data.get('color_analysis', {})
        
        area = float(measurements.get('area_cm2', 0))
        length = float(measurements.get('length_cm', 0))
        width = float(measurements.get('width_cm', 0))
        yellow_pct = float(color_analysis.get('color_percentages', {}).get('yellow', 0))
        green_pct = float(color_analysis.get('color_percentages', {}).get('green', 0))
        
        # Critical size thresholds
        if area > 10:
            overrides.append("🚨 CRITICAL: Large wound (>10cm²) - SEEK EMERGENCY MEDICAL CARE IMMEDIATELY")
        elif area > 5:
            overrides.append("⚠️ WARNING: Significant wound size (>5cm²) - Medical evaluation recommended within 24 hours")
        
        # Gaping wounds need closure
        if width > 1.0:
            overrides.append("🚨 URGENT: Gaping wound (>1cm width) - PROFESSIONAL CLOSURE REQUIRED within 6-8 hours for optimal healing")
        elif width > 0.7 and length > 2.5:
            overrides.append("⚠️ WARNING: Wound may benefit from medical closure - Consult healthcare provider within 24 hours")
        
        # Infection indicators
        if green_pct > 0:
            overrides.append("🚨 CRITICAL: Green coloration indicates BACTERIAL INFECTION - SEEK MEDICAL CARE IMMEDIATELY")
        elif yellow_pct > 40:
            overrides.append("⚠️ WARNING: Significant yellow discharge/slough (>40%) - Possible infection, seek medical evaluation")
        
        # Very long wounds (potential deep injuries)
        if length > 8:
            overrides.append("⚠️ WARNING: Extensive wound length (>8cm) - Professional assessment recommended")
        
        return overrides


def format_feedback_for_display(assessment: Dict) -> str:
    """Format AI assessment into readable text for display."""
    output = []
    
    # Header
    output.append("="*60)
    output.append("AI-POWERED CLINICAL ASSESSMENT")
    output.append("="*60)
    output.append(f"Method: {assessment.get('assessment_method', 'Unknown')}")
    output.append("")
    
    # Safety overrides (most important)
    safety = assessment.get('safety_overrides', [])
    if safety:
        output.append("⚠️  CRITICAL SAFETY ALERTS:")
        output.append("-" * 60)
        for override in safety:
            output.append(f"  {override}")
        output.append("")
    
    # Clinical feedback
    feedback = assessment.get('clinical_feedback', {})
    
    if feedback.get('infection_risk'):
        output.append("🦠 INFECTION RISK:")
        output.append(feedback['infection_risk'])
        output.append("")
    
    if feedback.get('closure_recommendation'):
        output.append("🩹 CLOSURE ASSESSMENT:")
        output.append(feedback['closure_recommendation'])
        output.append("")
    
    if feedback.get('immediate_care'):
        output.append("📋 IMMEDIATE CARE PRIORITIES:")
        for i, care in enumerate(feedback['immediate_care'][:5], 1):
            output.append(f"  {i}. {care}")
        output.append("")
    
    if feedback.get('red_flags'):
        output.append("🚩 WARNING SIGNS TO MONITOR:")
        for flag in feedback['red_flags'][:5]:
            output.append(f"  • {flag}")
        output.append("")
    
    if feedback.get('healing_estimate'):
        output.append("⏱️  HEALING TIME ESTIMATE:")
        output.append(f"  {feedback['healing_estimate']}")
        output.append("")
    
    if feedback.get('treatment_recommendations'):
        output.append("💊 TREATMENT RECOMMENDATIONS:")
        output.append(f"  {feedback['treatment_recommendations']}")
        output.append("")
    
    # Disclaimer
    output.append("")
    output.append("="*60)
    output.append(assessment.get('disclaimer', MEDICAL_DISCLAIMER))
    output.append("="*60)
    
    return "\n".join(output)

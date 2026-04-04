# Bugfix Requirements Document

## Introduction

The wound feedback system has critical issues where Gemini's AI-generated measurements and observations are being overridden by Traditional CV measurements, and the rule engine is not properly using Gemini's observations for clinical assessments (particularly stitch recommendations). This results in:
- Incorrect measurements displayed to users (e.g., showing 0.56 cm when actual wound is 3-4 cm)
- Inaccurate stitch assessments (fresh, deep lacerations not being recommended for closure)
- Clinical summaries using wrong measurement values

The system architecture should flow: Image → Gemini Analysis (observations) → Rule Engine (clinical rules) → Frontend Display. Currently, Traditional CV measurements are being displayed instead of Gemini's measurements.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN Gemini analyzes a wound image and returns measurements (e.g., 2.5 cm length) THEN the frontend displays Traditional CV measurements (e.g., 0.56 cm) instead of Gemini's measurements

1.2 WHEN Gemini identifies a fresh laceration with depth and gaping edges (e.g., 3-4 cm wound) THEN the rule engine does not properly assess the need for stitches and recommends "can heal naturally"

1.3 WHEN the clinical summary is generated THEN it uses Traditional CV measurements (e.g., "0.5 cm length, 0.10 cm² area") instead of Gemini's actual measurements

1.4 WHEN Gemini provides observations about wound characteristics (depth, gaping, tissue types) THEN the rule engine receives these observations but the frontend displays Traditional CV measurements instead

### Expected Behavior (Correct)

2.1 WHEN Gemini analyzes a wound image and returns measurements THEN the frontend SHALL display Gemini's measurements (not Traditional CV measurements)

2.2 WHEN Gemini identifies a fresh laceration >2cm with depth and gaping edges THEN the rule engine SHALL accurately recommend stitches based on Gemini's observations

2.3 WHEN the clinical summary is generated THEN it SHALL use Gemini's measurements in the summary text

2.4 WHEN Gemini provides observations about wound characteristics THEN both the rule engine and frontend SHALL use Gemini's observations for all assessments and displays

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the system uses Traditional CV analysis (without AI) THEN it SHALL CONTINUE TO display Traditional CV measurements and assessments

3.2 WHEN Gemini analysis fails or is unavailable THEN the system SHALL CONTINUE TO fall back to Traditional CV analysis

3.3 WHEN the rule engine applies clinical rules to observations THEN it SHALL CONTINUE TO generate evidence-based recommendations (infection risk, healing time, scar risk)

3.4 WHEN the system generates treatment recommendations THEN it SHALL CONTINUE TO provide immediate care, ongoing care, medications, warning signs, and follow-up guidance

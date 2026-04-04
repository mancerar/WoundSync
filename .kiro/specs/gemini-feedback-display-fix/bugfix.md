# Bugfix Requirements Document

## Introduction

When users analyze wound images on the website, the Roboflow model successfully detects and boxes the wound, but the Gemini AI model's detailed feedback is not displaying on the website form. The Gemini model is configured and generating analysis (including wound assessment with measurements, color analysis, healing indicators, infection likelihood, healing time prediction, treatment recommendations, and clinical summary), but this comprehensive feedback is not reaching the frontend display.

The expected behavior is that users should see the complete Gemini analysis output formatted nicely on the website, including all the detailed wound assessment information that the AI generates.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the /predict endpoint is called with a wound image THEN the system generates Gemini feedback via `ai_gen.generate_clinical_assessment()` but only stores it in the `gemini_feedback` field

1.2 WHEN the comprehensive wound analysis is performed via `analyze_wound_image()` THEN the system generates a complete `healing_assessment` structure but this is not included in the /predict endpoint response

1.3 WHEN the frontend receives the /predict response THEN the system displays only the `gemini_feedback` field (if present) but not the comprehensive `healing_assessment` data structure

1.4 WHEN the comprehensive analysis includes measurements, color_analysis, healing_assessment, recommendations, and overall_assessment THEN the system does not merge this data into the /predict response payload

### Expected Behavior (Correct)

2.1 WHEN the /predict endpoint is called with a wound image THEN the system SHALL include the complete comprehensive wound analysis (measurements, color_analysis, healing_assessment, recommendations, overall_assessment) in the response

2.2 WHEN the comprehensive wound analysis is performed THEN the system SHALL merge the healing_assessment data structure into the response payload at the top level

2.3 WHEN the frontend receives the /predict response THEN the system SHALL display all healing_assessment fields including healing_stage, severity, infection_risk, healing_time_prediction, stitches, scar_risk, concerns, healing_indicators, and recommendations

2.4 WHEN Gemini generates the clinical assessment THEN the system SHALL ensure the structured data (not just text feedback) is properly formatted and included in the response

### Unchanged Behavior (Regression Prevention)

3.1 WHEN Roboflow detection succeeds THEN the system SHALL CONTINUE TO return the bounding box, confidence, and annotated image

3.2 WHEN the image quality assessment is performed THEN the system SHALL CONTINUE TO return the assessment field with urgency, wound_type, and guidance

3.3 WHEN Gemini AI is unavailable or fails THEN the system SHALL CONTINUE TO handle the error gracefully without breaking the entire analysis

3.4 WHEN the /predict endpoint returns a response THEN the system SHALL CONTINUE TO maintain backward compatibility with existing response fields (ok, detected, confidence, class, bbox, annotated_image, assessment)

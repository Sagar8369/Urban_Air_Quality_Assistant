import json
import logging
import re

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Profile-specific concerns for tailored recommendations
USER_PROFILE_CONCERNS = {
    'family_with_children': (
        'You are advising a family with young children. Children are more vulnerable to air '
        'pollution due to their developing lungs and higher breathing rates. Focus on child-safe '
        'indoor activities, school commute alternatives, and child-friendly health precautions.'
    ),
    'working_professional': (
        'You are advising a working professional who commutes daily. Focus on commute optimization, '
        'office air quality, work-from-home considerations, and balancing productivity with health.'
    ),
    'elderly': (
        'You are advising an elderly individual. Older adults are at higher risk from air pollution '
        'due to pre-existing conditions. Focus on medication interactions, gentle indoor exercises, '
        'and minimizing exposure during daily routines.'
    ),
    'student': (
        'You are advising a student. Focus on campus air quality, study environment optimization, '
        'sustainable transport to school/university, and affordable protective measures.'
    ),
    'fitness_enthusiast': (
        'You are advising a fitness enthusiast who exercises regularly. Focus on safe workout windows, '
        'indoor exercise alternatives, respiratory protection during outdoor activities, and '
        'performance impacts of air quality.'
    ),
    'pregnant_woman': (
        'You are advising a pregnant woman. Air pollution exposure during pregnancy can affect fetal '
        'development. Focus on maximum protection, safe indoor environments, prenatal health '
        'considerations, and when to seek medical advice.'
    ),
}


class GeminiService:
    """Service for generating personalized air quality recommendations using Gemini."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

    def get_recommendations(self, aqi_data: dict, user_profile: dict) -> dict | None:
        """Generate personalized recommendations based on AQI data and user profile."""
        try:
            profile_type = user_profile.get('type', 'working_professional')
            profile_concerns = USER_PROFILE_CONCERNS.get(
                profile_type, USER_PROFILE_CONCERNS['working_professional']
            )
            profile_details = user_profile.get('details', '')

            prompt = self._build_prompt(aqi_data, profile_type, profile_concerns, profile_details)
            response = self.model.generate_content(prompt)

            return self._parse_response(response.text)

        except Exception as e:
            logger.error("Error generating recommendations: %s", e)
            return None

    def _build_prompt(
        self,
        aqi_data: dict,
        profile_type: str,
        profile_concerns: str,
        profile_details: str,
    ) -> str:
        """Build the prompt for Gemini with AQI data and user context."""
        pollutants = aqi_data.get('pollutants', {})
        pollutant_lines = '\n'.join(
            f"  - {k.upper()}: {v if v is not None else 'N/A'}"
            for k, v in pollutants.items()
        )

        return f"""You are an expert urban air quality health advisor and sustainability consultant.

Analyze the following real-time air quality data and provide personalized, actionable recommendations.

## Current Air Quality Data
- **Location**: {aqi_data.get('city', 'Unknown')}
- **AQI**: {aqi_data.get('aqi', 'N/A')}
- **Dominant Pollutant**: {aqi_data.get('dominant_pollutant', 'N/A')}
- **Pollutant Levels**:
{pollutant_lines}
- **Last Updated**: {aqi_data.get('time_updated', 'N/A')}

## User Profile
- **Type**: {profile_type.replace('_', ' ').title()}
- **Specific Concerns**: {profile_concerns}
{f'- **Additional Details**: {profile_details}' if profile_details else ''}

## Instructions
Provide your response as a **valid JSON object** (no markdown code fences, no extra text) with this exact structure:

{{
  "aqi_summary": "A clear, plain-language explanation of the current air quality and what the AQI number means for this location",
  "health_risk_level": "low or moderate or high or very_high or hazardous",
  "low_emission_routines": [
    {{
      "title": "Short title",
      "description": "Detailed actionable description",
      "impact": "Explain the environmental impact of this choice",
      "time_of_day": "morning or afternoon or evening or all_day",
      "icon": "relevant emoji"
    }}
  ],
  "indoor_air_quality_hacks": [
    {{
      "title": "Short title",
      "description": "Detailed actionable description",
      "effectiveness": "High or Medium or Low",
      "cost": "Free or Low or Medium or High",
      "icon": "relevant emoji"
    }}
  ],
  "sustainable_alternatives": [
    {{
      "title": "Short title",
      "current_practice": "What people typically do",
      "alternative": "The sustainable alternative",
      "environmental_impact": "Quantified impact explanation",
      "icon": "relevant emoji"
    }}
  ],
  "immediate_actions": ["action1", "action2", "action3"],
  "outdoor_activity_windows": "When is it safest to go outside today based on typical pollution patterns",
  "weekly_wellness_tips": ["tip1", "tip2", "tip3"]
}}

Provide at least 3 items for each array field. Make recommendations specific to the AQI level and user profile.
Respond ONLY with the JSON object, no other text."""

    @staticmethod
    def _parse_response(text: str) -> dict | None:
        """Parse JSON from Gemini's response, handling markdown code blocks."""
        if not text:
            return None

        # Strip markdown code fences if present
        cleaned = text.strip()
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find any JSON object in the text
            obj_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if obj_match:
                try:
                    return json.loads(obj_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.error("Failed to parse Gemini response as JSON: %s", text[:200])
            return None

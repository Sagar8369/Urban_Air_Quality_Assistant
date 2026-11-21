"""Unit tests for GeminiService."""

import json
import unittest
from unittest.mock import MagicMock, patch

from services.gemini_service import GeminiService, USER_PROFILE_CONCERNS


class TestGeminiService(unittest.TestCase):
    """Test suite for GeminiService."""

    @patch("services.gemini_service.genai.configure")
    @patch("services.gemini_service.genai.GenerativeModel")
    def setUp(self, mock_model_cls, mock_configure):
        self.mock_model = MagicMock()
        mock_model_cls.return_value = self.mock_model
        self.service = GeminiService(api_key="test_gemini_key")

    def test_parse_response_clean_json(self):
        """Test parsing clean JSON text."""
        raw_json = json.dumps({
            "aqi_summary": "Moderate air quality in Delhi.",
            "health_risk_level": "moderate",
            "immediate_actions": ["Keep windows closed during peak hours"],
            "outdoor_activity_windows": "Best after 4 PM.",
            "low_emission_routines": [],
            "indoor_air_quality_hacks": [],
            "sustainable_alternatives": [],
            "weekly_wellness_tips": ["Stay hydrated"],
        })
        parsed = self.service._parse_response(raw_json)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["health_risk_level"], "moderate")
        self.assertEqual(len(parsed["immediate_actions"]), 1)

    def test_parse_response_with_code_fences(self):
        """Test parsing JSON enclosed in markdown code fences."""
        raw_text = """```json
{
  "aqi_summary": "Clean air today.",
  "health_risk_level": "low",
  "immediate_actions": ["Enjoy outdoor exercise"],
  "outdoor_activity_windows": "All day",
  "low_emission_routines": [],
  "indoor_air_quality_hacks": [],
  "sustainable_alternatives": [],
  "weekly_wellness_tips": ["Keep plants indoors"]
}
```"""
        parsed = self.service._parse_response(raw_text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["health_risk_level"], "low")

    def test_parse_response_invalid_json(self):
        """Test handling of invalid non-JSON response."""
        parsed = self.service._parse_response("Sorry, I cannot fulfill this request.")
        self.assertIsNone(parsed)

    def test_build_prompt_structure(self):
        """Test prompt construction includes AQI and user profile details."""
        aqi_data = {
            "city": "Mumbai",
            "aqi": 115,
            "dominant_pollutant": "pm25",
            "pollutants": {"pm25": 115, "pm10": 160},
            "time_updated": "2026-11-21 14:00",
        }
        prompt = self.service._build_prompt(
            aqi_data=aqi_data,
            profile_type="fitness_enthusiast",
            profile_concerns=USER_PROFILE_CONCERNS["fitness_enthusiast"],
            profile_details="Running 10km daily morning outdoors",
        )
        self.assertIn("Mumbai", prompt)
        self.assertIn("115", prompt)
        self.assertIn("PM25: 115", prompt)
        self.assertIn("Fitness Enthusiast", prompt)
        self.assertIn("Running 10km daily", prompt)

    def test_get_recommendations_success(self):
        """Test end-to-end get_recommendations with mocked model."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "aqi_summary": "Air is good.",
            "health_risk_level": "low",
            "immediate_actions": ["Ventilate rooms"],
            "outdoor_activity_windows": "Morning hours",
            "low_emission_routines": [],
            "indoor_air_quality_hacks": [],
            "sustainable_alternatives": [],
            "weekly_wellness_tips": ["Stay active"],
        })
        self.service.model.generate_content.return_value = mock_response

        aqi_data = {"city": "Zurich", "aqi": 25, "pollutants": {}}
        user_profile = {"type": "student", "details": "University campus study"}

        result = self.service.get_recommendations(aqi_data, user_profile)
        self.assertIsNotNone(result)
        self.assertEqual(result["health_risk_level"], "low")

    def test_get_recommendations_model_exception(self):
        """Test handling when model generation raises an exception."""
        self.service.model.generate_content.side_effect = RuntimeError("API quota exceeded")
        result = self.service.get_recommendations({"city": "Test"}, {"type": "elderly"})
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

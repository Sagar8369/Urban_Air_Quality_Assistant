"""Integration tests for Flask application routes."""

import json
import unittest
from unittest.mock import patch

from app import app


class TestAppRoutes(unittest.TestCase):
    """Test suite for Flask endpoints."""

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_index_route(self):
        """Test GET / returns 200 and loads HTML page."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"UrbanAir", response.data)
        self.assertIn(b"main.js", response.data)

    def test_health_check(self):
        """Test GET /api/health returns 200 with status ok."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "ok")

    @patch("app.air_quality_service.get_aqi_by_city")
    def test_air_quality_by_city_success(self, mock_get_city):
        """Test POST /api/air-quality with valid city."""
        mock_get_city.return_value = {
            "aqi": 82,
            "city": "Bengaluru",
            "station_name": "Bengaluru City",
            "dominant_pollutant": "pm25",
            "pollutants": {"pm25": 82},
            "time_updated": "2026-11-21 12:00",
            "coordinates": {"lat": 12.9716, "lng": 77.5946},
        }

        response = self.client.post(
            "/api/air-quality",
            data=json.dumps({"city": "Bengaluru"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["data"]["city"], "Bengaluru")
        self.assertEqual(data["data"]["category"]["level"], "Moderate")
        self.assertIn("health_implications", data["data"])

    @patch("app.air_quality_service.get_aqi_by_coordinates")
    def test_air_quality_by_coords_success(self, mock_get_coords):
        """Test POST /api/air-quality with lat & lng."""
        mock_get_coords.return_value = {
            "aqi": 35,
            "city": "Tokyo",
            "station_name": "Tokyo Shinjuku",
            "dominant_pollutant": "o3",
            "pollutants": {"o3": 35},
            "time_updated": "2026-11-21 12:00",
            "coordinates": {"lat": 35.6762, "lng": 139.6503},
        }

        response = self.client.post(
            "/api/air-quality",
            data=json.dumps({"lat": 35.6762, "lng": 139.6503}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["data"]["category"]["level"], "Good")

    def test_air_quality_missing_body(self):
        """Test POST /api/air-quality with non-JSON or missing body."""
        response = self.client.post("/api/air-quality", data="not json")
        self.assertEqual(response.status_code, 400)

    def test_air_quality_missing_params(self):
        """Test POST /api/air-quality without city or coordinates."""
        response = self.client.post(
            "/api/air-quality",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.air_quality_service.get_aqi_by_city")
    def test_air_quality_not_found(self, mock_get_city):
        """Test POST /api/air-quality when service returns None."""
        mock_get_city.return_value = None
        response = self.client.post(
            "/api/air-quality",
            data=json.dumps({"city": "NonExistentCityXYZ"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    @patch("app.gemini_service.get_recommendations")
    def test_recommendations_success(self, mock_get_recs):
        """Test POST /api/recommendations with valid input."""
        mock_get_recs.return_value = {
            "aqi_summary": "Good conditions.",
            "health_risk_level": "low",
            "immediate_actions": ["Enjoy outdoors"],
            "outdoor_activity_windows": "Morning to noon",
            "low_emission_routines": [],
            "indoor_air_quality_hacks": [],
            "sustainable_alternatives": [],
            "weekly_wellness_tips": [],
        }

        payload = {
            "aqi_data": {"city": "Berlin", "aqi": 30},
            "user_profile": {"type": "student", "details": "Active daily"},
        }

        response = self.client.post(
            "/api/recommendations",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["data"]["health_risk_level"], "low")

    def test_recommendations_missing_aqi_data(self):
        """Test POST /api/recommendations missing required aqi_data."""
        response = self.client.post(
            "/api/recommendations",
            data=json.dumps({"user_profile": {"type": "elderly"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.air_quality_service.search_stations")
    def test_search_stations_success(self, mock_search):
        """Test GET /api/search-stations with query."""
        mock_search.return_value = [
            {"station_name": "Central London", "aqi": 45, "uid": 1}
        ]

        response = self.client.get("/api/search-stations?q=london")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(len(data["data"]), 1)

    def test_search_stations_missing_query(self):
        """Test GET /api/search-stations without query parameter."""
        response = self.client.get("/api/search-stations")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

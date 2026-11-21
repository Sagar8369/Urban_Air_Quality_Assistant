"""Unit tests for AirQualityService."""

import unittest
from unittest.mock import MagicMock, patch
import requests

from services.air_quality_service import AirQualityService


class TestAirQualityService(unittest.TestCase):
    """Test suite for AirQualityService."""

    def setUp(self):
        self.api_token = "dummy_token"
        self.service = AirQualityService(api_token=self.api_token)

    @patch("services.air_quality_service.requests.get")
    def test_get_aqi_by_city_success(self, mock_get):
        """Test fetching AQI data for a valid city."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "aqi": 85,
                "city": {"name": "Delhi", "geo": [28.6139, 77.2090]},
                "dominentpol": "pm25",
                "iaqi": {
                    "pm25": {"v": 85},
                    "pm10": {"v": 120},
                    "o3": {"v": 30},
                    "no2": {"v": 25},
                    "so2": {"v": 10},
                    "co": {"v": 5},
                },
                "time": {"s": "2026-11-21 12:00:00"},
            },
        }
        mock_get.return_value = mock_response

        result = self.service.get_aqi_by_city("Delhi")
        self.assertIsNotNone(result)
        self.assertEqual(result["aqi"], 85)
        self.assertEqual(result["city"], "Delhi")
        self.assertEqual(result["dominant_pollutant"], "pm25")
        self.assertEqual(result["pollutants"]["pm25"], 85)
        self.assertEqual(result["coordinates"]["lat"], 28.6139)

    @patch("services.air_quality_service.requests.get")
    def test_get_aqi_by_city_error_status(self, mock_get):
        """Test API returning error status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "error",
            "data": "Unknown station",
        }
        mock_get.return_value = mock_response

        result = self.service.get_aqi_by_city("InvalidCity12345")
        self.assertIsNone(result)

    @patch("services.air_quality_service.requests.get")
    def test_get_aqi_by_city_network_exception(self, mock_get):
        """Test handling network exception when fetching AQI."""
        mock_get.side_effect = requests.RequestException("Network unreachable")

        result = self.service.get_aqi_by_city("London")
        self.assertIsNone(result)

    @patch("services.air_quality_service.requests.get")
    def test_get_aqi_by_coordinates_success(self, mock_get):
        """Test fetching AQI by latitude and longitude."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "aqi": 42,
                "city": {"name": "London Central", "geo": [51.5074, -0.1278]},
                "dominentpol": "o3",
                "iaqi": {"o3": {"v": 42}},
                "time": {"s": "2026-11-21 12:00:00"},
            },
        }
        mock_get.return_value = mock_response

        result = self.service.get_aqi_by_coordinates(51.5074, -0.1278)
        self.assertIsNotNone(result)
        self.assertEqual(result["aqi"], 42)
        self.assertEqual(result["city"], "London Central")

    @patch("services.air_quality_service.requests.get")
    def test_search_stations_success(self, mock_get):
        """Test station search keyword parsing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": [
                {
                    "aqi": "95",
                    "station": {"name": "Delhi Anand Vihar", "geo": [28.6468, 77.3160]},
                    "time": {"stime": "2026-11-21 11:00:00"},
                    "uid": 1234,
                }
            ],
        }
        mock_get.return_value = mock_response

        stations = self.service.search_stations("delhi")
        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0]["station_name"], "Delhi Anand Vihar")
        self.assertEqual(stations[0]["uid"], 1234)

    @patch("services.air_quality_service.requests.get")
    def test_search_stations_error_handling(self, mock_get):
        """Test station search when network fails."""
        mock_get.side_effect = requests.RequestException("Search timeout")
        stations = self.service.search_stations("paris")
        self.assertEqual(stations, [])

    def test_get_aqi_category_boundaries(self):
        """Test all 6 AQI category thresholds."""
        # Good (0 - 50)
        self.assertEqual(AirQualityService.get_aqi_category(25)["level"], "Good")
        self.assertEqual(AirQualityService.get_aqi_category(50)["level"], "Good")

        # Moderate (51 - 100)
        self.assertEqual(AirQualityService.get_aqi_category(51)["level"], "Moderate")
        self.assertEqual(AirQualityService.get_aqi_category(100)["level"], "Moderate")

        # Unhealthy for Sensitive Groups (101 - 150)
        self.assertEqual(
            AirQualityService.get_aqi_category(101)["level"],
            "Unhealthy for Sensitive Groups",
        )
        self.assertEqual(
            AirQualityService.get_aqi_category(150)["level"],
            "Unhealthy for Sensitive Groups",
        )

        # Unhealthy (151 - 200)
        self.assertEqual(AirQualityService.get_aqi_category(151)["level"], "Unhealthy")
        self.assertEqual(AirQualityService.get_aqi_category(200)["level"], "Unhealthy")

        # Very Unhealthy (201 - 300)
        self.assertEqual(
            AirQualityService.get_aqi_category(201)["level"], "Very Unhealthy"
        )
        self.assertEqual(
            AirQualityService.get_aqi_category(300)["level"], "Very Unhealthy"
        )

        # Hazardous (> 300)
        self.assertEqual(AirQualityService.get_aqi_category(301)["level"], "Hazardous")
        self.assertEqual(AirQualityService.get_aqi_category(500)["level"], "Hazardous")

    def test_get_health_implications(self):
        """Test health implication descriptions across AQI bands."""
        self.assertIn("satisfactory", AirQualityService.get_health_implications(30).lower())
        self.assertIn("acceptable", AirQualityService.get_health_implications(75).lower())
        self.assertIn("respiratory", AirQualityService.get_health_implications(120).lower())
        self.assertIn("n95", AirQualityService.get_health_implications(180).lower())
        self.assertIn("health alert", AirQualityService.get_health_implications(250).lower())
        self.assertIn("emergency", AirQualityService.get_health_implications(400).lower())


if __name__ == "__main__":
    unittest.main()

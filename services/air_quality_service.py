import logging
import requests

logger = logging.getLogger(__name__)


class AirQualityService:
    """Service for fetching air quality data from the WAQI API."""

    def __init__(self, api_token: str, base_url: str = 'https://api.waqi.info'):
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')

    def get_aqi_by_city(self, city: str) -> dict | None:
        """Fetch AQI data for a given city name."""
        url = f"{self.base_url}/feed/{city}/?token={self.api_token}"
        return self._fetch_and_normalize(url)

    def get_aqi_by_coordinates(self, lat: float, lng: float) -> dict | None:
        """Fetch AQI data for given geographic coordinates."""
        url = f"{self.base_url}/feed/geo:{lat};{lng}/?token={self.api_token}"
        return self._fetch_and_normalize(url)

    def search_stations(self, keyword: str) -> list:
        """Search for AQI monitoring stations by keyword."""
        url = f"{self.base_url}/search/?keyword={keyword}&token={self.api_token}"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'ok':
                logger.error("WAQI search error: %s", data.get('data', 'Unknown error'))
                return []

            stations = []
            for item in data.get('data', []):
                station = {
                    'aqi': item.get('aqi'),
                    'station_name': item.get('station', {}).get('name', 'Unknown'),
                    'city': item.get('station', {}).get('name', 'Unknown'),
                    'time_updated': item.get('time', {}).get('stime', ''),
                    'coordinates': {
                        'lat': item.get('station', {}).get('geo', [None, None])[0],
                        'lng': item.get('station', {}).get('geo', [None, None])[1],
                    },
                    'uid': item.get('uid'),
                }
                stations.append(station)

            return stations

        except requests.RequestException as e:
            logger.error("Error searching stations: %s", e)
            return []
        except (ValueError, KeyError, IndexError) as e:
            logger.error("Error parsing station search results: %s", e)
            return []

    def _fetch_and_normalize(self, url: str) -> dict | None:
        """Fetch data from WAQI API and normalize the response."""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'ok':
                logger.error("WAQI API error: %s", data.get('data', 'Unknown error'))
                return None

            return self._normalize_response(data['data'])

        except requests.RequestException as e:
            logger.error("Error fetching AQI data: %s", e)
            return None
        except (ValueError, KeyError) as e:
            logger.error("Error parsing AQI response: %s", e)
            return None

    def _normalize_response(self, data: dict) -> dict:
        """Normalize raw WAQI API response into a consistent format."""
        iaqi = data.get('iaqi', {})

        def _pollutant_val(key: str):
            return iaqi.get(key, {}).get('v')

        city_data = data.get('city', {})
        geo = city_data.get('geo', [None, None])

        return {
            'aqi': data.get('aqi'),
            'station_name': city_data.get('name', 'Unknown'),
            'city': city_data.get('name', 'Unknown'),
            'dominant_pollutant': data.get('dominentpol', 'N/A'),
            'pollutants': {
                'pm25': _pollutant_val('pm25'),
                'pm10': _pollutant_val('pm10'),
                'o3': _pollutant_val('o3'),
                'no2': _pollutant_val('no2'),
                'so2': _pollutant_val('so2'),
                'co': _pollutant_val('co'),
            },
            'time_updated': data.get('time', {}).get('s', ''),
            'coordinates': {
                'lat': geo[0] if len(geo) > 0 else None,
                'lng': geo[1] if len(geo) > 1 else None,
            },
        }

    @staticmethod
    def get_aqi_category(aqi: int) -> dict:
        """Return the AQI category, color, and health message for a given AQI value."""
        if aqi <= 50:
            return {
                'level': 'Good',
                'color': '#009966',
                'health_message': 'Air quality is satisfactory, and air pollution poses little or no risk.',
            }
        elif aqi <= 100:
            return {
                'level': 'Moderate',
                'color': '#FFDE33',
                'health_message': 'Air quality is acceptable. However, there may be a risk for some people, particularly those who are unusually sensitive to air pollution.',
            }
        elif aqi <= 150:
            return {
                'level': 'Unhealthy for Sensitive Groups',
                'color': '#FF9933',
                'health_message': 'Members of sensitive groups may experience health effects. The general public is less likely to be affected.',
            }
        elif aqi <= 200:
            return {
                'level': 'Unhealthy',
                'color': '#CC0033',
                'health_message': 'Some members of the general public may experience health effects; members of sensitive groups may experience more serious health effects.',
            }
        elif aqi <= 300:
            return {
                'level': 'Very Unhealthy',
                'color': '#660099',
                'health_message': 'Health alert: The risk of health effects is increased for everyone.',
            }
        else:
            return {
                'level': 'Hazardous',
                'color': '#7E0023',
                'health_message': 'Health warning of emergency conditions: everyone is more likely to be affected.',
            }

    @staticmethod
    def get_health_implications(aqi: int) -> str:
        """Return detailed health implications based on AQI value."""
        if aqi <= 50:
            return (
                "Air quality is considered satisfactory. Enjoy your normal outdoor activities. "
                "No health implications for the general population."
            )
        elif aqi <= 100:
            return (
                "Air quality is acceptable, but unusually sensitive individuals may experience "
                "respiratory symptoms. Consider reducing prolonged outdoor exertion if you "
                "experience symptoms like coughing or shortness of breath."
            )
        elif aqi <= 150:
            return (
                "People with respiratory or heart conditions, the elderly, and children should "
                "limit prolonged outdoor exertion. The general public is not likely to be affected. "
                "Consider wearing a mask if you have asthma or other respiratory conditions."
            )
        elif aqi <= 200:
            return (
                "Everyone may begin to experience health effects. Members of sensitive groups may "
                "experience more serious effects. Avoid prolonged outdoor exertion. Keep windows "
                "closed and use air purifiers indoors. Wear an N95 mask if going outside."
            )
        elif aqi <= 300:
            return (
                "Health alert: everyone may experience more serious health effects. Avoid all "
                "outdoor physical activities. Keep windows and doors sealed. Use HEPA air "
                "purifiers. Wear an N95 or P100 mask if outdoor exposure is unavoidable. "
                "Seek medical attention if you experience difficulty breathing."
            )
        else:
            return (
                "Health warning of emergency conditions. The entire population is at risk. "
                "Stay indoors with air purification. Avoid any outdoor exposure. Seal windows "
                "and doors. If you must go outside, wear a P100 respirator. Seek immediate "
                "medical attention for any respiratory or cardiovascular symptoms."
            )

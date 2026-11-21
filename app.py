import logging

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import Config
from services.air_quality_service import AirQualityService
from services.gemini_service import GeminiService

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
air_quality_service = AirQualityService(
    api_token=Config.WAQI_API_TOKEN,
    base_url=Config.WAQI_BASE_URL,
)
gemini_service = GeminiService(api_key=Config.GEMINI_API_KEY)


# ===========================================================================
# Routes
# ===========================================================================

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/health')
def health():
    """Health-check endpoint."""
    return jsonify({'status': 'ok'})


@app.route('/api/air-quality', methods=['POST'])
def get_air_quality():
    """Return AQI data for a city name or coordinates."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    city = data.get('city')
    lat = data.get('lat')
    lng = data.get('lng')

    if city:
        aqi_data = air_quality_service.get_aqi_by_city(city)
    elif lat is not None and lng is not None:
        aqi_data = air_quality_service.get_aqi_by_coordinates(float(lat), float(lng))
    else:
        return jsonify({'error': 'Provide either "city" or "lat" and "lng"'}), 400

    if aqi_data is None:
        return jsonify({'error': 'Could not fetch air quality data. Check the city name or coordinates.'}), 404

    # Enrich with category info
    aqi_value = aqi_data.get('aqi')
    if isinstance(aqi_value, (int, float)):
        aqi_int = int(aqi_value)
        aqi_data['category'] = AirQualityService.get_aqi_category(aqi_int)
        aqi_data['health_implications'] = AirQualityService.get_health_implications(aqi_int)

    return jsonify({'status': 'ok', 'data': aqi_data})


@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    """Generate personalized recommendations from Gemini based on AQI data."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    aqi_data = data.get('aqi_data')
    user_profile = data.get('user_profile', {'type': 'working_professional'})

    if not aqi_data:
        return jsonify({'error': '"aqi_data" is required'}), 400

    recommendations = gemini_service.get_recommendations(aqi_data, user_profile)
    if recommendations is None:
        return jsonify({'error': 'Could not generate recommendations. Please try again.'}), 500

    return jsonify({'status': 'ok', 'data': recommendations})


@app.route('/api/search-stations')
def search_stations():
    """Search for AQI monitoring stations by keyword."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400

    stations = air_quality_service.search_stations(query)
    return jsonify({'status': 'ok', 'data': stations})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)

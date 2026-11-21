import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    WAQI_API_TOKEN = os.getenv('WAQI_API_TOKEN')
    WAQI_BASE_URL = 'https://api.waqi.info'
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1')

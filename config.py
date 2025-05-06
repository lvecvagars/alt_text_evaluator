import os
from dotenv import load_dotenv

# Drošības pēc ielādējam .env arī šeit, ja tas nav izdarīts citur
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# --- Nolasām no vides mainīgajiem ar noklusējuma vērtībām ---
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
GOOGLE_CLOUD_PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID')

ENABLE_VISION_API = os.environ.get('ENABLE_VISION_API', 'True').lower() == 'true'
ENABLE_TRANSLATION_API = os.environ.get('ENABLE_TRANSLATION_API', 'True').lower() == 'true'

TARGET_TRANSLATION_LANGUAGE = os.environ.get('TARGET_TRANSLATION_LANGUAGE', 'lv')

VISION_API_MIN_CONFIDENCE = float(os.environ.get('VISION_API_MIN_CONFIDENCE', 0.65))
MAX_AI_LABELS_TO_SHOW = int(os.environ.get('MAX_AI_LABELS_TO_SHOW', 5))

USER_AGENT = os.environ.get('USER_AGENT', 'Mozilla/5.0 (compatible; AltTextCheckerBot/1.1; +http://example.com/alt-text-checker-info)')
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 15))

FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'


# --- Fiksētas vai mazāk mainīgas vērtības ---
FORBIDDEN_PHRASES = {
    'lv': ["attēls par", "bilde par", "foto", "logo", "ikona", "grafiks", "diagramma"],
    'en': ["picture of", "image of", "photo of", "photo", "graphic of", "graphic", "logo", "icon", "chart", "diagram", "screenshot"]
}
SUPPORTED_LANGUAGES = { 'lv': 'lv_LV', 'en': 'en_US' }
USER_SPECIFIED_MAX_ALT_LENGTH = 125
USER_SPECIFIED_MIN_ALT_LENGTH = 5

# --- Pārbaude kritiskajiem mainīgajiem ---
if not GOOGLE_CLOUD_PROJECT_ID and (ENABLE_VISION_API or ENABLE_TRANSLATION_API):
    print("BRĪDINĀJUMS: GOOGLE_CLOUD_PROJECT_ID nav iestatīts!")
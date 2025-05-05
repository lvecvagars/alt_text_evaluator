import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

FORBIDDEN_PHRASES = {
    'lv': [
        "attēls par", "bilde par", "foto",
        "logo", "ikona", "grafiks", "diagramma"
    ],
    'en': [
        "picture of", "image of", "photo of", "photo", "graphic of", "graphic",
        "logo", "icon", "chart", "diagram", "screenshot"
    ]
}

USER_AGENT = 'Mozilla/5.0 (compatible; AltTextCheckerBot/1.1; +http://example.com/alt-text-checker-info)'
REQUEST_TIMEOUT = 15

ENABLE_VISION_API = True
VISION_API_MIN_CONFIDENCE = 0.65
MAX_AI_LABELS_TO_SHOW = 5

ENABLE_TRANSLATION_API = True
TARGET_TRANSLATION_LANGUAGE = 'lv'

# !!! AIZSTĀT ŠO ar Jūsu Google Cloud Projekta ID !!!
GOOGLE_CLOUD_PROJECT_ID = 'jusu-projekta-id'

# !!! AIZSTĀT ŠO ar ceļu uz Jūsu JSON atslēgas failu VAI iestatiet vides mainīgo !!!
GOOGLE_APPLICATION_CREDENTIALS = '/path/to/your/keyfile.json'

SUPPORTED_LANGUAGES = {
    'lv': 'lv_LV',
    'en': 'en_US'
}
USER_SPECIFIED_MAX_ALT_LENGTH = 125
USER_SPECIFIED_MIN_ALT_LENGTH = 5
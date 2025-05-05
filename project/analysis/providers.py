import logging
from flask import current_app, g

vision = None
translate = None
google_exceptions = None
vision_client_available = False
translation_client_available = False

logger = logging.getLogger(__name__)

# Mēģinām importēt bibliotēkas ielādes laikā
try:
    from google.cloud import vision
    from google.api_core import exceptions as google_exceptions
    vision_client_available = True
    logger.info("google-cloud-vision bibliotēka atrasta.")
except ImportError:
    logger.warning("'google-cloud-vision' bibliotēka nav instalēta. Vision API nebūs pieejams.")

try:
    from google.cloud import translate_v2 as translate
    translation_client_available = True
    logger.info("google-cloud-translate bibliotēka atrasta.")
except ImportError:
    logger.warning("'google-cloud-translate' bibliotēka nav instalēta. Translation API nebūs pieejams.")


def get_vision_client():
    """Atgriež inicializētu Vision API klientu, izmantojot Flask 'g' objektu."""
    if not vision_client_available or not current_app.config.get('ENABLE_VISION_API'):
        return None
    # Izmantojam g objektu, lai saglabātu klientu pieprasījuma kontekstā
    if 'vision_client' not in g:
        try:
            g.vision_client = vision.ImageAnnotatorClient()
            logger.info("Vision API klients inicializēts pieprasījumam.")
        except Exception as e:
            logger.error(f"Neizdevās inicializēt Vision API klientu: {e}", exc_info=True)
            g.vision_client = None # Atzīmējam kā neizdevušos
    return g.vision_client

def get_translation_client():
    """Atgriež inicializētu Translation API klientu, izmantojot Flask 'g' objektu."""
    if not translation_client_available or not current_app.config.get('ENABLE_TRANSLATION_API'):
        return None
    if 'translation_client' not in g:
        try:
            g.translation_client = translate.Client()
            logger.info("Translation API v2 klients inicializēts pieprasījumam.")
        except Exception as e:
            logger.error(f"Neizdevās inicializēt Translation API klientu: {e}", exc_info=True)
            g.translation_client = None
    return g.translation_client


def get_vision_api_labels(image_uri):
    """Izsauc Google Vision API label_detection un atgriež atslēgvārdu sarakstu."""
    client = get_vision_client()
    if not client:
        return None, "Vision API klients nav pieejams."

    labels_list = []
    error_message = None
    min_confidence = current_app.config.get('VISION_API_MIN_CONFIDENCE', 0.65)

    try:
        logger.info(f"Vaicājam Vision API: {image_uri[:80]}...")
        image = vision.Image()
        image.source.image_uri = image_uri
        response = client.label_detection(image=image)

        if response.error.message:
            error_message = f'Vision API kļūda: {response.error.message}'
            logger.error(error_message)
            return None, error_message

        annotations = response.label_annotations
        if annotations:
            for label in annotations:
                if label.score >= min_confidence:
                    labels_list.append(label.description.lower())
            logger.info(f"Vision API atrasti {len(labels_list)} atslēgvārdi.")
        else:
            logger.info(f"Vision API neatgrieza atslēgvārdus: {image_uri[:80]}")
            error_message = "AI neatpazina atslēgvārdus."

    except google_exceptions.GoogleAPIError as e:
        error_message = f"Google API kļūda (Vision): {e}"
        logger.error(error_message, exc_info=False)
    except Exception as e:
        error_message = f"Neizdevās iegūt AI atslēgvārdus (Vision): {e}"
        logger.error(error_message, exc_info=False)

    return labels_list if labels_list else None, error_message


def translate_labels(labels, target_language='lv'):
    """Tulko atslēgvārdu sarakstu uz norādīto mērķa valodu."""
    client = get_translation_client()
    if not client or not labels:
        return labels, "Translation API klients nav pieejams vai nav ko tulkot."

    translated_labels = []
    error_message = None
    try:
        logger.info(f"Tulkojam {len(labels)} atslēgvārdus uz '{target_language}'...")
        results = client.translate(labels, target_language=target_language)

        if isinstance(results, list):
            translated_labels = [item['translatedText'].lower() for item in results]
        elif isinstance(results, dict):
             translated_labels = [results['translatedText'].lower()]
        else:
            raise TypeError(f"Negaidīts tulkošanas rezultāta tips: {type(results)}")
        logger.info(f"Iztulkoti {len(translated_labels)} atslēgvārdi.")

    except google_exceptions.GoogleAPIError as e:
        error_message = f"Google API kļūda (Translate): {e}"
        logger.error(error_message, exc_info=False)
    except Exception as e:
        error_message = f"Neizdevās iztulkot atslēgvārdus: {e}"
        logger.error(error_message, exc_info=False)
        return labels, error_message

    return translated_labels, error_message
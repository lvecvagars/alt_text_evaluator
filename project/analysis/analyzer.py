import os
import logging
import re
import string
from urllib.parse import urlparse, urljoin
from flask import current_app

from ..core.spellchecker import initialize_phunspell, check_spelling_with_phunspell
from .providers import get_vision_api_labels, translate_labels

logger = logging.getLogger(__name__)

def compare_alt_with_labels(alt_text, labels_to_compare):
    """Salīdzina alt teksta vārdus ar padoto atslēgvārdu sarakstu."""
    if not alt_text or not labels_to_compare:
        return 0, len(labels_to_compare) if labels_to_compare else 0

    alt_words = set(re.findall(r'\b\w+\b', alt_text.lower(), re.UNICODE))
    labels_set = set(labels_to_compare)
    matches = alt_words.intersection(labels_set)
    matched_count = len(matches)
    total_labels = len(labels_set)

    logger.debug(f"Salīdzināšana: Alt={alt_words}, Labels={labels_set}, Sakritības={matches}")
    return matched_count, total_labels

def analyze_image_alt(img_tag, page_url, selected_language='lv'):
    """Analizē viena <img> taga ALT tekstu, ieskaitot AI un tulkošanu."""
    config = current_app.config
    enable_vision = config.get('ENABLE_VISION_API', False)
    enable_translation = config.get('ENABLE_TRANSLATION_API', False)
    target_translation_language = config.get('TARGET_TRANSLATION_LANGUAGE', 'lv')
    min_alt_len = config.get('USER_SPECIFIED_MIN_ALT_LENGTH', 5)
    max_alt_len = config.get('USER_SPECIFIED_MAX_ALT_LENGTH', 125)
    max_ai_labels = config.get('MAX_AI_LABELS_TO_SHOW', 5)
    forbidden_phrases = config.get('FORBIDDEN_PHRASES', {}).get(selected_language, [])

    current_pspell = initialize_phunspell(selected_language)
    raw_src = img_tag.get('src')
    alt = img_tag.get('alt')
    absolute_src = ''
    is_valid_for_vision = False

    if raw_src:
        try:
            absolute_src = urljoin(page_url, raw_src.strip())
            parsed_src = urlparse(absolute_src)
            is_valid_for_vision = parsed_src.scheme in ['http', 'https']
        except Exception as e:
            logger.warning(f"Neizdevās pārveidot src '{raw_src}' par URL: {e}")
            absolute_src = raw_src
    else:
        logger.debug("Attēlam nav 'src'.")

    analysis = {
        'exists': alt is not None, 'is_empty': None, 'is_too_long': None,
        'is_too_short': None, 'is_placeholder': None, 'is_filename': None,
        'has_spelling_issues': False, 'ai_analysis': None
    }
    suggestions = []

    if analysis['exists']:
        alt_text = alt.strip()
        analysis['is_empty'] = alt_text == ""

        if not analysis['is_empty']:
            if len(alt_text) > max_alt_len:
                analysis['is_too_long'] = True
                suggestions.append(f"ALT teksts > {max_alt_len} rakstzīmes.")
            elif len(alt_text) < min_alt_len:
                analysis['is_too_short'] = True
                suggestions.append(f"ALT teksts < {min_alt_len} rakstzīmes: '{alt_text}'.")

            lower_alt = alt_text.lower()
            for phrase in forbidden_phrases:
                phrase_lower = phrase.lower()
                if lower_alt.startswith(phrase_lower + ' ') or lower_alt == phrase_lower:
                    analysis['is_placeholder'] = True
                    suggestions.append(f"ALT teksts sākas ar vispārīgu frāzi: '{phrase}'.")
                    break

            if absolute_src and not analysis['is_placeholder']:
                try:
                    parsed_url = urlparse(absolute_src)
                    filename = os.path.basename(parsed_url.path)
                    if filename:
                        filename_no_ext = os.path.splitext(filename)[0]
                        alt_text_check = alt_text.strip(string.punctuation).lower()
                        fname_check = filename.lower()
                        fname_noext_check = filename_no_ext.lower()
                        is_exact_filename = (alt_text_check == fname_check or alt_text_check == fname_noext_check)
                        common_ext = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff', '.ico')
                        ends_with_ext = alt_text.lower().endswith(common_ext)
                        if is_exact_filename or (ends_with_ext and len(alt_text) < 80):
                            analysis['is_filename'] = True
                            suggestions.append("ALT teksts izskatās pēc faila nosaukuma.")
                except Exception as e:
                    logger.debug(f"Neizdevās pārbaudīt faila nosaukumu '{absolute_src}': {e}", exc_info=False)

            if current_pspell:
                try:
                    has_errors, spell_suggestions = check_spelling_with_phunspell(alt_text, current_pspell)
                    if has_errors:
                        analysis['has_spelling_issues'] = True
                        suggestions.extend(spell_suggestions)
                except Exception as e:
                    logger.error(f"Kļūda pareizrakstības pārbaudē: {e}", exc_info=False)
                    suggestions.append(f"Kļūda pareizrakstības pārbaudē ({selected_language}).")
            elif selected_language in config.get('SUPPORTED_LANGUAGES', {}):
                 logger.warning(f"Phunspell nav pieejams '{selected_language}'.")

            if enable_vision and is_valid_for_vision:
                original_ai_labels, vision_error = get_vision_api_labels(absolute_src)
                analysis['ai_analysis'] = {}

                if vision_error and not original_ai_labels:
                     analysis['ai_analysis']['error'] = f"Vision API: {vision_error}"
                     suggestions.append(f"AI attēla analīze neizdevās: {vision_error}")
                elif original_ai_labels:
                    analysis['ai_analysis']['original_labels'] = original_ai_labels[:max_ai_labels]
                    labels_to_compare = original_ai_labels
                    translation_error = None
                    analysis['ai_analysis']['used_language'] = 'en'
                    analysis['ai_analysis']['labels_for_display'] = original_ai_labels[:max_ai_labels] # Sākumā rādām oriģinālos

                    if enable_translation and target_translation_language != 'en':
                        translated_labels, translation_error = translate_labels(original_ai_labels, target_translation_language)
                        if translation_error:
                            suggestions.append(f"AI tulkošana neizdevās: {translation_error}")
                            analysis['ai_analysis']['translation_error'] = translation_error
                            # Salīdzināsim ar oriģinālajiem
                        elif translated_labels:
                            labels_to_compare = translated_labels # Salīdzināsim ar tulkotajiem
                            analysis['ai_analysis']['used_language'] = target_translation_language
                            analysis['ai_analysis']['translated_labels'] = translated_labels[:max_ai_labels]
                            analysis['ai_analysis']['labels_for_display'] = translated_labels[:max_ai_labels] # Rādām tulkotos


                    matched_count, total_labels = compare_alt_with_labels(alt_text, labels_to_compare)
                    analysis['ai_analysis']['matched_count'] = matched_count
                    analysis['ai_analysis']['total_compared_count'] = total_labels

                    lang_notice = f"({analysis['ai_analysis']['used_language'].upper()})"
                    suggestion_ai = f"AI atpazina {len(original_ai_labels)} vārdus. Salīdzināti {total_labels} {lang_notice}. "
                    suggestion_ai += f"Alt tekstā atrasti {matched_count} no tiem."
                    if total_labels > 0 and matched_count == 0:
                        suggestion_ai += " Apsveriet alt teksta papildināšanu."
                    suggestions.append(suggestion_ai)

                elif vision_error:
                    analysis['ai_analysis']['error'] = vision_error
                    suggestions.append(f"AI analīze: {vision_error}")

            elif enable_vision and not is_valid_for_vision:
                 suggestions.append("AI analīze nav iespējama šim attēla URL.")

        else:
            suggestions.append('ALT teksts ir tukšs (alt="").')

    else:
        suggestions.append("Trūkst 'alt' atribūta.")

    src_display = absolute_src if absolute_src else (raw_src if raw_src else "Nezināms SRC")

    return {
        'src': src_display,
        'alt': alt,
        'analysis': analysis,
        'suggestions': suggestions
    }
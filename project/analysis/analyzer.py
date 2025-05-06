import os
import logging
import re
import string
from urllib.parse import urlparse, urljoin
from flask import current_app

from .providers import get_vision_api_labels, translate_labels
from .word_normalization import compare_alt_with_labels

logger = logging.getLogger(__name__)

def is_svg_file(url):
    """Pārbauda vai URL norāda uz SVG failu."""
    if not url:
        return False
    try:
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        return path.endswith('.svg')
    except Exception as e:
        logger.debug(f"Kļūda URL pārbaudē: {e}")
        return False

def analyze_image_alt(img_tag, page_url, selected_language='lv'):
    """Analizē viena <img> taga ALT tekstu, ieskaitot AI un tulkošanu."""
    config = current_app.config
    enable_vision = config.get('ENABLE_VISION_API', False)
    enable_translation = config.get('ENABLE_TRANSLATION_API', False)
    # target_translation_language vairs tieši nenosaka salīdzināšanas valodu, to dara selected_language
    # Tomēr, ja selected_language = 'lv', tad mērķa tulkojums būs 'lv'.
    # TARGET_TRANSLATION_LANGUAGE varētu saglabāt, ja nākotnē būtu citi tulkošanas scenāriji.
    # Pašlaik to ignorēsim par labu selected_language vadītai loģikai.

    min_alt_len = config.get('USER_SPECIFIED_MIN_ALT_LENGTH', 5)
    max_alt_len = config.get('USER_SPECIFIED_MAX_ALT_LENGTH', 125)
    max_ai_labels_to_show = config.get('MAX_AI_LABELS_TO_SHOW', 5)
    forbidden_phrases = config.get('FORBIDDEN_PHRASES', {}).get(selected_language, [])

    raw_src = img_tag.get('src')
    
    if not raw_src or raw_src.strip() == '':
        logger.info("Attēls bez src atribūta izlaists")
        return None
        
    alt = img_tag.get('alt')
    absolute_src = ''
    is_valid_for_vision = False

    try:
        absolute_src = urljoin(page_url, raw_src.strip())
        
        if is_svg_file(absolute_src):
            logger.info(f"SVG fails izlaists: {absolute_src}")
            return None
            
        parsed_src = urlparse(absolute_src)
        is_valid_for_vision = parsed_src.scheme in ['http', 'https']
    except Exception as e:
        logger.warning(f"Neizdevās pārveidot src '{raw_src}' par URL: {e}")
        absolute_src = raw_src

    analysis = {
        'exists': alt is not None, 'is_empty': None, 'is_too_long': None,
        'is_too_short': None, 'is_placeholder': None, 'is_filename': None,
        'ai_analysis': None  # Inicializējam ai_analysis kā None
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
                        common_ext = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.ico')
                        ends_with_ext = alt_text.lower().endswith(common_ext)
                        if is_exact_filename or (ends_with_ext and len(alt_text) < 80):
                            analysis['is_filename'] = True
                            suggestions.append("ALT teksts izskatās pēc faila nosaukuma.")
                except Exception as e:
                    logger.debug(f"Neizdevās pārbaudīt faila nosaukumu '{absolute_src}': {e}", exc_info=False)

            # --- Sākums AI analīzes blokam ar labojumiem ---
            if enable_vision and is_valid_for_vision:
                analysis['ai_analysis'] = {} # Inicializējam šeit, jo AI analīze notiks
                original_ai_labels, vision_error = get_vision_api_labels(absolute_src) # Tie parasti ir 'en'

                if vision_error and not original_ai_labels:
                    analysis['ai_analysis']['error'] = f"Vision API: {vision_error}"
                    suggestions.append(f"AI attēla analīze neizdevās: {vision_error}")
                elif original_ai_labels:
                    analysis['ai_analysis']['original_labels'] = original_ai_labels[:max_ai_labels_to_show]

                    labels_for_comparison_input = original_ai_labels
                    language_for_normalization_and_comparison = 'en' # Noklusējums angļu valodai
                    labels_to_display_in_ui = original_ai_labels[:max_ai_labels_to_show]
                    
                    if selected_language == 'lv':
                        if enable_translation:
                            translated_lv_labels, translation_err_lv = translate_labels(original_ai_labels, 'lv')
                            if translation_err_lv:
                                suggestions.append(f"AI atslēgvārdu tulkošana uz LV neizdevās: {translation_err_lv}. Salīdzināšana notiks ar EN atslēgvārdiem, ALT teksts tiks normalizēts kā angļu valodā.")
                                analysis['ai_analysis']['translation_error'] = translation_err_lv
                                # Atkāpšanās: lieto oriģinālos EN atslēgvārdus un EN normalizāciju
                                labels_for_comparison_input = original_ai_labels
                                language_for_normalization_and_comparison = 'en'
                                labels_to_display_in_ui = original_ai_labels[:max_ai_labels_to_show]
                            elif translated_lv_labels:
                                labels_for_comparison_input = translated_lv_labels
                                language_for_normalization_and_comparison = 'lv'
                                analysis['ai_analysis']['translated_labels'] = translated_lv_labels[:max_ai_labels_to_show]
                                labels_to_display_in_ui = translated_lv_labels[:max_ai_labels_to_show]
                        else:
                            suggestions.append("AI atslēgvārdu tulkošana uz LV nav iespējota. Salīdzināšana notiks ar EN atslēgvārdiem, ALT teksts tiks normalizēts kā angļu valodā.")
                            labels_for_comparison_input = original_ai_labels
                            language_for_normalization_and_comparison = 'en'
                            labels_to_display_in_ui = original_ai_labels[:max_ai_labels_to_show]
                    
                    # Ja selected_language == 'en', noklusējuma vērtības jau ir pareizas

                    analysis['ai_analysis']['labels_for_display'] = labels_to_display_in_ui
                    analysis['ai_analysis']['used_language'] = language_for_normalization_and_comparison

                    matched_count, total_unique_normalized_ai_words = compare_alt_with_labels(
                        alt_text,
                        labels_for_comparison_input,
                        language=language_for_normalization_and_comparison
                    )
                    analysis['ai_analysis']['matched_count'] = matched_count
                    analysis['ai_analysis']['total_compared_count'] = total_unique_normalized_ai_words
                    
                    # Atjaunots ieteikuma ziņojums
                    suggestion_intro = f"AI atpazina {len(original_ai_labels)} oriģinālos (EN) atslēgvārdus. "
                    labels_lang_for_suggestion = language_for_normalization_and_comparison.upper()

                    if language_for_normalization_and_comparison == 'lv' and analysis['ai_analysis'].get('translated_labels'):
                        suggestion_intro += "Salīdzināšanai tika izmantoti tulkotie LV atslēgvārdi. "
                    elif language_for_normalization_and_comparison == 'en':
                        # Ja selected_language='lv' un notika atkāpšanās uz EN, ziņojums par to jau ir pievienots.
                        # Šeit vienkārši apstiprinām, ka EN tika izmantots.
                        if selected_language == 'lv' and not enable_translation: # Pārbaudām, vai tas bija atkāpšanās gadījums
                             pass # Ziņojums par EN lietošanu jau ir pievienots
                        elif selected_language == 'lv' and enable_translation and analysis['ai_analysis'].get('translation_error'):
                             pass # Ziņojums par EN lietošanu jau ir pievienots
                        else:
                             suggestion_intro += "Salīdzināšanai tika izmantoti oriģinālie EN atslēgvārdi. "


                    suggestion_match_info = f"Alt tekstā atrasta saderība ar {matched_count} no {total_unique_normalized_ai_words} unikāliem AI atslēgvārdiem ({labels_lang_for_suggestion}), kas tika izmantoti salīdzināšanai. "
                    suggestion_match_info += f"Lietotāja saskarnē tiek rādīti līdz {max_ai_labels_to_show} atslēgvārdiem."

                    suggestion_ai = suggestion_intro + suggestion_match_info
                    if total_unique_normalized_ai_words > 0 and matched_count == 0:
                        suggestion_ai += " Apsveriet alt teksta papildināšanu, lai tas labāk atbilstu attēla saturam."
                    suggestions.append(suggestion_ai)

                elif vision_error: # Ja original_ai_labels ir tukšs/None, bet ir vision_error (piem., "AI neatpazina...")
                    analysis['ai_analysis']['error'] = vision_error
                    suggestions.append(f"AI analīze: {vision_error}")
                # Ja original_ai_labels ir tukšs/None un nav vision_error, nekas netiks darīts AI blokā, kas ir pareizi.

            elif enable_vision and not is_valid_for_vision:
                 suggestions.append("AI analīze nav iespējama šim attēla URL.")
            # --- Beigas AI analīzes blokam ar labojumiem ---
        else: # alt_text ir tukšs
            suggestions.append('ALT teksts ir tukšs (alt="").')
    else: # Trūkst 'alt' atribūta
        suggestions.append("Trūkst 'alt' atribūta.")

    src_display = absolute_src if absolute_src else (raw_src if raw_src else "Nezināms SRC")

    return {
        'src': src_display,
        'alt': alt,
        'analysis': analysis,
        'suggestions': suggestions
    }
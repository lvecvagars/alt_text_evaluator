import os
import logging
import re
import string
from urllib.parse import urlparse, urljoin
from flask import current_app

from .providers import get_vision_api_labels, translate_labels
from .word_normalization import compare_alt_text_with_ai_phrases

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
    config = current_app.config
    enable_vision = config.get('ENABLE_VISION_API', False)
    enable_translation = config.get('ENABLE_TRANSLATION_API', False)
    min_alt_len = config.get('USER_SPECIFIED_MIN_ALT_LENGTH', 5)
    max_alt_len = config.get('USER_SPECIFIED_MAX_ALT_LENGTH', 125)
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
        'ai_analysis': None 
    }
    suggestions = []

    if analysis['exists']:
        alt_text = alt.strip()
        analysis['is_empty'] = alt_text == ""

        if not analysis['is_empty']:
            alt_len = len(alt_text)
            if alt_len > max_alt_len:
                analysis['is_too_long'] = True
                suggestions.append(
                    f"ALT teksts (garums: {alt_len}) pārsniedz ieteicamo {max_alt_len} rakstzīmju limitu. "
                    f"Apsveriet saīsināšanu."
                )
            elif alt_len < min_alt_len:
                analysis['is_too_short'] = True
                suggestions.append(
                    f"ALT teksts '{alt_text}' (garums: {alt_len}) ir īsāks par {min_alt_len} rakstzīmēm. "
                    f"Detalizētāks apraksts varētu būt noderīgāks."
                )

            lower_alt = alt_text.lower()
            for phrase in forbidden_phrases:
                phrase_lower = phrase.lower()
                if lower_alt.startswith(phrase_lower + ' ') or lower_alt == phrase_lower:
                    analysis['is_placeholder'] = True
                    suggestions.append(
                        f"ALT teksts sākas ar vai ir vispārīga frāze: '{phrase}'. "
                        f"Aizstājiet ar konkrētāku aprakstu."
                    )
                    break 

            if absolute_src and not analysis['is_placeholder']:
                try:
                    parsed_url = urlparse(absolute_src)
                    filename = os.path.basename(parsed_url.path)
                    if filename:
                        filename_no_ext = os.path.splitext(filename)[0]
                        alt_text_check = alt_text.strip(string.punctuation + ' ').lower()
                        fname_check = filename.lower()
                        fname_noext_check = filename_no_ext.lower()
                        common_ext = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.ico')
                        ends_with_common_ext = alt_text_check.endswith(common_ext)
                        is_exact_filename_match = (alt_text_check == fname_check or alt_text_check == fname_noext_check)
                        
                        if is_exact_filename_match or (ends_with_common_ext and len(alt_text_check) < 80):
                            analysis['is_filename'] = True
                            suggestions.append(
                                f"ALT teksts ('{alt_text}') varētu būt faila nosaukums. "
                                f"Faila nosaukumi parasti nav informatīvi. Aizstājiet ar satura aprakstu."
                            )
                except Exception as e:
                    logger.debug(f"Neizdevās pārbaudīt faila nosaukumu ALT tekstā '{absolute_src}': {e}", exc_info=False)

            if enable_vision and is_valid_for_vision:
                analysis['ai_analysis'] = {} 
                original_ai_labels, vision_error = get_vision_api_labels(absolute_src)

                if vision_error and not original_ai_labels:
                    if "AI neatpazina atslēgvārdus" in vision_error:
                        analysis['ai_analysis']['info'] = "MI neatpazina atslēgvārdus šim attēlam."
                    else:
                        analysis['ai_analysis']['error'] = f"MI attēla analīzes kļūda: {vision_error}."
                
                elif original_ai_labels: # original_ai_labels ir saraksts (var būt tukšs)
                    analysis['ai_analysis']['api_original_labels'] = original_ai_labels 

                    phrases_for_comparison = original_ai_labels
                    language_for_comparison = 'en' 
                    labels_to_display_in_ui = original_ai_labels 

                    if selected_language == 'lv':
                        if enable_translation:
                            translated_lv_phrases, translation_err_lv = translate_labels(original_ai_labels, 'lv')
                            if translation_err_lv:
                                analysis['ai_analysis']['translation_error'] = translation_err_lv
                            elif translated_lv_phrases: # Pārbaudām vai tulkošana bija veiksmīga
                                phrases_for_comparison = translated_lv_phrases
                                language_for_comparison = 'lv'
                                analysis['ai_analysis']['api_translated_labels'] = translated_lv_phrases
                                labels_to_display_in_ui = translated_lv_phrases
                        
                    analysis['ai_analysis']['labels_for_display'] = labels_to_display_in_ui
                    analysis['ai_analysis']['used_language_for_comparison'] = language_for_comparison.upper()

                    # Saņemam sakritības masku no compare_alt_text_with_ai_phrases
                    matched_phrase_count, total_input_phrases, matched_keyword_mask = compare_alt_text_with_ai_phrases(
                        alt_text,
                        phrases_for_comparison,
                        language=language_for_comparison
                    )
                    analysis['ai_analysis']['matched_phrase_count'] = matched_phrase_count
                    analysis['ai_analysis']['total_phrases_compared'] = total_input_phrases
                    analysis['ai_analysis']['matched_keyword_mask'] = matched_keyword_mask # Saglabājam masku

                    ai_suggestion_parts = []
                    if total_input_phrases > 0:
                        ai_suggestion_parts.append(
                            f"Jūsu ALT tekstam atbilst {matched_phrase_count} no {total_input_phrases} MI atpazītie atslēgvārdi."
                        )
                        if matched_phrase_count == 0:
                            ai_suggestion_parts.append("Apsveriet ALT teksta papildināšanu, lai tas labāk atbilstu attēla saturam.")
                        elif matched_phrase_count < total_input_phrases / 2 and matched_phrase_count > 0 :
                            ai_suggestion_parts.append("Lai gan ir dažas sakritības, ALT tekstu varētu uzlabot, lai tas precīzāk atspoguļotu attēla elementus.")
                    elif original_ai_labels: 
                         ai_suggestion_parts.append(
                            f"MI atpazina sākotnējos atslēgvārdus, bet pēc to apstrādes salīdzināšanai nekas nepalika."
                        )
                    
                    if selected_language == 'lv' and analysis['ai_analysis'].get('translation_error'):
                        ai_suggestion_parts.append(f"(Tulkošana uz LV neizdevās, salīdzināts ar EN frāzēm.)")
                    elif selected_language == 'lv' and not enable_translation and enable_vision:
                         ai_suggestion_parts.append(f"(Tulkošana uz LV nav aktivizēta, salīdzināts ar EN frāzēm.)")

                    if ai_suggestion_parts:
                        suggestions.append(" ".join(ai_suggestion_parts))
                
                elif not original_ai_labels and not vision_error and enable_vision: 
                    analysis['ai_analysis']['info'] = "MI neatpazina atslēgvārdus šim attēlam."


            elif enable_vision and not is_valid_for_vision:
                 if 'ai_analysis' not in analysis or analysis['ai_analysis'] is None: analysis['ai_analysis'] = {}
                 analysis['ai_analysis']['error'] = "MI attēla analīze nav iespējama šim URL (nav publiski pieejams vai neatbilstošs formāts)."

        else: 
            suggestions.append(
                'ALT teksts ir tukšs (alt=""). Pieņemami tikai tīri dekoratīviem attēliem. '
                'Ja attēls ir informatīvs, tam nepieciešams apraksts.'
            )
    else: 
        suggestions.append(
            "Attēlam trūkst obligātā 'alt' atribūta. Pievienojiet 'alt' ar aprakstu vai alt=\"\" dekoratīviem attēliem."
        )

    src_display = absolute_src if absolute_src else (raw_src if raw_src else "Nezināms SRC")

    return {
        'src': src_display,
        'alt': alt,
        'analysis': analysis,
        'suggestions': suggestions
    }
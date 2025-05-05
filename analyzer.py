import os
from urllib.parse import urlparse, urljoin
import logging
import string
import phunspell

from config import FORBIDDEN_PHRASES

logger = logging.getLogger(__name__)

USER_SPECIFIED_MAX_ALT_LENGTH = 125
USER_SPECIFIED_MIN_ALT_LENGTH = 5

pspell_objects = {}
initialized_languages = set()

SUPPORTED_LANGUAGES = {
    'lv': 'lv_LV',
    'en': 'en_US'
}

def initialize_phunspell(language_code='lv'):
    """Inicializē vai atgriež Phunspell objektu norādītajai valodai."""
    global pspell_objects, initialized_languages
    if language_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"Mēģinājums inicializēt neatbalstītu valodu: {language_code}")
        return None
    if language_code in pspell_objects:
        return pspell_objects[language_code]
    if language_code not in initialized_languages:
        initialized_languages.add(language_code)
        hunspell_code = SUPPORTED_LANGUAGES[language_code]
        try:
            ps = phunspell.Phunspell(hunspell_code)
            pspell_objects[language_code] = ps
            logger.info(f"Phunspell valodai '{language_code}' ({hunspell_code}) veiksmīgi inicializēts.")
            return ps
        except Exception as e:
            logger.error(f"Neizdevās inicializēt Phunspell valodai '{language_code}' ({hunspell_code}): {e}", exc_info=False)
            pspell_objects[language_code] = None
            return None
    else:
        return pspell_objects.get(language_code)

def is_likely_url_or_email(token):
    """Vienkārša pārbaude, vai tokens izskatās pēc URL vai e-pasta."""
    if '@' in token or '.' not in token:
       if '@' in token and '.' in token.split('@')[-1]: return True
       if '@' in token: return False
    if token.startswith(('http:', 'https:', 'www.')): return True
    return False

def check_spelling_with_phunspell(text, spellchecker):
    """Veic uzlabotu pareizrakstības pārbaudi."""
    if not spellchecker:
        return False, []

    errors_found = False
    suggestions_output = []
    checked_words_in_text = set()
    potential_words = text.split()

    for token in potential_words:
        cleaned_word = token.strip(string.punctuation + '“”’„–…')
        if not cleaned_word or cleaned_word.isdigit() or is_likely_url_or_email(cleaned_word):
            continue

        lower_word_for_tracking = cleaned_word.lower()
        if lower_word_for_tracking in checked_words_in_text:
            continue

        is_misspelled = False
        if not spellchecker.lookup(cleaned_word):
            if not spellchecker.lookup(cleaned_word.lower()):
                 if cleaned_word[0].isupper() and len(cleaned_word) > 1:
                     if not spellchecker.lookup(cleaned_word.capitalize()):
                          is_misspelled = True
                 elif not cleaned_word[0].isupper():
                     is_misspelled = True

        if is_misspelled:
            if '-' in cleaned_word and not spellchecker.lookup(cleaned_word):
                parts = cleaned_word.split('-')
                part_is_misspelled = False
                for part in parts:
                    if part and not part.isdigit():
                        if not spellchecker.lookup(part) and not spellchecker.lookup(part.lower()):
                             part_is_misspelled = True
                             break
                if not part_is_misspelled:
                     is_misspelled = False

        if is_misspelled:
            errors_found = True
            checked_words_in_text.add(lower_word_for_tracking)
            suggestions_generator = spellchecker.suggest(cleaned_word)
            suggestions_list = list(suggestions_generator)
            suggestion_text = f"Pareizrakstība: Iespējama kļūda vārdā '{cleaned_word}'."
            if suggestions_list:
                suggestion_text += f" Ieteikumi: {', '.join(suggestions_list[:3])}"
            suggestions_output.append(suggestion_text)

    return errors_found, suggestions_output

def analyze_image_alt(img_tag, page_url, selected_language='lv'):
    """Analizē viena <img> taga ALT tekstu, izmantojot izvēlēto valodu."""
    current_pspell = initialize_phunspell(selected_language)
    raw_src = img_tag.get('src')
    alt = img_tag.get('alt')

    absolute_src = ''
    if raw_src:
        try:
            absolute_src = urljoin(page_url, raw_src.strip())
        except Exception as e:
            logger.warning(f"Neizdevās pārveidot src '{raw_src}' par absolūtu URL lapā {page_url}: {e}")
            absolute_src = raw_src

    analysis = {
        'exists': alt is not None,
        'is_empty': None,
        'is_too_long': None,
        'is_too_short': None,
        'is_placeholder': None,
        'is_filename': None,
        'has_spelling_issues': False
    }
    suggestions = []

    if analysis['exists']:
        alt_text = alt.strip()
        analysis['is_empty'] = alt_text == ""

        if not analysis['is_empty']:
            if len(alt_text) > USER_SPECIFIED_MAX_ALT_LENGTH:
                analysis['is_too_long'] = True
                suggestions.append(f"ALT teksts ir pārāk garš (> {USER_SPECIFIED_MAX_ALT_LENGTH} rakstzīmes).")
            elif len(alt_text) < USER_SPECIFIED_MIN_ALT_LENGTH:
                analysis['is_too_short'] = True
                suggestions.append(f"ALT teksts ir ļoti īss (< {USER_SPECIFIED_MIN_ALT_LENGTH} rakstzīmes): '{alt_text}'.")

            phrases_to_check = FORBIDDEN_PHRASES.get(selected_language, [])
            lower_alt = alt_text.lower()
            for phrase in phrases_to_check:
                phrase_lower = phrase.lower()
                if lower_alt.startswith(phrase_lower + ' ') or lower_alt == phrase_lower:
                    analysis['is_placeholder'] = True
                    suggestions.append(f"ALT tekstam ({selected_language.upper()}) nav jāsākas vai jāsastāv tikai no vispārīgām frāzēm kā '{phrase}'.")
                    break

            if absolute_src and not analysis['is_placeholder']:
                try:
                    parsed_url = urlparse(absolute_src)
                    filename = os.path.basename(parsed_url.path)
                    if filename:
                        filename_no_ext = os.path.splitext(filename)[0]
                        is_exact_filename = (alt_text.lower() == filename.lower() or alt_text.lower() == filename_no_ext.lower())
                        common_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff')
                        ends_with_extension = alt_text.lower().endswith(common_extensions)

                        if is_exact_filename or (ends_with_extension and len(alt_text) < 80 and len(alt_text) > 4):
                            analysis['is_filename'] = True
                            if is_exact_filename:
                                suggestions.append("ALT teksts ir identisks faila nosaukumam.")
                            else:
                                suggestions.append("ALT teksts izskatās pēc faila nosaukuma (beidzas ar paplašinājumu).")
                except Exception as e:
                    logger.debug(f"Neizdevās pārbaudīt faila nosaukumu priekš src='{absolute_src}': {e}", exc_info=False)

            if current_pspell:
                try:
                    has_errors, spelling_suggestions = check_spelling_with_phunspell(alt_text, current_pspell)
                    if has_errors:
                        analysis['has_spelling_issues'] = True
                        suggestions.extend(spelling_suggestions)
                except Exception as e:
                    logger.error(f"Kļūda Phunspell pārbaudes laikā valodai '{selected_language}' tekstam '{alt_text[:50]}...': {e}", exc_info=False)
            elif selected_language in initialized_languages and not current_pspell:
                 logger.warning(f"Phunspell nav pieejams valodai '{selected_language}' (neizdevās inicializēt).")

        if analysis['is_empty']:
            suggestions.append('ALT teksts ir tukšs (alt=""). Pārliecinies, ka attēls ir tīri dekoratīvs.')

    else:
        suggestions.append("Trūkst 'alt' atribūta.")

    return {
        'src': absolute_src,
        'alt': alt,
        'analysis': analysis,
        'suggestions': suggestions
    }
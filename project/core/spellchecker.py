import logging
import phunspell
import re
from flask import current_app

logger = logging.getLogger(__name__)

pspell_objects = {}
initialized_languages = set()

def initialize_phunspell(language_code='lv'):
    """Inicializē vai atgriež Phunspell objektu norādītajai valodai."""
    global pspell_objects, initialized_languages
    supported_languages = current_app.config.get('SUPPORTED_LANGUAGES', {})

    if language_code not in supported_languages:
        logger.warning(f"Neatbalstīta valoda Phunspell: {language_code}")
        return None
    if language_code in pspell_objects:
        return pspell_objects[language_code]
    if language_code not in initialized_languages:
        initialized_languages.add(language_code)
        hunspell_code = supported_languages[language_code]
        try:
            ps = phunspell.Phunspell(hunspell_code)
            pspell_objects[language_code] = ps
            logger.info(f"Phunspell valodai '{language_code}' inicializēts.")
            return ps
        except Exception as e:
            logger.error(f"Neizdevās inicializēt Phunspell '{language_code}': {e}", exc_info=False)
            pspell_objects[language_code] = None
            return None
    else:
        return pspell_objects.get(language_code)

def is_likely_url_or_email(token):
    """Vienkārša pārbaude, vai tokens izskatās pēc URL vai e-pasta."""
    if '@' in token:
        if '.' in token.split('@')[-1]: return True
        return False
    if token.startswith(('http:', 'https:', 'www.')): return True
    parts = token.split('.')
    if len(parts) > 1 and len(parts[-1]) >= 2 and not parts[-1].isdigit(): return True
    return False

def check_spelling_with_phunspell(text, spellchecker):
    """Veic uzlabotu pareizrakstības pārbaudi, izmantojot Phunspell."""
    if not spellchecker:
        return False, []

    errors_found = False
    suggestions_output = []
    checked_words_in_text = set()
    potential_words = re.findall(r'\b[\w\'-]+\b', text, re.UNICODE)

    for token in potential_words:
        cleaned_word = token.strip("'")
        if not cleaned_word or cleaned_word.isdigit() or is_likely_url_or_email(cleaned_word):
            continue

        lower_word_for_tracking = cleaned_word.lower()
        if lower_word_for_tracking in checked_words_in_text:
            continue
        checked_words_in_text.add(lower_word_for_tracking)

        is_misspelled = False
        if not spellchecker.lookup(cleaned_word):
            if not spellchecker.lookup(cleaned_word.lower()):
                 if cleaned_word[0].isupper() and len(cleaned_word) > 1:
                     if not spellchecker.lookup(cleaned_word.capitalize()):
                          is_misspelled = True
                 elif not cleaned_word[0].isupper():
                     is_misspelled = True

        if is_misspelled and '-' in cleaned_word:
            parts = cleaned_word.split('-')
            all_parts_ok = True
            for part in parts:
                if part and not part.isdigit():
                    if not spellchecker.lookup(part) and not spellchecker.lookup(part.lower()):
                         all_parts_ok = False
                         break
            if all_parts_ok:
                 is_misspelled = False

        if is_misspelled:
            errors_found = True
            suggestions_list = list(spellchecker.suggest(cleaned_word))
            suggestions_to_show = suggestions_list[:3]
            suggestion_text = f"Pareizrakstība: Iespējama kļūda vārdā '{cleaned_word}'."
            if suggestions_to_show:
                suggestion_text += f" Ieteikumi: {', '.join(suggestions_to_show)}"
            suggestions_output.append(suggestion_text)

    return errors_found, suggestions_output
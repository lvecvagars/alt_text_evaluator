import re
import logging
from nltk.stem import SnowballStemmer
import simplemma
from LatvianStemmer import stem

logger = logging.getLogger(__name__)

snowball_stemmers = {}
try:
    snowball_stemmers['en'] = SnowballStemmer('english')
    logger.info("NLTK SnowballStemmer inicializēts angļu valodai")
except Exception as e:
    logger.warning(f"Nevarēja inicializēt SnowballStemmer: {e}")

def normalize_word(word, language='lv'):
    if not word:
        return word
        
    word = word.lower()
    
    if language == 'lv':
        try:
            return simplemma.lemmatize(word, lang='lv')
        except Exception as e:
            logger.debug(f"simplemma kļūda vārdam '{word}': {e}")
            
        try:
            return stem(word)
        except Exception as e:
            logger.debug(f"LatvianStemmer kļūda vārdam '{word}': {e}")
            
        return word
        
    elif language == 'en':
        if 'en' in snowball_stemmers:
            try:
                return snowball_stemmers['en'].stem(word)
            except Exception as e:
                logger.debug(f"SnowballStemmer kļūda vārdam '{word}': {e}")
        
        try:
            return simplemma.lemmatize(word, lang='en')
        except Exception as e:
            logger.debug(f"simplemma kļūda vārdam '{word}': {e}")
            
        return word
    
    else: 
        try:
            return simplemma.lemmatize(word, lang=language)
        except Exception as e:
            logger.debug(f"simplemma kļūda vārdam '{word}' valodai '{language}': {e}")
        return word

def tokenize_text(text):
    if not text:
        return []
    # Meklē burtu virknes, kas var ietvert iekšējas defises (piem., "self-propelled").
    words = re.findall(r'\b[a-zA-ZāčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ]+(?:-[a-zA-ZāčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ]+)*\b', text.lower(), re.UNICODE)
    return words

def compare_alt_text_with_ai_phrases(alt_text, ai_keyword_phrases, language='lv'):
    """
    Salīdzina ALT tekstu ar AI atslēgvārdu frāzēm.
    Frāze tiek uzskatīta par atbilstošu, ja visi tās normalizētie vārdi
    ir atrodami ALT teksta normalizētajos vārdos.
    """
    if not alt_text or not ai_keyword_phrases:
        return 0, len(ai_keyword_phrases) if ai_keyword_phrases else 0

    alt_words_tokenized = tokenize_text(alt_text)
    normalized_alt_words_set = {normalize_word(word, language) for word in alt_words_tokenized if word}

    if not normalized_alt_words_set:
        return 0, len(ai_keyword_phrases)

    matched_phrase_count = 0
    valid_phrase_count = 0 

    for phrase_text in ai_keyword_phrases:
        if not phrase_text or not phrase_text.strip():
            continue 
        
        valid_phrase_count += 1

        ai_phrase_tokenized_words = tokenize_text(phrase_text)
        if not ai_phrase_tokenized_words:
            continue

        current_ai_phrase_normalized_words = {normalize_word(word, language) for word in ai_phrase_tokenized_words if word}
        
        if not current_ai_phrase_normalized_words:
            continue

        if current_ai_phrase_normalized_words.issubset(normalized_alt_words_set):
            matched_phrase_count += 1
            
    final_total_phrases_to_compare_against = len(ai_keyword_phrases) # Kopējais skaits ir sākotnējais frāžu skaits sarakstā

    logger.debug(f"Frāžu salīdzināšana: Alt normalizētie vārdi='{normalized_alt_words_set}', "
                 f"AI frāzes='{ai_keyword_phrases}', Sakrita frāzes={matched_phrase_count}, Kopā AI frāzes={final_total_phrases_to_compare_against}")
    return matched_phrase_count, final_total_phrases_to_compare_against
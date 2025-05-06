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
            logger.debug(f"simplemma kļūda vārdam '{word}': {e}")
        return word

def tokenize_text(text):
    if not text:
        return []
    
    words = re.findall(r'\b[a-zA-ZāčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ]+\b', text.lower(), re.UNICODE)
    return words

def compare_alt_with_labels(alt_text, labels_to_compare, language='lv'):
    if not alt_text or not labels_to_compare:
        return 0, len(labels_to_compare) if labels_to_compare else 0
    
    alt_words = tokenize_text(alt_text)
    alt_normalized = {normalize_word(word, language) for word in alt_words if word}
    
    all_label_normalized = set()
    for label in labels_to_compare:
        label_words = tokenize_text(label)
        for word in label_words:
            if word:
                normalized = normalize_word(word, language)
                if normalized:
                    all_label_normalized.add(normalized)
    
    matches = alt_normalized.intersection(all_label_normalized)
    matched_count = len(matches)
    total_normalized = len(all_label_normalized)
    
    logger.debug(f"Salīdzināšana ar normalizāciju: Alt normalizēti={alt_normalized}, Label normalizēti={all_label_normalized}, Sakritības={matches}")
    return matched_count, total_normalized
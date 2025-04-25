# analyzer.py
import os
from urllib.parse import urlparse, urljoin
import logging # Lai varētu reģistrēt informāciju arī no šejienes

# Konstantes
MAX_ALT_LENGTH = 150
MIN_ALT_LENGTH_THRESHOLD = 5 # Piemērs īsam tekstam
FORBIDDEN_PHRASES = [
    "attēls par", "bilde par", "picture of", "image of", 
    "logo", "ikona", "grafiks", "diagramma", "foto" # Pielāgojams saraksts
] 

# Iegūstam logger instanci (tas pats, ko lieto Flask, ja konfigurēts)
logger = logging.getLogger(__name__)

def analyze_image_alt(img_tag, page_url):
    """
    Analizē viena <img> taga ALT tekstu.

    Argumenti:
        img_tag (bs4.element.Tag): BeautifulSoup objekts <img> tagam.
        page_url (str): Lapas URL, no kuras attēls iegūts (nepieciešams relatīvo URL pārveidošanai).

    Atgriež:
        dict: Vārdnīcu ar attēla 'src', 'alt', analīzes rezultātiem ('analysis') 
              un ieteikumiem ('suggestions').
    """
    raw_src = img_tag.get('src')
    alt = img_tag.get('alt') # Var būt None

    # Pārveidojam src par absolūtu URL
    if raw_src:
        absolute_src = urljoin(page_url, raw_src)
    else:
        absolute_src = '' # Tukšs src arī ir problēma

    analysis = {
        'exists': alt is not None,
        'is_empty': None,
        'is_too_long': None,
        'is_too_short': None,
        'is_placeholder': None,
        'is_filename': None,
        'is_link': img_tag.find_parent('a') is not None,
        'src_missing': not absolute_src # Pievienojam pārbaudi vai src nav tukšs
    }
    suggestions = []

    if not absolute_src:
         suggestions.append("Attēlam trūkst 'src' atribūta vai tas ir tukšs.")

    if analysis['exists']:
        alt_text = alt.strip()
        analysis['is_empty'] = alt_text == ""

        # 1. Garuma pārbaude
        if not analysis['is_empty']:
            if len(alt_text) > MAX_ALT_LENGTH:
                analysis['is_too_long'] = True
                suggestions.append(f"ALT teksts ir pārāk garš (vairāk nekā {MAX_ALT_LENGTH} rakstzīmes). Tam jābūt kodolīgam.")
            elif len(alt_text) < MIN_ALT_LENGTH_THRESHOLD:
                analysis['is_too_short'] = True
                suggestions.append(f"ALT teksts ir ļoti īss ('{alt_text}'). Pārliecinies, vai tas pietiekami apraksta attēlu.")

        # 2. Aizliegto frāžu pārbaude
        lower_alt = alt_text.lower()
        for phrase in FORBIDDEN_PHRASES:
            # Pārbaudam vai sākas ar frāzi VAI ir precīza frāze (piem., alt="logo")
            if lower_alt.startswith(phrase.lower() + ' ') or lower_alt == phrase.lower():
                analysis['is_placeholder'] = True
                suggestions.append(f"ALT tekstam nav jāsākas vai jāsastāv tikai no vispārīgām frāzēm kā '{phrase}'. Apraksti attēla saturu vai funkciju.")
                break 

        # 3. Faila nosaukuma pārbaude
        if absolute_src: # Pārbaudam tikai, ja ir src
            try:
                parsed_url = urlparse(absolute_src)
                filename = os.path.basename(parsed_url.path)
                # Vienkāršota pārbaude
                if filename and not analysis['is_empty'] and (alt_text.lower() == filename.lower() or alt_text.lower() == os.path.splitext(filename)[0].lower()):
                    analysis['is_filename'] = True
                    suggestions.append("ALT teksts izskatās pēc faila nosaukuma. Tam jāapraksta attēla saturs vai funkcija.")
            except Exception as e:
                logger.warning(f"Neizdevās pārbaudīt faila nosaukumu priekš src='{absolute_src}': {e}", exc_info=True)

        # 4. Tukša ALT teksta konteksts
        if analysis['is_empty']:
            # Papildus pārbaude dekoratīviem attēliem varētu būt šeit (ļoti sarežģīti!)
            suggestions.append('ALT teksts ir tukšs (alt=""). Pārliecinies, ka attēls ir tīri dekoratīvs. Ja tas sniedz informāciju vai ir saite, tam nepieciešams aprakstošs ALT teksts.')

        # 5. Saites konteksts
        if analysis['is_link'] and (analysis['is_empty'] or not analysis['exists']): # Pārbaudam arī ja neeksistē
             suggestions.append("Attēls ir saite, bet tam nav aprakstoša ALT teksta vai tas ir tukšs. ALT tekstam jāapraksta saites mērķis vai funkcija.")

    else: # Ja alt atribūts vispār nav
         suggestions.append("Attēlam trūkst 'alt' atribūta. Visiem informatīvajiem attēliem tas ir nepieciešams.")
         if analysis['is_link']:
             suggestions.append("Šis attēls ir arī saite, tādēļ ALT teksts ir īpaši svarīgs, lai aprakstītu saites mērķi.")


    return {
        'src': absolute_src,
        'alt': alt, # Saglabājam oriģinālo vērtību
        'analysis': analysis,
        'suggestions': suggestions
    }
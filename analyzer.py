# analyzer.py
import os
from urllib.parse import urlparse, urljoin
import logging 
# Importējam konfigurāciju
from config import MAX_ALT_LENGTH, MIN_ALT_LENGTH_THRESHOLD, FORBIDDEN_PHRASES

# Iegūstam logger instanci
logger = logging.getLogger(__name__)

def analyze_image_alt(img_tag, page_url):
    """
    Analizē viena <img> taga ALT tekstu.

    Argumenti:
        img_tag (bs4.element.Tag): BeautifulSoup objekts <img> tagam.
        page_url (str): Lapas URL, no kuras attēls iegūts.

    Atgriež:
        dict: Vārdnīcu ar attēla datiem, analīzi un ieteikumiem.
    """
    raw_src = img_tag.get('src')
    alt = img_tag.get('alt') 

    absolute_src = ''
    if raw_src:
        try:
            # Pārveidojam src par absolūtu URL, apstrādājot iespējamas kļūdas
            absolute_src = urljoin(page_url, raw_src.strip())
        except Exception as e:
            logger.warning(f"Neizdevās pārveidot src '{raw_src}' par absolūtu URL lapā {page_url}: {e}")
            absolute_src = raw_src # Atstājam oriģinālo, ja neizdodas pārveidot

    analysis = {
        'exists': alt is not None,
        'is_empty': None,
        'is_too_long': None,
        'is_too_short': None,
        'is_placeholder': None,
        'is_filename': None, # Šis tiks iestatīts zemāk
        'is_link': img_tag.find_parent('a') is not None,
        'src_missing': not raw_src 
    }
    suggestions = []

    if analysis['src_missing']:
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
            phrase_lower = phrase.lower()
            # Pārbaudam vai sākas ar frāzi + atstarpi VAI ir precīza frāze
            if lower_alt.startswith(phrase_lower + ' ') or lower_alt == phrase_lower:
                analysis['is_placeholder'] = True
                suggestions.append(f"ALT tekstam nav jāsākas vai jāsastāv tikai no vispārīgām frāzēm kā '{phrase}'. Apraksti attēla saturu vai funkciju.")
                break # Pietiek ar vienu atrasto

        # 3. Faila nosaukuma pārbaude (UZLABOTĀ VERSIJA)
        if absolute_src: # Pārbaudam tikai, ja ir src
            try:
                parsed_url = urlparse(absolute_src)
                filename = os.path.basename(parsed_url.path)
                if filename and not analysis['is_empty']:
                    # Saglabājam veco, precīzo pārbaudi
                    filename_no_ext = os.path.splitext(filename)[0]
                    is_exact_filename = (alt_text.lower() == filename.lower() or alt_text.lower() == filename_no_ext.lower())
                    
                    # Pievienojam jaunu, vienkāršāku pārbaudi - vai ALT beidzas ar tipisku attēla paplašinājumu?
                    common_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff')
                    # Pārbaudam vai beidzas ar kādu no paplašinājumiem (case-insensitive)
                    ends_with_extension = alt_text.lower().endswith(common_extensions)

                    # Atzīmējam kā problēmu, ja ir precīza sakritība VAI 
                    # ja beidzas ar paplašinājumu UN nav aizdomīgi garš (piem., < 80, lai neķertu teikumus, kas beidzas ar .jpg)
                    # UN nav tikai pats paplašinājums (piem., > 4 simboli)
                    # UN nav jau atzīmēts kā placeholder (lai nebūtu dubultu ziņojumu, ja alt="logo.png")
                    if is_exact_filename or (ends_with_extension and len(alt_text) < 80 and len(alt_text) > 4 and not analysis['is_placeholder']): 
                        analysis['is_filename'] = True
                        # Pielāgojam ziņojumu atkarībā no tā, vai bija precīza sakritība vai tikai paplašinājums
                        if is_exact_filename:
                            suggestions.append("ALT teksts ir identisks faila nosaukumam. Tam jāapraksta attēla saturs vai funkcija.")
                        else:
                            suggestions.append("ALT teksts beidzas ar attēla paplašinājumu un izskatās pēc faila nosaukuma. Tam jāapraksta attēla saturs vai funkcija.")
                            
            except Exception as e:
                # Samazinām loglevel šeit, jo tas var notikt bieži ar dīvainiem URL
                logger.debug(f"Neizdevās pārbaudīt faila nosaukumu priekš src='{absolute_src}': {e}", exc_info=False)


        # 4. Tukša ALT teksta konteksts
        if analysis['is_empty']:
            suggestions.append('ALT teksts ir tukšs (alt=""). Pārliecinies, ka attēls ir tīri dekoratīvs. Ja tas sniedz informāciju vai ir saite, tam nepieciešams aprakstošs ALT teksts.')
        
        # 5. Saites konteksts
        if analysis['is_link']:
             if analysis['is_empty']: # Ja ir saite un alt ir tukšs
                 suggestions.append("Attēls ir saite ar tukšu ALT tekstu (alt=\"\"). Tas apklusinās saiti ekrānlasītājiem. Ja saitei jābūt funkcionālai, ALT tekstam jāapraksta tās mērķis.")
             elif not analysis['exists']: # Ja ir saite un alt nav vispār
                 # Pārbaudam, vai vecākais 'a' tags nesatur tekstu
                 parent_link = img_tag.find_parent('a')
                 link_text = parent_link.get_text(strip=True) if parent_link else ''
                 if not link_text:
                    suggestions.append("Attēls ir vienīgais saturs saitē un tam trūkst ALT atribūta. ALT teksts ir obligāts, lai aprakstītu saites mērķi.")
                 else:
                    # Šis gadījums ir nedaudz diskutabls, bet labāk pievienot ieteikumu pārbaudīt
                    suggestions.append(f"Attēls ir saitē bez ALT atribūta, bet saitei ir teksts ('{link_text[:50]}...'). Ja attēls ir dekoratīvs šajā kontekstā, tam vajadzētu būt tukšam alt=\"\". Ja tas sniedz papildu informāciju, tam vajag ALT tekstu.")

    else: # Ja alt atribūts vispār nav
            suggestions.append("Attēlam trūkst 'alt' atribūta. Visiem informatīvajiem attēliem tas ir nepieciešams.")
            if analysis['is_link']:
                 parent_link = img_tag.find_parent('a')
                 link_text = parent_link.get_text(strip=True) if parent_link else ''
                 if not link_text:
                    # Atkārtojam ziņojumu no augšas skaidrības labad
                    suggestions.append("Šis attēls ir vienīgais saturs saitē, tādēļ ALT teksts ir obligāts, lai aprakstītu saites mērķi.")
                 else:
                    # Atkārtojam ziņojumu no augšas skaidrības labad
                     suggestions.append(f"Šis attēls ir saitē bez ALT atribūta, bet saitei ir teksts ('{link_text[:50]}...'). Ja attēls ir dekoratīvs šajā kontekstā, tam vajadzētu būt tukšam alt=\"\". Ja tas sniedz papildu informāciju, tam vajag ALT tekstu.")


    return {
        'src': absolute_src, # Atgriežam absolūto URL
        'alt': alt, 
        'analysis': analysis,
        'suggestions': suggestions
    }
import os
from urllib.parse import urlparse, urljoin
import logging
from config import FORBIDDEN_PHRASES # Izmantojam tikai šo no config

logger = logging.getLogger(__name__)

# Garuma konstantes atbilstoši lietotāja prasībām
USER_SPECIFIED_MAX_ALT_LENGTH = 125
USER_SPECIFIED_MIN_ALT_LENGTH = 5

def analyze_image_alt(img_tag, page_url):
    """
    Analizē viena <img> taga ALT tekstu atbilstoši pamata plānam.

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
    }
    suggestions = []

    if analysis['exists']:
        alt_text = alt.strip()
        analysis['is_empty'] = alt_text == ""

        if not analysis['is_empty']:
            # 1. Garuma pārbaude
            if len(alt_text) > USER_SPECIFIED_MAX_ALT_LENGTH:
                analysis['is_too_long'] = True
                suggestions.append(f"ALT teksts ir pārāk garš (vairāk nekā {USER_SPECIFIED_MAX_ALT_LENGTH} rakstzīmes).")
            elif len(alt_text) < USER_SPECIFIED_MIN_ALT_LENGTH:
                analysis['is_too_short'] = True
                suggestions.append(f"ALT teksts ir ļoti īss (mazāk nekā {USER_SPECIFIED_MIN_ALT_LENGTH} rakstzīmes, teksts: '{alt_text}').")

            # 2. Aizliegtās frāzes
            lower_alt = alt_text.lower()
            for phrase in FORBIDDEN_PHRASES:
                phrase_lower = phrase.lower()
                if lower_alt.startswith(phrase_lower + ' ') or lower_alt == phrase_lower:
                    analysis['is_placeholder'] = True
                    suggestions.append(f"ALT tekstam nav jāsākas vai jāsastāv tikai no vispārīgām frāzēm kā '{phrase}'.")
                    break

            # 3. Faila nosaukums
            if absolute_src:
                try:
                    parsed_url = urlparse(absolute_src)
                    filename = os.path.basename(parsed_url.path)
                    if filename:
                        filename_no_ext = os.path.splitext(filename)[0]
                        is_exact_filename = (alt_text.lower() == filename.lower() or alt_text.lower() == filename_no_ext.lower())
                        common_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff')
                        ends_with_extension = alt_text.lower().endswith(common_extensions)

                        # Pārbaude: vai ir precīzs nosaukums VAI beidzas ar paplašinājumu (ar papildu nosacījumiem)
                        if is_exact_filename or (ends_with_extension and len(alt_text) < 80 and len(alt_text) > 4 and not analysis['is_placeholder']):
                            analysis['is_filename'] = True
                            if is_exact_filename:
                                suggestions.append("ALT teksts ir identisks faila nosaukumam.")
                            else:
                                suggestions.append("ALT teksts izskatās pēc faila nosaukuma (beidzas ar paplašinājumu).")
                except Exception as e:
                    logger.debug(f"Neizdevās pārbaudīt faila nosaukumu priekš src='{absolute_src}': {e}", exc_info=False)

        # 4. Tukšs ALT teksts
        if analysis['is_empty']:
            suggestions.append('ALT teksts ir tukšs (alt=""). Pārliecinies, ka attēls ir tīri dekoratīvs.')

    else: # Ja alt atribūts vispār nav
        suggestions.append("Attēlam trūkst 'alt' atribūta.")

    return {
        'src': absolute_src,
        'alt': alt,
        'analysis': analysis,
        'suggestions': suggestions
    }
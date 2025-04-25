from flask import Flask, render_template, request
import requests 
from bs4 import BeautifulSoup 
import logging 
from urllib.parse import urlparse # Nepieciešams, lai pārbaudītu URL shēmu

# Importējam analīzes funkciju no mūsu moduļa
from analyzer import analyze_image_alt 

app = Flask(__name__)

# Konfigurējam vienkāršu kļūdu reģistrēšanu konsolē
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Samazinām bibliotēku 'requests' un 'urllib3' logošanas līmeni, lai nebūtu pārāk daudz ziņojumu
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


@app.route('/', methods=['GET', 'POST']) 
def index():
    results = None 
    error_message = None 
    submitted_url = "" # Saglabāsim ievadīto URL, lai to parādītu formā

    if request.method == 'POST':
        page_url = request.form.get('url', '').strip()
        submitted_url = page_url # Saglabājam atkārtotai attēlošanai

        if page_url:
            # Vienkārša URL validācija - jābūt http vai https
            parsed_uri = urlparse(page_url)
            if not parsed_uri.scheme in ['http', 'https']:
                 error_message = "Lūdzu, ievadiet derīgu URL adresi (jāsākas ar http:// vai https://)."
                 # Atgriežamies uz formu ar kļūdas ziņu
                 return render_template('index.html', results=None, error=error_message, submitted_url=submitted_url)

            app.logger.info(f"Saņemts pieprasījums analizēt URL: {page_url}")
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (compatible; AltTextEvaluatorBot/1.0)'} # Labāks User-Agent
                response = requests.get(page_url, headers=headers, timeout=15, allow_redirects=True) # Palielināts timeout, atļauti redirecti
                response.raise_for_status() 

                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    raise ValueError(f"Saturs nav HTML (Content-Type: {content_type})")

                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                app.logger.info(f"Atrasti {len(img_tags)} <img> tagi lapā {page_url}.")

                results = []
                for img in img_tags:
                    # Izsaucam analīzes funkciju no analyzer.py, padodot arī lapas URL relatīvo ceļu korektai apstrādei
                    image_analysis_data = analyze_image_alt(img, page_url) 
                    results.append(image_analysis_data)
                    app.logger.debug(f"Analizēts attēls: src='{image_analysis_data['src']}', alt='{image_analysis_data['alt']}', problēmas: {len(image_analysis_data['suggestions'])}")

            except requests.exceptions.Timeout:
                error_message = f"Vaicājums uz {page_url} pārsniedza laika limitu (timeout). Lapa varētu būt pārāk lēna vai nepieejama."
                app.logger.error(f"Timeout kļūda pieprasot {page_url}")
            except requests.exceptions.RequestException as e:
                error_message = f"Neizdevās ielādēt lapu {page_url}. Kļūda: {e}"
                app.logger.error(f"Tīkla kļūda pieprasot {page_url}: {e}", exc_info=True)
            except ValueError as e:
                error_message = f"Apstrādes kļūda: {e}"
                app.logger.error(f"Apstrādes kļūda URL {page_url}: {e}", exc_info=True)
            except Exception as e: 
                error_message = f"Radās neparedzēta kļūda apstrādājot {page_url}. Sīkāka informācija reģistrā."
                app.logger.exception(f"Neparedzēta kļūda apstrādājot {page_url}") # Reģistrē pilnu traceback

        else: # Ja URL lauks ir tukšs
             error_message = "Lūdzu, ievadiet URL adresi."

    # Attēlojam HTML lapu
    return render_template('index.html', results=results, error=error_message, submitted_url=submitted_url)

if __name__ == '__main__':
    # debug=False produkcijā, True - izstrādes laikā
    # host='0.0.0.0' ļauj piekļūt no tīkla (ja nepieciešams)
    app.run(debug=True, host='127.0.0.1')
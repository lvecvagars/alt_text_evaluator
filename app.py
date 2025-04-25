# app.py
from flask import Flask, render_template, request
import requests 
from bs4 import BeautifulSoup 
import logging 
from urllib.parse import urlparse 

# Importējam analīzes funkciju un konfigurāciju
from analyzer import analyze_image_alt 
from config import USER_AGENT, REQUEST_TIMEOUT

app = Flask(__name__)

# Detalizētāka logošanas konfigurācija
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

@app.route('/', methods=['GET', 'POST']) 
def index():
    results = None 
    error_message = None 
    submitted_url = "" 

    if request.method == 'POST':
        page_url = request.form.get('url', '').strip()
        submitted_url = page_url 

        if page_url:
            parsed_uri = urlparse(page_url)
            if not parsed_uri.scheme in ['http', 'https']:
                 error_message = "Lūdzu, ievadiet derīgu URL adresi (jāsākas ar http:// vai https://)."
                 app.logger.warning(f"Lietotājs ievadīja nederīgu URL shēmu: {page_url}")
                 return render_template('index.html', results=None, error=error_message, submitted_url=submitted_url)

            app.logger.info(f"Saņemts pieprasījums analizēt URL: {page_url}")
            try:
                headers = {'User-Agent': USER_AGENT} 
                response = requests.get(page_url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True) 

                response.raise_for_status() # Pārbauda 4xx, 5xx kļūdas

                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    error_message = f"Saņemtā satura tips nav HTML (Content-Type: {content_type}). Var analizēt tikai HTML lapas."
                    app.logger.warning(f"Nederīgs satura tips {content_type} no {page_url}")
                    raise ValueError(error_message) # Izmantojam ValueError, lai notvertu zemāk

                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                app.logger.info(f"Atrasti {len(img_tags)} <img> tagi lapā {page_url}.")

                results = []
                for img in img_tags:
                    image_analysis_data = analyze_image_alt(img, page_url) 
                    results.append(image_analysis_data)
                    # Šis logs ir pārāk detalizēts INFO līmenim
                    # app.logger.debug(f"Analizēts attēls: src='{image_analysis_data['src']}', alt='{image_analysis_data['alt']}', problēmas: {len(image_analysis_data['suggestions'])}")

            except requests.exceptions.Timeout:
                error_message = f"Vaicājums uz adresi pārsniedza laika limitu ({REQUEST_TIMEOUT}s). Lapa '{page_url}' varētu būt pārāk lēna vai nepieejama."
                app.logger.error(f"Timeout kļūda pieprasot {page_url}")
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code == 404:
                    error_message = f"Lapa '{page_url}' nav atrasta (Kļūda 404)."
                elif status_code == 403:
                    error_message = f"Piekļuve lapai '{page_url}' liegta (Kļūda 403). Serveris varētu bloķēt šādus pieprasījumus vai nepieciešama autorizācija."
                elif status_code == 401:
                     error_message = f"Nepieciešama autorizācija, lai piekļūtu '{page_url}' (Kļūda 401)."
                elif status_code == 429:
                     error_message = f"Pārāk daudz pieprasījumu uz '{page_url}' (Kļūda 429). Serveris ierobežo pieprasījumu skaitu."
                elif status_code >= 500:
                     error_message = f"Servera kļūda ({status_code}), mēģinot piekļūt '{page_url}'. Lapa varētu nedarboties."
                else:
                     error_message = f"HTTP kļūda {status_code}, mēģinot piekļūt '{page_url}'."
                app.logger.error(f"HTTP kļūda {status_code} pieprasot {page_url}: {e}")
            except requests.exceptions.ConnectionError:
                 server_host = urlparse(page_url).netloc
                 error_message = f"Neizdevās izveidot savienojumu ar serveri '{server_host}'. Pārbaudiet interneta savienojumu un vai adrese ir pareiza."
                 app.logger.error(f"Savienojuma kļūda pieprasot {page_url}")
            except requests.exceptions.InvalidURL:
                 error_message = f"Ievadītā adrese '{page_url}' nav derīgs URL."
                 app.logger.warning(f"Lietotājs ievadīja nederīgu URL formātu: {page_url}")
            except requests.exceptions.RequestException as e:
                error_message = f"Tīkla vai cita pieprasījuma kļūda, mēģinot piekļūt '{page_url}'. Kļūda: {e}"
                app.logger.error(f"Cita RequestException pieprasot {page_url}: {e}", exc_info=True)
            except ValueError as e: 
                error_message = str(e) 
                # Logger jau ir izsaukts vietā, kur kļūda radās
            except Exception as e: 
                error_message = f"Radās neparedzēta iekšēja kļūda apstrādājot '{page_url}'. Lūdzu, ziņojiet par šo problēmu."
                app.logger.exception(f"Neparedzēta kļūda apstrādājot {page_url}")

        else:
             # Ja URL nav ievadīts, bet metode ir POST (nevajadzētu notikt ar 'required' atribūtu, bet drošības pēc)
             if request.method == 'POST':
                  error_message = "Lūdzu, ievadiet URL adresi."

    # Attēlojam HTML lapu
    return render_template('index.html', results=results, error=error_message, submitted_url=submitted_url)

if __name__ == '__main__':
    # host='0.0.0.0' ļauj piekļūt no citiem datoriem tīklā (uzmanīgi ar drošību!)
    app.run(debug=True, host='127.0.0.1', port=5000) # Norādām arī portu skaidrības labad
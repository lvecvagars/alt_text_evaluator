from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urlparse

from analyzer import analyze_image_alt
from config import USER_AGENT, REQUEST_TIMEOUT

app = Flask(__name__)

# Pamata logošanas konfigurācija
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
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
            # Vienkārša URL validācija
            parsed_uri = urlparse(page_url)
            if not parsed_uri.scheme in ['http', 'https']:
                 error_message = "Lūdzu, ievadiet derīgu URL adresi (jāsākas ar http:// vai https://)."
                 app.logger.warning(f"Nederīga URL shēma: {page_url}")
                 return render_template('index.html', results=None, error=error_message, submitted_url=submitted_url)

            app.logger.info(f"Saņemts pieprasījums analizēt URL: {page_url}")
            try:
                headers = {'User-Agent': USER_AGENT}
                response = requests.get(page_url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                response.raise_for_status() # Pārbauda HTTP kļūdas (4xx, 5xx)

                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    error_message = f"Saņemtais saturs nav HTML (Content-Type: {content_type}). Var analizēt tikai HTML lapas."
                    app.logger.warning(f"Nederīgs satura tips {content_type} no {page_url}")
                    raise ValueError(error_message)

                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                app.logger.info(f"Atrasti {len(img_tags)} <img> tagi lapā {page_url}.")

                results = []
                for img in img_tags:
                    image_analysis_data = analyze_image_alt(img, page_url)
                    results.append(image_analysis_data)

            # Kļūdu apstrāde
            except requests.exceptions.Timeout:
                error_message = f"Vaicājums uz adresi pārsniedza laika limitu ({REQUEST_TIMEOUT}s)."
                app.logger.error(f"Timeout kļūda pieprasot {page_url}")
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                error_message = f"HTTP kļūda {status_code}, mēģinot piekļūt '{page_url}'."
                if status_code == 404: error_message = f"Lapa '{page_url}' nav atrasta (404)."
                elif status_code == 403: error_message = f"Piekļuve lapai '{page_url}' liegta (403)."
                app.logger.error(f"HTTP kļūda {status_code} pieprasot {page_url}: {e}")
            except requests.exceptions.ConnectionError:
                 server_host = urlparse(page_url).netloc
                 error_message = f"Neizdevās izveidot savienojumu ar serveri '{server_host}'."
                 app.logger.error(f"Savienojuma kļūda pieprasot {page_url}")
            except requests.exceptions.InvalidURL:
                 error_message = f"Ievadītā adrese '{page_url}' nav derīgs URL."
                 app.logger.warning(f"Nederīgs URL formāts: {page_url}")
            except requests.exceptions.RequestException as e:
                error_message = f"Tīkla vai cita pieprasījuma kļūda: {e}"
                app.logger.error(f"Cita RequestException pieprasot {page_url}: {e}", exc_info=True)
            except ValueError as e: # Piemēram, nepareizs content-type
                error_message = str(e)
            except Exception as e:
                error_message = "Radās neparedzēta iekšēja kļūda."
                app.logger.exception(f"Neparedzēta kļūda apstrādājot {page_url}")

        else:
             if request.method == 'POST':
                  error_message = "Lūdzu, ievadiet URL adresi."

    return render_template('index.html', results=results, error=error_message, submitted_url=submitted_url)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
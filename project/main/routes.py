import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import render_template, request, current_app

from . import main_bp
from ..analysis.analyzer import analyze_image_alt

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    results = None
    error_message = None
    submitted_url = ""
    selected_language = 'lv'

    config = current_app.config
    user_agent = config.get('USER_AGENT')
    request_timeout = config.get('REQUEST_TIMEOUT')

    if request.method == 'POST':
        page_url = request.form.get('url', '').strip()
        selected_language = request.form.get('language', 'lv')
        submitted_url = page_url

        if page_url:
            parsed_uri = urlparse(page_url)
            if not parsed_uri.scheme in ['http', 'https']:
                 error_message = "URL jāsākas ar http:// vai https://."
                 current_app.logger.warning(f"Nederīga URL shēma: {page_url}")
                 return render_template('index.html', results=None, error=error_message, submitted_url=submitted_url, selected_language=selected_language)

            current_app.logger.info(f"Analizējam URL: {page_url} valodai: {selected_language}")
            try:
                headers = {'User-Agent': user_agent}
                response = requests.get(page_url, headers=headers, timeout=request_timeout, allow_redirects=True)
                response.raise_for_status()

                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    error_message = f"Saturs nav HTML (Tips: {content_type})."
                    current_app.logger.warning(f"Nederīgs satura tips {content_type} no {page_url}")
                    return render_template('index.html', results=None, error=error_message, submitted_url=submitted_url, selected_language=selected_language)

                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                current_app.logger.info(f"Atrasti {len(img_tags)} <img> tagi.")

                results = []
                for img in img_tags:
                    image_analysis_data = analyze_image_alt(img, page_url, selected_language)
                    results.append(image_analysis_data)

            except requests.exceptions.Timeout:
                error_message = f"Vaicājuma laiks ({request_timeout}s) pārsniegts."
                current_app.logger.error(f"Timeout: {page_url}")
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 'N/A'
                error_message = f"HTTP kļūda {status_code} piekļūstot '{page_url}'."
                if status_code == 404: error_message = f"Lapa nav atrasta (404): '{page_url}'."
                elif status_code == 403: error_message = f"Piekļuve liegta (403): '{page_url}'."
                current_app.logger.error(f"HTTP kļūda {status_code}: {page_url}", exc_info=False)
            except requests.exceptions.ConnectionError:
                 server_host = urlparse(page_url).netloc or page_url
                 error_message = f"Neizdevās savienoties ar '{server_host}'."
                 current_app.logger.error(f"Savienojuma kļūda: {page_url}")
            except requests.exceptions.InvalidURL:
                 error_message = f"Nederīgs URL formāts: '{page_url}'."
                 current_app.logger.warning(f"Nederīgs URL: {page_url}")
            except requests.exceptions.RequestException as e:
                error_message = f"Tīkla pieprasījuma kļūda: {e}"
                current_app.logger.error(f"RequestException: {page_url}", exc_info=True)
            except Exception as e:
                error_message = "Radās neparedzēta iekšēja kļūda."
                current_app.logger.exception(f"Neparedzēta kļūda apstrādājot {page_url}")

        elif request.method == 'POST':
              error_message = "Lūdzu, ievadiet URL adresi."

    return render_template('index.html', results=results, error=error_message, submitted_url=submitted_url, selected_language=selected_language)
import os
from flask import Flask
import logging

def create_app(config_filename='config.py'):
    """Flask aplikācijas rūpnīca (factory)."""
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates',
                instance_relative_config=False)

    config_path = os.path.join(app.root_path, '..', config_filename)
    app.config.from_pyfile(config_path)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # Samazinām bibliotēku logu detalizāciju
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google.auth.transport.requests").setLevel(logging.WARNING)
    logging.getLogger("google.cloud.translate").setLevel(logging.WARNING)
    logging.getLogger("google.cloud.vision").setLevel(logging.WARNING)

    # Pārbaudām credentials pieejamību tikai informatīvi
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') and \
       (app.config.get('ENABLE_VISION_API') or app.config.get('ENABLE_TRANSLATION_API')):
        logging.warning("GOOGLE_APPLICATION_CREDENTIALS nav atrasts vides mainīgajos.")
    elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
         logging.info("GOOGLE_APPLICATION_CREDENTIALS atrasts vides mainīgajos.")

    with app.app_context():
        from .main import main_bp
        app.register_blueprint(main_bp)

        @app.context_processor
        def inject_config():
            # Padodam visu app.config uz veidnēm
            return dict(config=app.config)

    logging.info("Flask aplikācija izveidota.")
    return app
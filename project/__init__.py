import os
from flask import Flask
import logging

def create_app(config_filename='config.py'):
    """Flask aplikācijas rūpnīca (factory)."""
    app = Flask(__name__,
                static_folder='static',        # Norāda statisko failu mapi
                template_folder='templates',   # Norāda veidņu mapi
                instance_relative_config=False)

    # Pielāgojam ceļu, lai tas būtu relatīvs pret aplikācijas sakni, nevis __init__.py
    config_path = os.path.join(app.root_path, '..', config_filename)
    app.config.from_pyfile(config_path)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google.auth.transport.requests").setLevel(logging.WARNING)
    logging.getLogger("google.cloud.translate").setLevel(logging.WARNING)
    logging.getLogger("google.cloud.vision").setLevel(logging.WARNING)

    config_creds_path = app.config.get('GOOGLE_APPLICATION_CREDENTIALS')
    if config_creds_path and config_creds_path != '/path/to/your/keyfile.json' and not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        if os.path.exists(config_creds_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = config_creds_path
            logging.info(f"Credentials iestatītas no: {config_creds_path}")
        else:
            logging.error(f"Credentials fails NAV atrasts norādītajā vietā: {config_creds_path}")

    with app.app_context():
        from .main import main_bp
        app.register_blueprint(main_bp)

        @app.context_processor
        def inject_config():
            return dict(config=app.config)

    logging.info("Flask aplikācija izveidota.")
    return app
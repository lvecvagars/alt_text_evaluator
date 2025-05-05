from flask import Blueprint

main_bp = Blueprint(
    'main',
    __name__,
    template_folder='../templates', # Norāda uz veidņu mapi
    static_folder='../static',      # Norāda uz statisko failu mapi
    static_url_path='/project/static' # Pārliecinās par unikālu ceļu statiskajiem failiem
)

from . import routes
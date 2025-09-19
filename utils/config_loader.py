import json
import os
from functools import lru_cache
from flask import current_app


@lru_cache(maxsize=None)
def load_conexiones_config():
    """
    Loads the 'conexiones.json' file.
    The @lru_cache decorator ensures the file is read from disk only once.
    """
    json_path = os.path.join(current_app.root_path, 'conexiones.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(
            f"Critical error loading 'conexiones.json': {e}", exc_info=True)
        return {}


@lru_cache(maxsize=None)
def load_perfiles_config():
    """
    Loads the 'perfiles_propiedades.json' file.
    The @lru_cache decorator ensures the file is read from disk only once.
    """
    json_path = os.path.join(current_app.root_path,
                             'perfiles_propiedades.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(
            f"Critical error loading 'perfiles_propiedades.json': {e}", exc_info=True)
        return {}

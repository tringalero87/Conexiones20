import os
import json
from flask import current_app, g, session
from dal.sqlite_dal import SQLiteDAL


def get_catalogo_data(preselect_project_id):
    """
    Prepara los datos necesarios para la página del catálogo.
    """
    dal = SQLiteDAL()
    user_id = g.user['id']
    user_roles = session.get('user_roles', [])
    is_admin = 'ADMINISTRADOR' in user_roles

    try:
        json_path = os.path.join(current_app.root_path, 'conexiones.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(
            f"Error crítico al cargar 'conexiones.json': {e}", exc_info=True)
        raise ValueError(
            "Error crítico: No se pudo cargar la configuración de conexiones.")

    proyectos = dal.get_proyectos_for_user(user_id, is_admin)

    return {
        'estructura': estructura,
        'proyectos': proyectos,
        'preselect_project_id': preselect_project_id
    }


def search_conexiones(query):
    """
    Realiza una búsqueda de conexiones utilizando la capa DAL.
    """
    if not query:
        return []

    dal = SQLiteDAL()
    # La sanitización para FTS se hará en la DAL para mantener la lógica de BD encapsulada.
    return dal.search_conexiones_fts(query)

import os
import json
from flask import current_app, g, session
from sqlalchemy import text
from extensions import db
from models import Proyecto, Usuario

def get_catalogo_data(preselect_project_id):
    """Prepara los datos necesarios para la página del catálogo usando el ORM."""
    user_id = g.user.id
    is_admin = 'ADMINISTRADOR' in session.get('user_roles', [])

    try:
        json_path = os.path.join(current_app.root_path, 'conexiones.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(f"Error crítico al cargar 'conexiones.json': {e}", exc_info=True)
        estructura = {}

    if is_admin:
        proyectos = db.session.query(Proyecto).order_by(Proyecto.nombre).all()
    else:
        proyectos = db.session.query(Proyecto).join(Proyecto.usuarios_asignados).filter(Usuario.id == user_id).order_by(Proyecto.nombre).all()

    return {
        'estructura': estructura,
        'proyectos': proyectos,
        'preselect_project_id': preselect_project_id
    }

def search_conexiones(query):
    """Realiza una búsqueda de conexiones utilizando FTS5 con SQLAlchemy."""
    if not query:
        return []

    # FTS5 en SQLite es una característica especializada. Usar `text()` es la forma más directa.
    # Se podría crear una expresión de SQLA más compleja, pero esto es claro y efectivo.
    term = f'"{query.replace("\"", "\"\"")}"*'
    sql = text("""
        SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre
        FROM conexiones_fts fts
        JOIN conexiones c ON fts.rowid = c.id
        JOIN proyectos p ON c.proyecto_id = p.id
        LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
        WHERE fts.conexiones_fts MATCH :term
        ORDER BY c.fecha_creacion DESC
    """)

    result = db.session.execute(sql, {'term': term}).fetchall()
    return result

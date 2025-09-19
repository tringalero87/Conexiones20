import pandas as pd
import json
from extensions import db
from models import Proyecto, AliasPerfil, Conexion, HistorialEstado
from db import log_action
from flask import current_app
from services.connection_service import get_tipologia_config

def importar_conexiones_from_file(file, proyecto_id, user_id):
    """Gestiona la importación masiva de conexiones desde un archivo Excel usando el ORM."""
    proyecto = db.session.get(Proyecto, proyecto_id)
    if not proyecto:
        return 0, [], "El proyecto no existe."

    try:
        df = pd.read_excel(file, engine='openpyxl')
        # ... (La lógica de validación de columnas de pandas se mantiene)

        aliases = db.session.query(AliasPerfil).all()
        alias_map = {a.nombre_perfil: a.alias for a in aliases}

        existing_codes = {c.codigo_conexion for c in db.session.query(Conexion.codigo_conexion).all()}

        imported_count = 0
        error_rows = []

        for index, row in df.iterrows():
            try:
                # ... (La lógica de parsing de filas de pandas se mantiene)

                # Reemplazar las llamadas a la BD con el ORM
                tipologia_config = get_tipologia_config(tipo, subtipo, tipologia_nombre)
                # ...

                new_conexion = Conexion(
                    # ... (poblar el objeto Conexion)
                )
                db.session.add(new_conexion)
                db.session.flush() # Para obtener el ID de la nueva conexión

                new_historial = HistorialEstado(
                    conexion_id=new_conexion.id,
                    usuario_id=user_id,
                    estado='SOLICITADO'
                )
                db.session.add(new_historial)

                existing_codes.add(new_conexion.codigo_conexion)
                log_action('IMPORTAR_CONEXION', user_id, 'conexiones', new_conexion.id, f"Conexión '{new_conexion.codigo_conexion}' importada.")
                imported_count += 1

            except Exception as row_e:
                error_rows.append(f"Fila {index+2}: Error - {row_e}")

        db.session.commit()
        return imported_count, error_rows, None

    except Exception as e:
        db.session.rollback()
        return 0, [], f"Ocurrió un error inesperado: {e}"

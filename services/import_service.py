# This file will contain the business logic for importing connections.
import pandas as pd
import json
from db import get_db, log_action
from flask import current_app, g
from services.connection_service import get_tipologia_config

def importar_conexiones_from_file(file, proyecto_id, user_id):
    """
    Gestiona la importación masiva de conexiones desde un archivo Excel.
    """
    db = get_db()
    is_postgres = hasattr(db, 'cursor')
    placeholder = '%s' if is_postgres else '?'

    if is_postgres:
        with db.cursor() as cursor:
            cursor.execute(f'SELECT * FROM proyectos WHERE id = {placeholder}', (proyecto_id,))
            proyecto = cursor.fetchone()
    else:
        proyecto = db.execute(f'SELECT * FROM proyectos WHERE id = {placeholder}', (proyecto_id,)).fetchone()
    if not proyecto:
        return 0, [], "El proyecto no existe."

    try:
        df = pd.read_excel(file, engine='openpyxl')

        required_cols = ['TIPO', 'SUBTIPO', 'TIPOLOGIA', 'PERFIL1']
        df.columns = [col.upper().strip() for col in df.columns]
        if not all(col in df.columns for col in required_cols):
            return 0, [], 'El archivo Excel no contiene todas las columnas requeridas (TIPO, SUBTIPO, TIPOLOGIA, PERFIL1).'

        imported_count = 0
        error_rows = []

        if is_postgres:
            with db.cursor() as cursor:
                cursor.execute("SELECT alias, nombre_perfil FROM alias_perfiles ORDER BY nombre_perfil")
                aliases = cursor.fetchall()
                cursor.execute("SELECT codigo_conexion FROM conexiones")
                existing_codes = set(row['codigo_conexion'] for row in cursor.fetchall())
        else:
            aliases = db.execute("SELECT alias, nombre_perfil FROM alias_perfiles ORDER BY nombre_perfil").fetchall()
            existing_codes = set(row['codigo_conexion'] for row in db.execute("SELECT codigo_conexion FROM conexiones").fetchall())

        alias_map_by_fullname = {row['nombre_perfil']: row['alias'] for row in aliases}

        for index, row in df.iterrows():
            try:
                tipo = str(row.get('TIPO')).upper().strip()
                subtipo = str(row.get('SUBTIPO')).upper().strip()
                tipologia_nombre = str(row.get('TIPOLOGIA')).upper().strip()
                perfil1_input = str(row.get('PERFIL1')).strip()
                perfil2_input = str(row.get('PERFIL2')).strip() if 'PERFIL2' in df.columns else ''
                descripcion_input = str(row.get('DESCRIPCION')).strip() if 'DESCRIPCION' in df.columns else None
                if descripcion_input == 'nan': descripcion_input = None

                if not all([tipo, subtipo, tipologia_nombre, perfil1_input]):
                    error_rows.append(f"Fila {index+2}: Faltan datos obligatorios (Tipo, Subtipo, Tipología, Perfil1).")
                    continue

                tipologia_config = get_tipologia_config(tipo, subtipo, tipologia_nombre)
                if not tipologia_config:
                    error_rows.append(f"Fila {index+2}: Tipología '{tipologia_nombre}' no encontrada para Tipo '{tipo}' y Subtipo '{subtipo}'.")
                    continue

                num_perfiles_requeridos = tipologia_config.get('perfiles', 0)
                plantilla_codigo = tipologia_config.get('plantilla', '')

                perfiles_para_plantilla = {}
                perfiles_para_detalles = {}

                perfiles_para_detalles['Perfil 1'] = perfil1_input
                perfiles_para_plantilla['p1'] = alias_map_by_fullname.get(perfil1_input, perfil1_input)

                if num_perfiles_requeridos >= 2:
                    if not perfil2_input:
                        error_rows.append(f"Fila {index+2}: Se requiere Perfil 2 para esta tipología, pero no se proporcionó.")
                        continue
                    perfiles_para_detalles['Perfil 2'] = perfil2_input
                    perfiles_para_plantilla['p2'] = alias_map_by_fullname.get(perfil2_input, perfil2_input)

                if num_perfiles_requeridos >= 3:
                    perfil3_input = str(row.get('PERFIL3')).strip() if 'PERFIL3' in df.columns else ''
                    if not perfil3_input:
                        error_rows.append(f"Fila {index+2}: Se requiere Perfil 3 para esta tipología, pero no se proporcionó.")
                        continue
                    perfiles_para_detalles['Perfil 3'] = perfil3_input
                    perfiles_para_plantilla['p3'] = alias_map_by_fullname.get(perfil3_input, perfil3_input)

                codigo_conexion_base = plantilla_codigo.format(**perfiles_para_plantilla)

                contador = 1
                codigo_conexion_final = codigo_conexion_base
                while codigo_conexion_final in existing_codes:
                    contador += 1
                    codigo_conexion_final = f"{codigo_conexion_base}-{contador}"
                existing_codes.add(codigo_conexion_final)

                detalles_json = json.dumps(perfiles_para_detalles)

                sql_insert_conexion = f"INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, descripcion, detalles_json, solicitante_id) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}) RETURNING id"
                params_conexion = (codigo_conexion_final, proyecto_id, tipo, subtipo, tipologia_nombre, descripcion_input, detalles_json, user_id)

                sql_insert_historial = f"INSERT INTO historial_estados (conexion_id, usuario_id, estado) VALUES ({placeholder}, {placeholder}, {placeholder})"

                if is_postgres:
                    with db.cursor() as cursor:
                        cursor.execute(sql_insert_conexion, params_conexion)
                        new_conexion_id = cursor.fetchone()['id']
                        cursor.execute(sql_insert_historial, (new_conexion_id, user_id, 'SOLICITADO'))
                else:
                    cursor = db.execute(sql_insert_conexion.replace('%s', '?'), params_conexion)
                    new_conexion_id = cursor.lastrowid
                    db.execute(sql_insert_historial.replace('%s', '?'), (new_conexion_id, user_id, 'SOLICITADO'))
                db.commit()
                log_action('IMPORTAR_CONEXION', user_id, 'conexiones', new_conexion_id,
                           f"Conexión '{codigo_conexion_final}' importada en proyecto '{proyecto['nombre']}'.")
                imported_count += 1

            except Exception as row_e:
                db.rollback()
                error_rows.append(f"Fila {index+2}: Error al procesar - {row_e}")
                current_app.logger.error(f"Error al importar fila {index+2}: {row_e}")

        return imported_count, error_rows, None

    except pd.errors.EmptyDataError:
        return 0, [], 'El archivo Excel está vacío o no contiene datos válidos.'
    except pd.errors.ParserError as pe:
        return 0, [], f'Error al analizar el archivo Excel. Asegúrate de que el formato sea correcto. Detalle: {pe}'
    except Exception as e:
        current_app.logger.error(f"Ocurrió un error inesperado durante la importación: {e}")
        return 0, [], f"Ocurrió un error inesperado durante la importación: {e}"

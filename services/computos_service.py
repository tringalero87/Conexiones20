# This file will contain the business logic for calculating metric computations.
import json
from flask import g
from db import get_db, log_action
from utils.computos import calcular_peso_perfil

def get_computos_results(conexion):
    """
    Calculates and returns the metric computations for a connection based on saved data.
    """
    detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
    perfiles = [(key, value) for key, value in detalles.items() if key.startswith('Perfil')]

    resultados = []

    for i, (key, full_profile_name) in enumerate(perfiles):
        longitud_guardada_mm = detalles.get(f'Longitud {key} (mm)')
        if longitud_guardada_mm is not None:
            try:
                peso = calcular_peso_perfil(full_profile_name, float(longitud_guardada_mm))
                resultados.append({
                    'perfil': full_profile_name,
                    'longitud': float(longitud_guardada_mm),
                    'peso': peso
                })
            except (ValueError, TypeError):
                resultados.append({
                    'perfil': full_profile_name,
                    'longitud': longitud_guardada_mm,
                    'peso': 'Error'
                })
        else:
            resultados.append({
                'perfil': full_profile_name,
                'longitud': '', # Empty string for placeholder
                'peso': 'N/A'
            })
    return resultados, detalles

import sqlite3

def calculate_and_save_computos(conexion_id, form_data, user_id):
    """
    Calculates and saves the metric computations for a connection.
    """
    db = get_db()
    is_postgres = hasattr(db, 'cursor')
    placeholder = '%s' if is_postgres else '?'

    if is_postgres:
        with db.cursor() as cursor:
            cursor.execute(f'SELECT * FROM conexiones WHERE id = {placeholder}', (conexion_id,))
            conexion = cursor.fetchone()
    else:
        conexion = db.execute(f'SELECT * FROM conexiones WHERE id = {placeholder}', (conexion_id,)).fetchone()

    if not conexion:
        return None, "La conexión no existe.", None, None

    detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] and isinstance(conexion['detalles_json'], str) else conexion['detalles_json'] or {}
    perfiles = [(key, value) for key, value in detalles.items() if key.startswith('Perfil')]

    resultados = []
    updated_detalles = detalles.copy()
    has_error = False
    error_messages = []

    for i, (key, full_profile_name) in enumerate(perfiles):
        longitud_mm_str = form_data.get(f'longitud_{i+1}')

        if not longitud_mm_str:
            has_error = True
            error_messages.append(f"La longitud para {full_profile_name} ({key}) no puede estar vacía.")
            continue

        try:
            longitud_mm = float(longitud_mm_str)
            peso = calcular_peso_perfil(full_profile_name, longitud_mm)
            resultados.append({
                'perfil': full_profile_name,
                'longitud': longitud_mm,
                'peso': peso
            })
            updated_detalles[f'Longitud {key} (mm)'] = longitud_mm
        except ValueError:
            has_error = True
            error_messages.append(f"La longitud para {full_profile_name} ({key}) no es un número válido.")
            resultados.append({
                'perfil': full_profile_name,
                'longitud': longitud_mm_str,
                'peso': 'Error'
            })
        except Exception as e:
            has_error = True
            error_messages.append(f"Error al calcular peso para {full_profile_name} ({key}): {e}")
            resultados.append({
                'perfil': full_profile_name,
                'longitud': longitud_mm_str,
                'peso': 'Error'
            })

    if not has_error:
        sql = f'UPDATE conexiones SET detalles_json = {placeholder}, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = {placeholder}'
        params = (json.dumps(updated_detalles), conexion_id)
        if is_postgres:
            with db.cursor() as cursor:
                cursor.execute(sql, params)
        else:
            db.execute(sql, params)
        db.commit()
        log_action('CALCULAR_COMPUTOS', user_id, 'conexiones', conexion_id,
                   f"Cómputos métricos calculados y guardados para conexión '{conexion['codigo_conexion']}'.")
        return resultados, "Cómputos calculados y longitudes guardadas con éxito.", None, perfiles
    else:
        for i, (key, _) in enumerate(perfiles):
            updated_detalles[f'Longitud {key} (mm)'] = form_data.get(f'longitud_{i+1}')
        return resultados, None, error_messages, perfiles

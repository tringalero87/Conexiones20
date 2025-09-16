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

from flask import current_app
from services.connection_service import _get_placeholder, _is_testing

def calculate_and_save_computos(conexion_id, form_data, user_id):
    """
    Calculates and saves the metric computations for a connection.
    """
    db = get_db()
    p = _get_placeholder()
    cursor = db.cursor()

    try:
        cursor.execute(f'SELECT * FROM conexiones WHERE id = {p}', (conexion_id,))
        conexion = cursor.fetchone()

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
                resultados.append({'perfil': full_profile_name, 'longitud': longitud_mm, 'peso': peso})
                updated_detalles[f'Longitud {key} (mm)'] = longitud_mm
            except ValueError:
                has_error = True
                error_messages.append(f"La longitud para {full_profile_name} ({key}) no es un número válido.")
                resultados.append({'perfil': full_profile_name, 'longitud': longitud_mm_str, 'peso': 'Error'})
            except Exception as e:
                has_error = True
                error_messages.append(f"Error al calcular peso para {full_profile_name} ({key}): {e}")
                resultados.append({'perfil': full_profile_name, 'longitud': longitud_mm_str, 'peso': 'Error'})

        if not has_error:
            timestamp_expr = "CURRENT_TIMESTAMP" if not _is_testing() else "datetime('now')"
            sql = f'UPDATE conexiones SET detalles_json = {p}, fecha_modificacion = {timestamp_expr} WHERE id = {p}'
            params = (json.dumps(updated_detalles), conexion_id)
            cursor.execute(sql, params)
            db.commit()
            log_action('CALCULAR_COMPUTOS', user_id, 'conexiones', conexion_id, f"Cómputos métricos calculados para '{conexion['codigo_conexion']}'.")
            return resultados, "Cómputos calculados y guardados con éxito.", None, perfiles
        else:
            for i, (key, _) in enumerate(perfiles):
                updated_detalles[f'Longitud {key} (mm)'] = form_data.get(f'longitud_{i+1}')
            return resultados, None, error_messages, perfiles
    finally:
        cursor.close()

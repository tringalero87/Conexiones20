# Hepta_Conexiones/routes/api.py
"""
routes/api.py

Este archivo contiene todos los endpoints de la API de la aplicación.
Las APIs son rutas especiales que no devuelven una página HTML completa, sino
datos en formato JSON. Son utilizadas por el código JavaScript del frontend para
obtener información de forma dinámica sin tener que recargar la página.
"""

import json
import os
import re # Importar para normalización de texto
from flask import Blueprint, jsonify, request, g, current_app, session
from datetime import datetime # Importar datetime para posibles usos de CURRENT_TIMESTAMP si no es directo de SQLite

# Se importa el módulo de base de datos y el decorador de roles.
from db import get_db
from . import roles_required

# CORRECCIÓN DE MANTENIBILIDAD: Se importa la función centralizada desde el service correspondiente.
from services.connection_service import _notify_users, process_connection_state_transition

# Se define el Blueprint para agrupar todas las rutas de la API.
# El prefijo /api asegura que todas estas rutas comiencen con esa URL.
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/tipologias')
@roles_required('ADMINISTRADOR', 'SOLICITANTE', 'REALIZADOR')
def get_tipologias():
    """
    API endpoint para obtener las tipologías de conexión basadas en el tipo y subtipo.
    Es utilizado por el JavaScript de la página del catálogo para cargar dinámicamente
    las opciones de conexión.
    """
    tipo = request.args.get('tipo')
    subtipo = request.args.get('subtipo')

    if not tipo or not subtipo:
        # Si no se proporcionan los parámetros necesarios, devuelve una lista vacía.
        return jsonify([])

    json_path = os.path.join(current_app.root_path, 'conexiones.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
        
        # Se navega por la estructura del JSON para encontrar las tipologías correspondientes.
        tipologias = estructura[tipo]['subtipos'][subtipo]['tipologias']
        return jsonify(tipologias)
    except (KeyError, FileNotFoundError, json.JSONDecodeError) as e:
        # Si ocurre un error (ej. archivo no encontrado, clave incorrecta),
        # se registra el error y se devuelve una lista vacía para no bloquear el frontend.
        current_app.logger.error(f"API Error: No se pudieron obtener las tipologías para tipo='{tipo}', subtipo='{subtipo}'. Error: {e}")
        return jsonify([])

@api_bp.route('/perfiles')
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE')
def get_perfiles():
    """
    API endpoint para obtener los perfiles y sus propiedades para los cálculos
    de cómputos métricos.
    """
    json_path = os.path.join(current_app.root_path, 'perfiles_propiedades.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            perfiles = json.load(f)
        return jsonify(perfiles)
    except FileNotFoundError:
        current_app.logger.error("API Error: No se encontró 'perfiles_propiedades.json'.")
        return jsonify({"error": "Archivo de perfiles no encontrado"}), 404
    except json.JSONDecodeError:
        current_app.logger.error("API Error: Error de formato en 'perfiles_propiedades.json'.")
        return jsonify({"error": "Error al leer el archivo de perfiles"}), 500

@api_bp.route('/perfiles/buscar')
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE', 'APROBADOR')
def buscar_perfiles():
    """
    API endpoint para buscar perfiles por nombre o alias para la funcionalidad de autocompletado.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # Normalizar la consulta del usuario de la misma manera que se normalizará en la BD
    normalized_query = re.sub(r'[ -]', '', query).lower()
    db = get_db()
    
    resultados = []
    added_profiles = set()

    # 1. Buscar en alias_perfiles con normalización en la consulta SQL
    # Se usa REPLACE anidado para quitar espacios y guiones, y LOWER para ser case-insensitive.
    sql_query = """
        SELECT nombre_perfil, alias FROM alias_perfiles
        WHERE
            REPLACE(REPLACE(LOWER(nombre_perfil), ' ', ''), '-', '') LIKE ?
            OR
            REPLACE(REPLACE(LOWER(alias), ' ', ''), '-', '') LIKE ?
    """
    like_param = f'%{normalized_query}%'

    aliases = db.execute(sql_query, (like_param, like_param)).fetchall()
    
    for row in aliases:
        if row['nombre_perfil'] not in added_profiles:
            # Si el alias coincide, mostrarlo en la etiqueta para mayor claridad
            if row['alias'] and normalized_query in re.sub(r'[ -]', '', row['alias']).lower():
                 resultados.append({'label': f"{row['alias']} ({row['nombre_perfil']})", 'value': row['nombre_perfil']})
            else:
                 resultados.append({'label': row['nombre_perfil'], 'value': row['nombre_perfil']})
            added_profiles.add(row['nombre_perfil'])

    # 2. Buscar directamente en perfiles_propiedades.json (la lógica aquí se mantiene)
    json_path = os.path.join(current_app.root_path, 'perfiles_propiedades.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            perfiles_props = json.load(f)
        
        for nombre_perfil_key in perfiles_props.keys():
            if nombre_perfil_key not in added_profiles:
                normalized_key_for_search = re.sub(r'[ -]', '', nombre_perfil_key).lower()

                if normalized_query in normalized_key_for_search:
                    resultados.append({'label': nombre_perfil_key, 'value': nombre_perfil_key})
                    added_profiles.add(nombre_perfil_key)
    except (FileNotFoundError, json.JSONDecodeError):
        current_app.logger.error("API Error: No se pudo cargar 'perfiles_propiedades.json' para sugerencias.")

    # Limitar el número de resultados para no sobrecargar el frontend
    return jsonify(sorted(resultados, key=lambda x: x['label'])[:10])


@api_bp.route('/set-theme', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def set_theme():
    """
    API endpoint para guardar la preferencia de tema (claro/oscuro) del usuario
    en su sesión, permitiendo persistencia entre visitas.
    """
    data = request.get_json()
    if data and 'theme' in data:
        theme = data['theme']
        # Se valida que el tema sea uno de los valores permitidos para seguridad.
        if theme in ['light', 'dark']:
            session['theme'] = theme
            return jsonify({'success': True, 'message': f'Tema establecido a {theme}'})
    
    # Si los datos no son válidos, se devuelve un error.
    return jsonify({'success': False, 'message': 'Datos de tema inválidos'}), 400

@api_bp.route('/notificaciones/marcar-leidas', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def marcar_notificaciones_leidas():
    """
    Endpoint de API para marcar todas las notificaciones de un usuario como leídas.
    Se utiliza cuando el usuario hace clic en el ícono de la campana.
    """
    db = get_db()
    try:
        db.execute('UPDATE notificaciones SET leida = 1 WHERE usuario_id = ? AND leida = 0', (g.user['id'],))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"API Error: No se pudieron marcar las notificaciones como leídas para el usuario {g.user['id']}. Error: {e}")
        return jsonify({'success': False, 'message': 'Error en la base de datos'}), 500

# CORRECCIÓN DE MANTENIBILIDAD: Usar la función centralizada de cambio de estado
@api_bp.route('/conexiones/<int:conexion_id>/cambiar_estado_rapido', methods=['POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'APROBADOR')
def cambiar_estado_rapido(conexion_id):
    """
    Permite cambiar el estado de una conexión rápidamente vía AJAX.
    Ideal para acciones desde el dashboard.
    """
    db = get_db()

    # VERIFICACIÓN DE AUTORIZACIÓN: Asegurarse de que el usuario pertenece al proyecto de la conexión.
    conexion = db.execute('SELECT proyecto_id FROM conexiones WHERE id = ?', (conexion_id,)).fetchone()
    if not conexion:
        return jsonify({'success': False, 'message': 'La conexión no existe.'}), 404

    # Comprobar si el usuario es administrador, en cuyo caso tiene acceso a todo.
    if 'ADMINISTRADOR' not in session.get('user_roles', []):
        # Si no es admin, comprobar si está asignado al proyecto.
        acceso = db.execute('SELECT 1 FROM proyecto_usuarios WHERE proyecto_id = ? AND usuario_id = ?',
                              (conexion['proyecto_id'], g.user['id'])).fetchone()
        if not acceso:
            return jsonify({'success': False, 'message': 'No tienes permiso para acceder a esta conexión.'}), 403

    data = request.get_json()
    nuevo_estado = data.get('estado')
    detalles = data.get('detalles', '') # Para el motivo de rechazo

    success, message, _ = process_connection_state_transition(
        db, conexion_id, nuevo_estado, g.user['id'], g.user['nombre_completo'], session.get('user_roles', []), detalles
    )

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        # Asegurarse de que el status code sea 400 o 403 si hay un error de negocio
        status_code = 400 if "Debes proporcionar un motivo" in message else 403
        return jsonify({'success': False, 'message': message}), status_code


# NUEVO ENDPOINT: Guardar preferencias de personalización del dashboard
@api_bp.route('/dashboard/save_preferences', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def save_dashboard_preferences():
    """
    Guarda las preferencias de personalización del dashboard del usuario.
    """
    db = get_db()
    data = request.get_json()
    widgets_config = json.dumps(data.get('widgets_config', {}))
    
    try:
        # Usa INSERT OR REPLACE para actualizar si ya existe o insertar si no.
        db.execute(
            'INSERT OR REPLACE INTO user_dashboard_preferences (usuario_id, widgets_config) VALUES (?, ?)',
            (g.user['id'], widgets_config)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Preferencias del dashboard guardadas con éxito.'})
    except Exception as e:
        current_app.logger.error(f"Error al guardar preferencias de dashboard para usuario {g.user['id']}: {e}")
        return jsonify({'success': False, 'message': 'Error al guardar preferencias del dashboard.'}), 500
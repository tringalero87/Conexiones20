import json
import os
import re
from flask import Blueprint, jsonify, request, g, current_app, session
from datetime import datetime
from db import get_db
from . import roles_required
from services.connection_service import process_connection_state_transition

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/tipologias')
@roles_required('ADMINISTRADOR', 'SOLICITANTE', 'REALIZADOR')
def get_tipologias():
    tipo = request.args.get('tipo')
    subtipo = request.args.get('subtipo')

    if not tipo or not subtipo:
        return jsonify([])

    json_path = os.path.join(current_app.root_path, 'conexiones.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
        
        tipologias = estructura.get(tipo, {}).get('subtipos', {}).get(subtipo, {}).get('tipologias', [])
        return jsonify(tipologias)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(f"API Error: No se pudieron obtener las tipologías para tipo='{tipo}', subtipo='{subtipo}'. Error: {e}")
        return jsonify([])

@api_bp.route('/perfiles')
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE')
def get_perfiles():
    json_path = os.path.join(current_app.root_path, 'perfiles_propiedades.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            perfiles = json.load(f)
        return jsonify(perfiles)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Archivo de perfiles no encontrado"}), 404
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Error al leer el archivo de perfiles"}), 500

@api_bp.route('/perfiles/buscar')
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE', 'APROBADOR')
def buscar_perfiles():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    normalized_query = re.sub(r'[ -]', '', query).lower()
    db = get_db()
    cursor = db.cursor()
    
    resultados = []
    added_profiles = set()

    # La función REPLACE es compatible con SQLite y PostgreSQL
    sql_query = """
        SELECT nombre_perfil, alias FROM alias_perfiles
        WHERE
            REPLACE(REPLACE(LOWER(nombre_perfil), ' ', ''), '-', '') LIKE %s
            OR
            REPLACE(REPLACE(LOWER(alias), ' ', ''), '-', '') LIKE %s
    """
    like_param = f'%{normalized_query}%'

    cursor.execute(sql_query, (like_param, like_param))
    aliases = cursor.fetchall()
    cursor.close()
    
    for row in aliases:
        if row['nombre_perfil'] not in added_profiles:
            if row['alias'] and normalized_query in re.sub(r'[ -]', '', row['alias']).lower():
                 resultados.append({'label': f"{row['alias']} ({row['nombre_perfil']})", 'value': row['nombre_perfil']})
            else:
                 resultados.append({'label': row['nombre_perfil'], 'value': row['nombre_perfil']})
            added_profiles.add(row['nombre_perfil'])

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

    return jsonify(sorted(resultados, key=lambda x: x['label'])[:10])

@api_bp.route('/set-theme', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def set_theme():
    data = request.get_json()
    if data and 'theme' in data and data['theme'] in ['light', 'dark']:
        session['theme'] = data['theme']
        return jsonify({'success': True, 'message': f'Tema establecido a {data["theme"]}'})
    
    return jsonify({'success': False, 'error': 'Datos de tema inválidos'}), 400

@api_bp.route('/notificaciones/marcar-leidas', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def marcar_notificaciones_leidas():
    db = get_db()
    sql = 'UPDATE notificaciones SET leida = 1 WHERE usuario_id = %s AND leida = 0'
    cursor = db.cursor()
    try:
        cursor.execute(sql, (g.user['id'],))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"API Error: No se pudieron marcar las notificaciones como leídas para el usuario {g.user['id']}. Error: {e}")
        return jsonify({'success': False, 'error': 'Error en la base de datos'}), 500
    finally:
        cursor.close()

@api_bp.route('/dashboard/project-details')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def get_project_details_for_chart():
    proyecto_id = request.args.get('proyecto_id', type=int)
    estado = request.args.get('estado')

    if not proyecto_id or not estado:
        return jsonify({'error': 'Parámetros incompletos'}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        sql = "SELECT id, codigo_conexion, fecha_creacion FROM conexiones WHERE proyecto_id = %s AND estado = %s ORDER BY fecha_creacion DESC"
        cursor.execute(sql, (proyecto_id, estado))
        conexiones = cursor.fetchall()

        # Convertir a una lista de diccionarios para JSON
        results = [dict(row) for row in conexiones]
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error al obtener detalles del proyecto para el gráfico: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500
    finally:
        cursor.close()

@api_bp.route('/conexiones/<int:conexion_id>/cambiar_estado_rapido', methods=['POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'APROBADOR')
def cambiar_estado_rapido(conexion_id):
    db = get_db()
    cursor = db.cursor()

    try:
        conexion_sql = "SELECT proyecto_id FROM conexiones WHERE id = %s"
        cursor.execute(conexion_sql, (conexion_id,))
        conexion = cursor.fetchone()
        if not conexion:
            return jsonify({'success': False, 'error': 'La conexión no existe.'}), 404

        if 'ADMINISTRADOR' not in session.get('user_roles', []):
            acceso_sql = "SELECT 1 FROM proyecto_usuarios WHERE proyecto_id = %s AND usuario_id = %s"
            cursor.execute(acceso_sql, (conexion['proyecto_id'], g.user['id']))
            acceso = cursor.fetchone()
            if not acceso:
                return jsonify({'success': False, 'error': 'No tienes permiso para acceder a esta conexión.'}), 403

        data = request.get_json()
        nuevo_estado = data.get('estado')
        detalles = data.get('detalles', '')

        success, message, _ = process_connection_state_transition(
            db, conexion_id, nuevo_estado, g.user['id'], g.user['nombre_completo'], session.get('user_roles', []), detalles
        )

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            status_code = 400 if "Debes proporcionar un motivo" in message else 403
            return jsonify({'success': False, 'error': message}), status_code
    finally:
        cursor.close()

@api_bp.route('/dashboard/save_preferences', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def save_dashboard_preferences():
    db = get_db()
    data = request.get_json()
    widgets_config = json.dumps(data.get('widgets_config', {}))
    
    sql = "INSERT INTO user_dashboard_preferences (usuario_id, widgets_config) VALUES (%s, %s) ON CONFLICT (usuario_id) DO UPDATE SET widgets_config = EXCLUDED.widgets_config"

    cursor = db.cursor()
    try:
        cursor.execute(sql, (g.user['id'], widgets_config))
        db.commit()
        return jsonify({'success': True, 'message': 'Preferencias del dashboard guardadas con éxito.'})
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error al guardar preferencias de dashboard para usuario {g.user['id']}: {e}")
        return jsonify({'success': False, 'error': 'Error al guardar preferencias del dashboard.'}), 500
    finally:
        cursor.close()
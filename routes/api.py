import json
import re
from flask import Blueprint, jsonify, request, g, session
from extensions import db
from models import Notificacion, UserDashboardPreference, Conexion, AliasPerfil
from . import roles_required
import services.connection_service as cs
from utils.config_loader import load_conexiones_config, load_perfiles_config
from sqlalchemy import text

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/tipologias')
@roles_required('ADMINISTRADOR', 'SOLICITANTE', 'REALIZADOR')
def get_tipologias():
    # This route does not use the database and remains the same
    tipo = request.args.get('tipo')
    subtipo = request.args.get('subtipo')
    if not tipo or not subtipo:
        return jsonify([])
    estructura = load_conexiones_config()
    if not estructura:
        return jsonify([])
    tipologias = estructura.get(tipo, {}).get('subtipos', {}).get(subtipo, {}).get('tipologias', [])
    return jsonify(tipologias)

@api_bp.route('/perfiles/buscar')
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE', 'APROBADOR')
def buscar_perfiles():
    """Busca perfiles usando FTS con el ORM, con tokenización mejorada."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # Limpia y tokeniza el término de búsqueda para FTS5
    processed_query = re.sub(r'([A-Za-z])(\d)', r'\1 \2', query)
    cleaned_query = processed_query.replace("-", " ").replace("_", " ").replace("\"", "\"\"")
    tokens = [f'"{token}"*' for token in cleaned_query.split() if token]
    term = " AND ".join(tokens)

    if not term:
        return jsonify([])

    sql = text("SELECT ap.nombre_perfil, ap.alias FROM alias_perfiles_fts fts JOIN alias_perfiles ap ON fts.rowid = ap.id WHERE fts.alias_perfiles_fts MATCH :term")
    results = db.session.execute(sql, {'term': term}).fetchall()

    profiles = [{'label': f"{row.alias} ({row.nombre_perfil})" if row.alias else row.nombre_perfil, 'value': row.nombre_perfil} for row in results]
    return jsonify(sorted(profiles, key=lambda x: x['label'])[:10])

@api_bp.route('/notificaciones/marcar-leidas', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def marcar_notificaciones_leidas():
    """Marca las notificaciones como leídas usando el ORM."""
    try:
        Notificacion.query.filter_by(usuario_id=g.user.id, leida=False).update({'leida': True})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"API Error al marcar notificaciones: {e}")
        return jsonify({'success': False, 'error': 'Error en la base de datos'}), 500

@api_bp.route('/conexiones/<int:conexion_id>/cambiar_estado_rapido', methods=['POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'APROBADOR')
def cambiar_estado_rapido(conexion_id):
    """Cambia el estado de una conexión a través de la API, usando los servicios refactorizados."""
    conexion = db.session.get(Conexion, conexion_id)
    if not conexion:
        return jsonify({'success': False, 'error': 'La conexión no existe.'}), 404

    # Simplified permission check
    if 'ADMINISTRADOR' not in session.get('user_roles', []) and not any(g.user.id == u.id for u in conexion.proyecto.usuarios_asignados):
        return jsonify({'success': False, 'error': 'No tienes permiso para acceder a esta conexión.'}), 403

    data = request.get_json()
    success, message, _ = cs.process_connection_state_transition(
        conexion_id, data.get('estado'), g.user.id, g.user.nombre_completo, session.get('user_roles', []), data.get('detalles', '')
    )
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400

# ... (other API routes refactored similarly) ...

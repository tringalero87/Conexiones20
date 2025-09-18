import os
import json
import threading
from flask import current_app, render_template, url_for, g
from flask_mail import Message
from extensions import mail
from db import get_db, log_action

def get_tipologia_config(tipo, subtipo, tipologia_nombre):
    """Función auxiliar para obtener la configuración de una tipología desde conexiones.json."""
    json_path = os.path.join(current_app.root_path, 'conexiones.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
        if tipo in estructura and subtipo in estructura[tipo]['subtipos']:
            tipologia_obj_list = estructura[tipo]['subtipos'][subtipo]['tipologias']
            return next((t for t in tipologia_obj_list if t['nombre'] == tipologia_nombre), None)
        return None
    except (KeyError, StopIteration, FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(f"Error al cargar configuración de tipología: {e}")
        return None

def _get_conexion(conexion_id):
    """
    Función auxiliar para obtener una conexión y sus datos asociados desde la base de datos.
    Lanza un error 404 si la conexión no se encuentra.
    """
    db = get_db()
    cursor = db.cursor()

    try:
        conexion_query = """
            SELECT c.*, p.nombre as proyecto_nombre,
                   sol.nombre_completo as solicitante_nombre,
                   real.nombre_completo as realizador_nombre,
                   aprob.nombre_completo as aprobador_nombre
            FROM conexiones c
            JOIN proyectos p ON c.proyecto_id = p.id
            LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
            LEFT JOIN usuarios real ON c.realizador_id = real.id
            LEFT JOIN usuarios aprob ON c.aprobador_id = aprob.id
            WHERE c.id = ?
        """
        cursor.execute(conexion_query, (conexion_id,))
        conexion = cursor.fetchone()
    finally:
        cursor.close()

    if conexion is None:
        from flask import abort
        abort(404, f"La conexión con id {conexion_id} no existe.")
    return dict(conexion)

def _send_email_notification(recipients, subject, template, **kwargs):
    """
    Función auxiliar para enviar notificaciones por correo electrónico de forma asíncrona.
    """
    if not recipients:
        return

    if not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.warning("Configuración de correo electrónico no completa. No se enviará email.")
        return

    msg = Message(subject, recipients=recipients)
    msg.html = render_template(template, **kwargs)

    def send_async_email(app, msg_obj):
        with app.app_context():
            try:
                mail.send(msg_obj)
                app.logger.info(f"Correo enviado a {', '.join(msg_obj.recipients)} con asunto: {msg_obj.subject}")
            except Exception as e:
                app.logger.error(f"Error al enviar correo electrónico a {msg_obj.recipients}: {e}", exc_info=True)

    thr = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
    thr.start()

def _notify_users(db, conexion_id, message, url_suffix, roles_to_notify):
    """Crea notificaciones y envía correos electrónicos a usuarios con roles específicos."""
    conexion = _get_conexion(conexion_id)

    placeholders = ', '.join(['?'] * len(roles_to_notify))
    params = [conexion['proyecto_id']] + roles_to_notify

    query = f"""
        SELECT DISTINCT u.id, u.email, u.nombre_completo, COALESCE(pn.email_notif_estado, 1) as email_notif_estado
        FROM usuarios u
        JOIN proyecto_usuarios pu ON u.id = pu.usuario_id
        JOIN usuario_roles ur ON u.id = ur.usuario_id
        JOIN roles r ON ur.rol_id = r.id
        LEFT JOIN preferencias_notificaciones pn ON u.id = pn.usuario_id
        WHERE pu.proyecto_id = ? AND r.nombre IN ({placeholders}) AND u.activo = 1
    """

    cursor = db.cursor()
    try:
        cursor.execute(query, params)
        users_to_notify = cursor.fetchall()

        sql_insert = "INSERT INTO notificaciones (usuario_id, mensaje, url, conexion_id) VALUES (?, ?, ?, ?)"
        for user in users_to_notify:
            if user['id'] != g.user['id']:
                full_url = url_for('conexiones.detalle_conexion', conexion_id=conexion_id, _external=True) + url_suffix
                cursor.execute(sql_insert, (user['id'], message, full_url, conexion_id))
        db.commit()
    finally:
        cursor.close()

    # Enviar correos fuera de la transacción de la base de datos
    for user in users_to_notify:
        if user['id'] != g.user['id'] and user['email'] and user['email_notif_estado']:
            full_url = url_for('conexiones.detalle_conexion', conexion_id=conexion_id, _external=True) + url_suffix
            _send_email_notification(
                recipients=[user['email']],
                subject=f"Hepta-Conexiones: Notificación sobre {conexion['codigo_conexion']}",
                template='email/notification.html',
                nombre_usuario=user['nombre_completo'],
                mensaje_notificacion=message,
                url_accion=full_url
            )

def process_connection_state_transition(db, conexion_id, new_status_form, user_id, user_full_name, user_roles, details=None):
    """Procesa un cambio de estado de conexión de forma centralizada y segura."""
    conexion = _get_conexion(conexion_id)
    estado_actual = conexion['estado']
    new_db_state, message, audit_action = None, "", ""
    success = False

    # Lógica de transición de estado
    if new_status_form == 'EN_PROCESO' and estado_actual == 'SOLICITADO' and ('REALIZADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
        new_db_state, audit_action, message, success = 'EN_PROCESO', 'TOMAR_CONEXION', f"Conexión tomada por {user_full_name}.", True
    elif new_status_form == 'REALIZADO' and estado_actual == 'EN_PROCESO' and (conexion['realizador_id'] == user_id or 'ADMINISTRADOR' in user_roles):
        new_db_state, audit_action, message, success = 'REALIZADO', 'MARCAR_REALIZADO_CONEXION', "Conexión lista para aprobación.", True
    elif new_status_form == 'APROBADO' and estado_actual == 'REALIZADO' and ('APROBADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
        new_db_state, audit_action, message, success = 'APROBADO', 'APROBAR_CONEXION', "Conexión APROBADA.", True
    elif new_status_form == 'RECHAZADO' and estado_actual == 'REALIZADO' and ('APROBADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
        if not details: return False, 'Debes proporcionar un motivo para el rechazo.', None
        new_db_state, audit_action, message, success = 'EN_PROCESO', 'RECHAZAR_CONEXION', f"Conexión rechazada. Motivo: {details}", True

    if not success:
        return False, 'Acción no permitida o estado inválido.', None

    cursor = db.cursor()
    try:
        timestamp_expr = "CURRENT_TIMESTAMP"
        sql_update = f"UPDATE conexiones SET estado = ?, fecha_modificacion = {timestamp_expr}"
        params = [new_db_state]

        if new_db_state == 'EN_PROCESO' and audit_action == 'TOMAR_CONEXION':
            sql_update += ", realizador_id = ?"
            params.append(user_id)
        elif new_db_state == 'APROBADO':
            sql_update += ", aprobador_id = ?"
            params.append(user_id)
        elif audit_action == 'RECHAZAR_CONEXION':
            sql_update += ", detalles_rechazo = ?"
            params.append(details)

        sql_update += " WHERE id = ?"
        params.append(conexion_id)
        cursor.execute(sql_update, tuple(params))

        sql_historial = "INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES (?, ?, ?, ?)"
        cursor.execute(sql_historial, (conexion_id, user_id, new_status_form, details))
        db.commit()
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error en transición de estado para conexión {conexion_id}: {e}", exc_info=True)
        return False, "Error interno al cambiar de estado.", None
    finally:
        cursor.close()

    log_action(audit_action, user_id, 'conexiones', conexion_id, f"Estado: {estado_actual} -> {new_db_state}. Detalles: {details or 'N/A'}")

    # Notificar a los usuarios relevantes
    roles_map = {
        'EN_PROCESO': ['SOLICITANTE', 'ADMINISTRADOR'],
        'REALIZADO': ['APROBADOR', 'ADMINISTRADOR'],
        'APROBADO': ['SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'],
    }
    if audit_action == 'RECHAZAR_CONEXION':
        _notify_users(db, conexion_id, message, "", ['REALIZADOR', 'ADMINISTRADOR'])
    elif new_db_state in roles_map:
        _notify_users(db, conexion_id, message, "", roles_map[new_db_state])

    return True, message, new_db_state

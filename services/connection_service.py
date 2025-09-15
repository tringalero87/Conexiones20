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
        # Asegúrate de que las claves de tipo y subtipo existan
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
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"

    conexion_query = f"""
        SELECT c.*, p.nombre as proyecto_nombre,
               sol.nombre_completo as solicitante_nombre,
               real.nombre_completo as realizador_nombre,
               aprob.nombre_completo as aprobador_nombre
        FROM conexiones c
        JOIN proyectos p ON c.proyecto_id = p.id
        LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
        LEFT JOIN usuarios real ON c.realizador_id = real.id
        LEFT JOIN usuarios aprob ON c.aprobador_id = aprob.id
        WHERE c.id = {p}
    """

    cursor = db.cursor()
    try:
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
    """
    Función auxiliar para crear notificaciones para usuarios con roles específicos
    y también enviar correos electrónicos si tienen un email y sus preferencias lo permiten.
    """
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"

    conexion = _get_conexion(conexion_id)
    proyecto_id = conexion['proyecto_id']

    placeholders = ', '.join([p] * len(roles_to_notify))
    params = [proyecto_id] + roles_to_notify

    query = f"""
        SELECT DISTINCT u.id, u.email, u.nombre_completo, COALESCE(pn.email_notif_estado, TRUE) as email_notif_estado
        FROM usuarios u
        JOIN proyecto_usuarios pu ON u.id = pu.usuario_id
        JOIN usuario_roles ur ON u.id = ur.usuario_id
        JOIN roles r ON ur.rol_id = r.id
        LEFT JOIN preferencias_notificaciones pn ON u.id = pn.usuario_id
        WHERE pu.proyecto_id = {p} AND r.nombre IN ({placeholders}) AND u.activo = TRUE
    """

    cursor = db.cursor()
    try:
        cursor.execute(query, params)
        users_to_notify = cursor.fetchall()

        # First, insert all internal notifications to ensure DB persistence
        for user in users_to_notify:
            if user['id'] != g.user['id'] or (url_suffix == "" and "RECHAZADO" in message):
                sql_insert = f"INSERT INTO notificaciones (usuario_id, mensaje, url, conexion_id) VALUES ({p}, {p}, {p}, {p})"
                full_url = url_for('conexiones.detalle_conexion', conexion_id=conexion_id, _external=True) + url_suffix
                insert_params = (user['id'], message, full_url, conexion_id)
                cursor.execute(sql_insert, insert_params)
        db.commit()
    finally:
        cursor.close()

    # Now, send emails
    for user in users_to_notify:
        if user['id'] != g.user['id'] or (url_suffix == "" and "RECHAZADO" in message):
            if user['email'] and user['email_notif_estado']:
                full_url = url_for('conexiones.detalle_conexion', conexion_id=conexion_id, _external=True) + url_suffix
                _send_email_notification(
                    recipients=[user['email']],
                    subject=f"Hepta-Conexiones: Notificación sobre conexión {conexion['codigo_conexion']}",
                    template='email/notification.html',
                    nombre_usuario=user['nombre_completo'],
                    mensaje_notificacion=message,
                    url_accion=full_url
                )

def process_connection_state_transition(db, conexion_id, new_status_form, user_id, user_full_name, user_roles, details=None):
    """
    Procesa un cambio de estado de conexión de forma centralizada.
    Retorna (success, message, new_db_state_name_for_audit)
    """
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"

    conexion = _get_conexion(conexion_id)
    estado_actual = conexion['estado']
    new_db_state = None
    message = ""
    success = False
    audit_action = ""

    cursor = db.cursor()

    try:
        if new_status_form == 'EN_PROCESO' and estado_actual == 'SOLICITADO' and ('REALIZADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
            new_db_state = 'EN_PROCESO'
            cursor.execute(f'UPDATE conexiones SET realizador_id = {p} WHERE id = {p}', (user_id, conexion_id))
            audit_action = 'TOMAR_CONEXION'
            message = f"La conexión {conexion['codigo_conexion']} ha sido tomada por {user_full_name}."
            success = True

        elif new_status_form == 'REALIZADO' and estado_actual == 'EN_PROCESO' and (conexion['realizador_id'] == user_id or 'ADMINISTRADOR' in user_roles):
            new_db_state = 'REALIZADO'
            audit_action = 'MARCAR_REALIZADO_CONEXION'
            message = f"La conexión {conexion['codigo_conexion']} está lista para ser aprobada."
            success = True

        elif new_status_form == 'APROBADO' and estado_actual == 'REALIZADO' and ('APROBADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
            new_db_state = 'APROBADO'
            cursor.execute(f'UPDATE conexiones SET aprobador_id = {p} WHERE id = {p}', (user_id, conexion_id))
            audit_action = 'APROBAR_CONEXION'
            message = f"La conexión {conexion['codigo_conexion']} ha sido APROBADA."
            success = True

        elif new_status_form == 'RECHAZADO' and estado_actual == 'REALIZADO' and ('APROBADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
            if not details:
                return False, 'Debes proporcionar un motivo para el rechazo.', None
            new_db_state = 'EN_PROCESO'
            cursor.execute(f'UPDATE conexiones SET detalles_rechazo = {p} WHERE id = {p}', (details, conexion_id))
            audit_action = 'RECHAZAR_CONEXION'
            message = f"Atención: La conexión {conexion['codigo_conexion']} fue rechazada. Motivo: {details}"
            success = True

        if success and new_db_state:
            current_timestamp_sql = "datetime('now')" if is_testing else "CURRENT_TIMESTAMP"
            cursor.execute(f'UPDATE conexiones SET estado = {p}, fecha_modificacion = {current_timestamp_sql} WHERE id = {p}', (new_db_state, conexion_id))
            cursor.execute(f'INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES ({p}, {p}, {p}, {p})',
                       (conexion_id, user_id, new_status_form, details))

            # Log action and commit everything at once
            db.commit()

            # These can be called after commit
            log_action(audit_action, user_id, 'conexiones', conexion_id,
                       f"Conexión '{conexion['codigo_conexion']}' Estado: {estado_actual} -> {new_db_state}. Detalles: {details if details else 'N/A'}")

            # Notify users after the state is securely saved
            if new_db_state == 'EN_PROCESO':
                 _notify_users(db, conexion_id, message, "", ['SOLICITANTE', 'ADMINISTRADOR'])
            elif new_db_state == 'REALIZADO':
                _notify_users(db, conexion_id, message, "", ['APROBADOR', 'ADMINISTRADOR'])
            elif new_db_state == 'APROBADO':
                _notify_users(db, conexion_id, message, "", ['SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'])
            elif audit_action == 'RECHAZAR_CONEXION':
                _notify_users(db, conexion_id, message, "", ['REALIZADOR', 'ADMINISTRADOR'])

            return True, message, new_db_state
        else:
            return False, 'Acción no permitida o estado inválido.', None
    finally:
        cursor.close()

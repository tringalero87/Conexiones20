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

import sqlite3

def _get_conexion(conexion_id):
    """
    Función auxiliar para obtener una conexión y sus datos asociados desde la base de datos.
    Lanza un error 404 si la conexión no se encuentra.
    """
    db = get_db()
    is_postgres = hasattr(db, 'cursor')
    placeholder = '%s' if is_postgres else '?'

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
        WHERE c.id = {placeholder}
    """

    if is_postgres:
        with db.cursor() as cursor:
            cursor.execute(conexion_query, (conexion_id,))
            conexion = cursor.fetchone()
    else:
        conexion = db.execute(conexion_query, (conexion_id,)).fetchone()

    if conexion is None:
        from flask import abort
        abort(404, f"La conexión con id {conexion_id} no existe.")
    return conexion

def _send_email_notification(recipients, subject, template, **kwargs):
    """
    Función auxiliar para enviar notificaciones por correo electrónico de forma asíncrona.
    RECOMENDACIÓN: Para una aplicación en producción, es mejor usar una cola de tareas como Celery
    en lugar de hilos de threading directamente para manejar el envío de correos.
    """
    if not recipients:
        return # No enviar si no hay destinatarios

    if not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.warning("Configuración de correo electrónico no completa. No se enviará email.")
        return

    # Se crea el objeto Message de Flask-Mail
    msg = Message(subject, recipients=recipients)
    msg.html = render_template(template, **kwargs)

    # Se define una función para enviar el correo en un hilo separado
    def send_async_email(app, msg_obj):
        with app.app_context(): # Se asegura de que el hilo tenga el contexto de la aplicación
            try:
                mail.send(msg_obj)
                app.logger.info(f"Correo enviado a {', '.join(msg_obj.recipients)} con asunto: {msg_obj.subject}")
            except Exception as e:
                app.logger.error(f"Error al enviar correo electrónico a {msg_obj.recipients}: {e}", exc_info=True)

    # Se inicia el hilo. current_app._get_current_object() es importante para pasar la app en un contexto de hilo.
    thr = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
    thr.start()


def _notify_users(db, conexion_id, message, url_suffix, roles_to_notify):
    """
    Función auxiliar para crear notificaciones para usuarios con roles específicos
    y también enviar correos electrónicos si tienen un email y sus preferencias lo permiten.
    """
    conexion = _get_conexion(conexion_id)
    proyecto_id = conexion['proyecto_id']
    is_postgres = hasattr(db, 'cursor')

    # Adaptar placeholders para la consulta IN
    if is_postgres:
        placeholders = ', '.join(['%s'] * len(roles_to_notify))
        params = [proyecto_id] + roles_to_notify
    else:
        placeholders = ', '.join(['?'] * len(roles_to_notify))
        params = [proyecto_id] + roles_to_notify

    query = f"""
        SELECT DISTINCT u.id, u.email, u.nombre_completo, COALESCE(pn.email_notif_estado, TRUE) as email_notif_estado
        FROM usuarios u
        JOIN proyecto_usuarios pu ON u.id = pu.usuario_id
        JOIN usuario_roles ur ON u.id = ur.usuario_id
        JOIN roles r ON ur.rol_id = r.id
        LEFT JOIN preferencias_notificaciones pn ON u.id = pn.usuario_id
        WHERE pu.proyecto_id = {'%s' if is_postgres else '?'} AND r.nombre IN ({placeholders}) AND u.activo = TRUE
    """

    if is_postgres:
        with db.cursor() as cursor:
            cursor.execute(query, params)
            users_to_notify = cursor.fetchall()
    else:
        users_to_notify = db.execute(query, params).fetchall()

    # First, insert all internal notifications to ensure DB persistence
    for user in users_to_notify:
        if user['id'] != g.user['id'] or (url_suffix == "" and "RECHAZADO" in message):
            sql_insert = "INSERT INTO notificaciones (usuario_id, mensaje, url, conexion_id) VALUES (%s, %s, %s, %s)"
            insert_params = (user['id'], message, url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + url_suffix, conexion_id)
            if not is_postgres:
                sql_insert = sql_insert.replace('%s', '?')

            if is_postgres:
                with db.cursor() as cursor:
                    cursor.execute(sql_insert, insert_params)
            else:
                db.execute(sql_insert, insert_params)
    db.commit()

    # Now, send emails
    for user in users_to_notify:
        if user['id'] != g.user['id'] or (url_suffix == "" and "RECHAZADO" in message):
            # Recopilar destinatarios para el correo electrónico, si las preferencias lo permiten
            if user['email'] and user['email_notif_estado']:
                _send_email_notification(
                    recipients=[user['email']],
                    subject=f"Hepta-Conexiones: Notificación sobre conexión {conexion['codigo_conexion']}",
                    template='email/notification.html',
                    nombre_usuario=user['nombre_completo'],
                    mensaje_notificacion=message,
                    url_accion=url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + url_suffix
                )


def process_connection_state_transition(db, conexion_id, new_status_form, user_id, user_full_name, user_roles, details=None):
    """
    Procesa un cambio de estado de conexión de forma centralizada.
    Retorna (success, message, new_db_state_name_for_audit)
    """
    is_postgres = hasattr(db, 'cursor')
    placeholder = '%s' if is_postgres else '?'

    def execute_query(sql, params):
        if is_postgres:
            with db.cursor() as cursor:
                cursor.execute(sql, params)
        else:
            db.execute(sql, params)

    conexion = _get_conexion(conexion_id)
    estado_actual = conexion['estado']
    new_db_state = None
    message = ""
    success = False
    audit_action = ""

    if new_status_form == 'EN_PROCESO' and estado_actual == 'SOLICITADO' and ('REALIZADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
        new_db_state = 'EN_PROCESO'
        execute_query(f'UPDATE conexiones SET realizador_id = {placeholder} WHERE id = {placeholder}', (user_id, conexion_id))
        audit_action = 'TOMAR_CONEXION'
        message = f"La conexión {conexion['codigo_conexion']} ha sido tomada por {user_full_name}."
        _notify_users(db, conexion_id, message, "", ['SOLICITANTE', 'ADMINISTRADOR'])
        success = True

    elif new_status_form == 'REALIZADO' and estado_actual == 'EN_PROCESO' and (conexion['realizador_id'] == user_id or 'ADMINISTRADOR' in user_roles):
        new_db_state = 'REALIZADO'
        audit_action = 'MARCAR_REALIZADO_CONEXION'
        message = f"La conexión {conexion['codigo_conexion']} está lista para ser aprobada."
        _notify_users(db, conexion_id, message, "", ['APROBADOR', 'ADMINISTRADOR'])
        success = True

    elif new_status_form == 'APROBADO' and estado_actual == 'REALIZADO' and ('APROBADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
        new_db_state = 'APROBADO'
        execute_query(f'UPDATE conexiones SET aprobador_id = {placeholder} WHERE id = {placeholder}', (user_id, conexion_id))
        audit_action = 'APROBAR_CONEXION'
        message = f"La conexión {conexion['codigo_conexion']} ha sido APROBADA."
        _notify_users(db, conexion_id, message, "", ['SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'])
        success = True

    elif new_status_form == 'RECHAZADO' and estado_actual == 'REALIZADO' and ('APROBADOR' in user_roles or 'ADMINISTRADOR' in user_roles):
        if not details:
            return False, 'Debes proporcionar un motivo para el rechazo.', None
        new_db_state = 'EN_PROCESO'
        execute_query(f'UPDATE conexiones SET detalles_rechazo = {placeholder} WHERE id = {placeholder}', (details, conexion_id))
        audit_action = 'RECHAZAR_CONEXION'
        message = f"Atención: La conexión {conexion['codigo_conexion']} fue rechazada. Motivo: {details}"
        _notify_users(db, conexion_id, message, "", ['REALIZADOR', 'ADMINISTRADOR'])
        success = True

    if success and new_db_state:
        execute_query(f'UPDATE conexiones SET estado = {placeholder}, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = {placeholder}', (new_db_state, conexion_id))
        execute_query(f'INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})',
                   (conexion_id, user_id, new_status_form, details))
        log_action(audit_action, user_id, 'conexiones', conexion_id,
                   f"Conexión '{conexion['codigo_conexion']}' Estado: {estado_actual} -> {new_db_state}. Detalles: {details if details else 'N/A'}")
        db.commit()
        return True, message, new_db_state
    else:
        return False, 'Acción no permitida o estado inválido.', None

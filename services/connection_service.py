import json
from flask import current_app, render_template, url_for, g, abort
from flask_mail import Message
from extensions import mail
from db import get_db, log_action
from utils.config_loader import load_conexiones_config
from dal.sqlite_dal import SQLiteDAL


def get_tipologia_config(tipo, subtipo, tipologia_nombre):
    """Función auxiliar para obtener la configuración de una tipología desde el loader cacheado."""
    estructura = load_conexiones_config()
    try:
        if tipo in estructura and subtipo in estructura[tipo]['subtipos']:
            tipologia_obj_list = estructura[tipo]['subtipos'][subtipo]['tipologias']
            return next((t for t in tipologia_obj_list if t['nombre'] == tipologia_nombre), None)
        return None
    except (KeyError, StopIteration) as e:
        current_app.logger.error(
            f"Error al buscar configuración de tipología: {e}")
        return None


def get_conexion(conexion_id):
    """
    Obtiene una conexión y sus datos asociados utilizando la capa DAL.
    Lanza un error 404 si la conexión no se encuentra.
    """
    dal = SQLiteDAL()
    conexion = dal.get_conexion(conexion_id)
    if conexion is None:
        abort(404, f"La conexión con id {conexion_id} no existe.")
    return dict(conexion)


def get_connection_details(conexion_id):
    """
    Obtiene todos los detalles necesarios para la página de una conexión.
    """
    dal = SQLiteDAL()
    conexion = get_conexion(conexion_id)
    archivos = dal.get_archivos_by_conexion(conexion_id)
    comentarios = dal.get_comentarios_by_conexion(conexion_id)
    historial = dal.get_historial_by_conexion(conexion_id)

    # Agrupar archivos por tipo
    archivos_agrupados = {}
    for archivo in archivos:
        tipo = archivo['tipo_archivo']
        if tipo not in archivos_agrupados:
            archivos_agrupados[tipo] = []
        archivos_agrupados[tipo].append(archivo)

    detalles_json = json.loads(
        conexion['detalles_json']) if conexion['detalles_json'] else {}
    tipologia_config = get_tipologia_config(
        conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    plantilla_archivos = tipologia_config.get(
        'plantilla_archivos', []) if tipologia_config else []

    return {
        "conexion": conexion,
        "archivos_agrupados": archivos_agrupados,
        "comentarios": comentarios,
        "historial": historial,
        "detalles": detalles_json,
        "plantilla_archivos": plantilla_archivos
    }


def generate_unique_connection_code(codigo_conexion_base):
    """
    Genera un código de conexión único, añadiendo un sufijo numérico si es necesario.
    """
    dal = SQLiteDAL()
    existing_codes = dal.get_all_conexiones_codes()

    if codigo_conexion_base not in existing_codes:
        return codigo_conexion_base

    contador = 1
    while True:
        nuevo_codigo = f"{codigo_conexion_base}-{contador}"
        if nuevo_codigo not in existing_codes:
            return nuevo_codigo
        contador += 1


def create_connection(form_data, user_id):
    """
    Procesa la creación de una nueva conexión.
    Retorna (id_nueva_conexion, mensaje_exito) o (None, mensaje_error).
    """
    dal = SQLiteDAL()
    tipo = form_data.get('tipo')
    subtipo = form_data.get('subtipo')
    tipologia_nombre = form_data.get('tipologia_nombre')

    tipologia_config = get_tipologia_config(tipo, subtipo, tipologia_nombre)
    if not tipologia_config:
        return None, "Error: Configuración de tipología no encontrada."

    num_perfiles = tipologia_config.get('perfiles', 0)
    perfiles_para_plantilla = {}
    perfiles_para_detalles = {}

    for i in range(1, num_perfiles + 1):
        nombre_campo = f'perfil_{i}'
        nombre_completo_perfil = form_data.get(nombre_campo)
        if not nombre_completo_perfil:
            return None, f"El campo 'Perfil {i}' es obligatorio."

        alias_row = dal.get_alias(nombre_completo_perfil)
        perfiles_para_plantilla[f'p{i}'] = alias_row['alias'] if alias_row else nombre_completo_perfil
        perfiles_para_detalles[f'Perfil {i}'] = nombre_completo_perfil

    codigo_conexion_base = tipologia_config.get(
        'plantilla', '').format(**perfiles_para_plantilla)
    codigo_conexion_final = generate_unique_connection_code(
        codigo_conexion_base)

    conexion_data = {
        'codigo_conexion': codigo_conexion_final,
        'proyecto_id': form_data.get('proyecto_id'),
        'tipo': tipo,
        'subtipo': subtipo,
        'tipologia': tipologia_nombre,
        'descripcion': form_data.get('descripcion'),
        'detalles_json': perfiles_para_detalles,
        'solicitante_id': user_id
    }

    try:
        new_id = dal.create_conexion(conexion_data)
        dal.add_historial_estado(new_id, user_id, 'SOLICITADO')

        log_action('CREAR_CONEXION', user_id, 'conexiones', new_id,
                   f"Conexión '{codigo_conexion_final}' creada.")

        db = get_db()
        _notify_users(db, new_id, f"Nueva conexión '{codigo_conexion_final}' lista para ser tomada.", "", [
                      'REALIZADOR', 'ADMINISTRADOR'])

        return new_id, f'Conexión {codigo_conexion_final} creada con éxito.'
    except Exception as e:
        current_app.logger.error(
            f"Error al crear conexión: {e}", exc_info=True)
        return None, "Ocurrió un error interno al crear la conexión."


def _send_email_notification(recipients, subject, template, **kwargs):
    """
    Función auxiliar para enviar notificaciones por correo electrónico de forma asíncrona.
    """
    if not recipients:
        return

    if not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.warning(
            "Configuración de correo electrónico no completa. No se enviará email.")
        return

    msg = Message(subject, recipients=recipients)
    msg.html = render_template(template, **kwargs)

    def send_async_email(app, msg_obj):
        with app.app_context():
            try:
                mail.send(msg_obj)
                app.logger.info(
                    f"Correo enviado a {', '.join(msg_obj.recipients)} con asunto: {msg_obj.subject}")
            except Exception as e:
                app.logger.error(
                    f"Error al enviar correo electrónico a {msg_obj.recipients}: {e}", exc_info=True)

    # Usar el ThreadPoolExecutor de la aplicación para gestionar los hilos
    current_app.executor.submit(
        send_async_email, current_app._get_current_object(), msg)


def _notify_users(conexion_id, message, url_suffix, roles_to_notify):
    """Crea notificaciones y envía correos electrónicos a usuarios con roles específicos."""
    dal = SQLiteDAL()
    conexion = get_conexion(conexion_id)

    users_to_notify = dal.get_users_for_notification(
        conexion['proyecto_id'], roles_to_notify)

    for user in users_to_notify:
        if user['id'] != g.user['id']:
            full_url = url_for('conexiones.detalle_conexion',
                               conexion_id=conexion_id, _external=True) + url_suffix
            dal.create_notification(user['id'], message, full_url, conexion_id)

            if user['email'] and user['email_notif_estado']:
                _send_email_notification(
                    recipients=[user['email']],
                    subject=f"Hepta-Conexiones: Notificación sobre {conexion['codigo_conexion']}",
                    template='email/notification.html',
                    nombre_usuario=user['nombre_completo'],
                    mensaje_notificacion=message,
                    url_accion=full_url
                )


def update_connection(conexion_id, form, current_user, user_roles):
    """
    Procesa la actualización de una conexión existente.
    """
    dal = SQLiteDAL()
    conexion = get_conexion(conexion_id)

    # Lógica de permisos de edición
    can_edit = ('ADMINISTRADOR' in user_roles or
                ('SOLICITANTE' in user_roles and conexion['estado'] == 'SOLICITADO' and conexion['solicitante_id'] == current_user['id']) or
                ('REALIZADOR' in user_roles and conexion['estado'] == 'EN_PROCESO' and conexion['realizador_id'] == current_user['id']))
    if not can_edit:
        abort(403)

    tipologia_config = get_tipologia_config(
        conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    if not tipologia_config:
        return False, "Error: No se encontró la configuración de la tipología para editar.", None

    num_perfiles = tipologia_config.get('perfiles', 0)
    perfiles_nuevos_dict_alias = {}
    perfiles_nuevos_dict_full_name = {}

    for i in range(1, num_perfiles + 1):
        nombre_completo_perfil_nuevo = getattr(
            form, f'perfil_{i}').data.strip()
        alias_row = dal.get_alias(nombre_completo_perfil_nuevo)
        perfiles_nuevos_dict_alias[f'p{i}'] = alias_row['alias'] if alias_row else nombre_completo_perfil_nuevo
        perfiles_nuevos_dict_full_name[f'Perfil {i}'] = nombre_completo_perfil_nuevo

    nuevo_codigo_base = tipologia_config['plantilla'].format(
        **perfiles_nuevos_dict_alias)
    codigo_a_guardar = conexion['codigo_conexion']
    flash_message = None

    if not conexion['codigo_conexion'].startswith(nuevo_codigo_base):
        codigo_a_guardar = generate_unique_connection_code(nuevo_codigo_base)
        flash_message = f"El código de la conexión se ha actualizado a '{codigo_a_guardar}'."

    update_data = {
        'codigo_conexion': codigo_a_guardar,
        'descripcion': form.descripcion.data,
        'detalles_json': perfiles_nuevos_dict_full_name
    }

    try:
        dal.update_conexion(conexion_id, update_data)
        log_action('EDITAR_CONEXION', current_user['id'], 'conexiones', conexion_id,
                   f"Conexión '{conexion['codigo_conexion']}' editada a '{codigo_a_guardar}'.")
        return True, 'Conexión actualizada con éxito.', flash_message
    except Exception as e:
        current_app.logger.error(
            f"Error al actualizar conexión {conexion_id}: {e}", exc_info=True)
        return False, "Ocurrió un error interno al actualizar la conexión.", None


def assign_realizador(conexion_id, username_to_assign, current_user):
    """
    Asigna o reasigna un realizador a una conexión.
    """
    dal = SQLiteDAL()
    conexion = get_conexion(conexion_id)

    usuario_a_asignar = dal.get_usuario_a_asignar(username_to_assign)
    if not usuario_a_asignar:
        return False, f"Usuario '{username_to_assign}' no encontrado o inactivo."

    try:
        if conexion['estado'] == 'SOLICITADO':
            nuevo_estado = 'EN_PROCESO'
            dal.update_conexion_realizador(
                conexion_id, usuario_a_asignar['id'], nuevo_estado)
            dal.add_historial_estado(
                conexion_id, current_user['id'], nuevo_estado, f"Asignada a {usuario_a_asignar['nombre_completo']}")

            _notify_users(conexion_id, f"La conexión {conexion['codigo_conexion']} ha sido asignada.", "", [
                          'SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'])

            return True, f"Conexión asignada a {usuario_a_asignar['nombre_completo']}."
        else:
            dal.update_conexion_realizador(
                conexion_id, usuario_a_asignar['id'])
            log_action('REASIGNAR_CONEXION', current_user['id'], 'conexiones', conexion_id,
                       f"Conexión reasignada a '{usuario_a_asignar['nombre_completo']}'.")

            _notify_users(conexion_id, f"La conexión {conexion['codigo_conexion']} ha sido reasignada.", "", [
                          'SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'])

            return True, 'Realizador de la conexión actualizado.'
    except Exception as e:
        current_app.logger.error(
            f"Error al asignar realizador a conexión {conexion_id}: {e}", exc_info=True)
        return False, "Ocurrió un error interno al asignar el realizador."


def delete_connection(conexion_id, user_id):
    """
    Elimina una conexión y registra la acción.
    """
    dal = SQLiteDAL()
    # Para obtener el código antes de eliminar
    conexion = get_conexion(conexion_id)
    try:
        dal.delete_conexion(conexion_id)
        log_action('ELIMINAR_CONEXION', user_id, 'conexiones', conexion_id,
                   f"Conexión '{conexion['codigo_conexion']}' eliminada.")
        return True, f"La conexión {conexion['codigo_conexion']} ha sido eliminada."
    except Exception as e:
        current_app.logger.error(
            f"Error al eliminar conexión {conexion_id}: {e}", exc_info=True)
        return False, "Ocurrió un error interno al eliminar la conexión."


def process_connection_state_transition(conexion_id, new_status_form, user_id, user_full_name, user_roles, details=None):
    """Procesa un cambio de estado de conexión de forma centralizada y segura."""
    conexion = get_conexion(conexion_id)
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
        if not details:
            return False, 'Debes proporcionar un motivo para el rechazo.', None
        new_db_state, audit_action, message, success = 'EN_PROCESO', 'RECHAZAR_CONEXION', f"Conexión rechazada. Motivo: {details}", True

    if not success:
        return False, 'Acción no permitida o estado inválido.', None

    db = get_db()
    cursor = db.cursor()
    try:
        sql_update_parts = ["estado = ?",
                            "fecha_modificacion = CURRENT_TIMESTAMP"]
        params = [new_db_state]

        if new_db_state == 'EN_PROCESO' and audit_action == 'TOMAR_CONEXION':
            sql_update_parts.append("realizador_id = ?")
            params.append(user_id)
        elif new_db_state == 'APROBADO':
            sql_update_parts.append("aprobador_id = ?")
            params.append(user_id)
        elif audit_action == 'RECHAZAR_CONEXION':
            sql_update_parts.append("detalles_rechazo = ?")
            params.append(details)

        # Construye la consulta de forma segura
        sql_update = "UPDATE conexiones SET " + \
            ", ".join(sql_update_parts) + " WHERE id = ?"
        params.append(conexion_id)

        cursor.execute(sql_update, tuple(params))

        sql_historial = "INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES (?, ?, ?, ?)"
        cursor.execute(sql_historial, (conexion_id,
                       user_id, new_status_form, details))
        db.commit()
    except Exception as e:
        db.rollback()
        current_app.logger.error(
            f"Error en transición de estado para conexión {conexion_id}: {e}", exc_info=True)
        return False, "Error interno al cambiar de estado.", None
    finally:
        cursor.close()

    log_action(audit_action, user_id, 'conexiones', conexion_id,
               f"Estado: {estado_actual} -> {new_db_state}. Detalles: {details or 'N/A'}")

    # Notificar a los usuarios relevantes
    roles_map = {
        'EN_PROCESO': ['SOLICITANTE', 'ADMINISTRADOR'],
        'REALIZADO': ['APROBADOR', 'ADMINISTRADOR'],
        'APROBADO': ['SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'],
    }
    if audit_action == 'RECHAZAR_CONEXION':
        _notify_users(conexion_id, message, "", [
                      'REALIZADOR', 'ADMINISTRADOR'])
    elif new_db_state in roles_map:
        _notify_users(conexion_id, message, "", roles_map[new_db_state])

    return True, message, new_db_state

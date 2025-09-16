import os
import json
import re
import io
import csv
from datetime import datetime, timedelta
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    g,
    flash,
    abort,
    current_app,
    make_response)
from werkzeug.security import generate_password_hash
from db import get_db, log_action
from forms import UserForm, ConfigurationForm, ReportForm, AliasForm, ComputosReportForm
from flask_wtf import FlaskForm
import pandas as pd
from weasyprint import HTML
from flask_mail import Message
from extensions import mail
from collections import defaultdict
from werkzeug.utils import secure_filename
from utils.computos import calcular_peso_perfil
from . import roles_required


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _generate_report_data_and_file(reporte_id, app_context):
    """
    Genera los datos del reporte y un archivo en memoria (BytesIO o StringIO)
    según el formato especificado en el reporte.
    Retorna (filename, mimetype, file_content, preview_results) o (None, None, None, None) si falla.
    """
    with app_context:
        db = get_db()
        reporte = db.execute(
            'SELECT * FROM reportes WHERE id = %s', (reporte_id,)).fetchone()
        if not reporte:
            current_app.logger.error(
                f"Reporte ID {reporte_id} no encontrado para generación programada.")
            return None, None, None, None

        try:
            filtros = json.loads(reporte['filtros'])
        except json.JSONDecodeError:
            current_app.logger.error(
                f"Error de JSON en filtros para reporte ID {reporte_id}.")
            return None, None, None, None

        columnas_seleccionadas = filtros.get('columnas', [])
        output_format = filtros.get('output_format', 'csv')

        if not columnas_seleccionadas:
            current_app.logger.warning(
                f"Reporte ID {reporte_id} no tiene columnas seleccionadas.")
            return None, None, None, None

        query_base = f"SELECT {
            ', '.join(columnas_seleccionadas)} FROM conexiones_view WHERE 1=1"
        params = []

        if filtros.get('proyecto_id') and filtros['proyecto_id'] != 0:
            query_base += " AND proyecto_id = %s"
            params.append(filtros['proyecto_id'])
        if filtros.get('estado'):
            query_base += " AND estado = %s"
            params.append(filtros['estado'])
        if filtros.get('realizador_id') and filtros['realizador_id'] != 0:
            query_base += " AND realizador_id = %s"
            params.append(filtros['realizador_id'])
        if filtros.get('fecha_inicio'):
            query_base += " AND date(fecha_creacion) >= %s"
            params.append(filtros['fecha_inicio'])
        if filtros.get('fecha_fin'):
            query_base += " AND date(fecha_creacion) <= %s"
            params.append(filtros['fecha_fin'])

        resultados_raw = db.execute(query_base, tuple(params)).fetchall()

        preview_results = [dict(row) for row in resultados_raw[:10]]

        resultados_dicts = [dict(row) for row in resultados_raw]

        filename_base = f"reporte_{
            reporte['nombre'].replace(
                ' ', '_').lower()}"
        file_content = None
        mimetype = None
        filename = None

        try:
            if output_format == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(columnas_seleccionadas)
                for row in resultados_dicts:
                    writer.writerow([row[col]
                                    for col in columnas_seleccionadas])
                file_content = output.getvalue().encode('utf-8')
                mimetype = "text/csv"
                filename = f"{filename_base}.csv"

            elif output_format == 'xlsx':
                df = pd.DataFrame(
                    resultados_dicts,
                    columns=columnas_seleccionadas)
                output = io.BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                file_content = output.getvalue()
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                filename = f"{filename_base}.xlsx"

            elif output_format == 'pdf':
                reporte_data_for_template = {
                    'nombre_reporte': reporte['nombre'],
                    'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'columnas': columnas_seleccionadas,
                    'resultados_preview': preview_results,
                    'descripcion_filtros': reporte['descripcion'] if reporte['descripcion'] else 'Reporte generado automáticamente.'}
                rendered_html = render_template(
                    'email/reporte_programado.html',
                    reporte=reporte_data_for_template,
                    resultados=resultados_dicts,
                    now=datetime.now)

                pdf_bytes = HTML(string=rendered_html).write_pdf()
                file_content = pdf_bytes
                mimetype = "application/pdf"
                filename = f"{filename_base}.pdf"

            db.execute(
                'UPDATE reportes SET ultima_ejecucion = CURRENT_TIMESTAMP WHERE id = %s',
                (reporte_id,
                 ))
            db.commit()

            return filename, mimetype, file_content, preview_results

        except Exception as e:
            current_app.logger.error(
                f"Error generando reporte {reporte_id} en formato {output_format}: {e}",
                exc_info=True)
            return None, None, None, None


def scheduled_report_job(reporte_id):
    """
    Esta función es el "job" que APScheduler ejecutará.
    Genera el reporte y lo envía por correo electrónico.
    """
    with current_app.app_context():
        db = get_db()
        reporte = db.execute(
            'SELECT * FROM reportes WHERE id = %s', (reporte_id,)).fetchone()
        if not reporte or not reporte['programado'] or not reporte['destinatarios']:
            current_app.logger.warning(
                (f"Tarea programada para reporte ID {reporte_id} no ejecutada: "
                 "reporte no encontrado, no programado o sin destinatarios.")
            )
            return

        recipients_str = reporte['destinatarios']
        recipients = [email.strip()
                      for email in recipients_str.split(',') if email.strip()]

        if not recipients:
            current_app.logger.warning(
                f"Reporte ID {reporte_id} programado sin destinatarios válidos.")
            return

        (filename, mimetype, file_content,
         preview_results_dicts) = _generate_report_data_and_file(
            reporte_id, current_app.app_context())

        if file_content:
            try:
                subject = f"Reporte Programado: {
                    reporte['nombre']} ({
                    datetime.now().strftime('%Y-%m-%d')})"
                msg = Message(subject, recipients=recipients)

                msg.html = render_template(
                    'email/reporte_programado.html',
                    reporte={
                        'nombre': reporte['nombre'],
                        'descripcion_filtros': reporte['descripcion'] if reporte['descripcion'] else 'Reporte generado automáticamente.'},
                    resultados=preview_results_dicts,
                    now=datetime.now)

                msg.attach(filename, mimetype, file_content)

                mail.send(msg)
                current_app.logger.info(
                    f"Reporte programado '{
                        reporte['nombre']}' ({reporte_id}) enviado a {recipients}.")
            except Exception as e:
                current_app.logger.error(
                    f"Error al enviar reporte programado '{
                        reporte['nombre']}' ({reporte_id}): {e}",
                    exc_info=True)
        else:
            current_app.logger.error(
                f"No se pudo generar el archivo para el reporte programado ID {reporte_id}.")


@admin_bp.route('/usuarios')
@roles_required('ADMINISTRADOR')
def listar_usuarios():
    """Muestra una lista completa de todos los usuarios registrados en el sistema, incluyendo sus roles."""
    db = get_db()

    # PostgreSQL version
    sql = """
        SELECT
            u.id, u.username, u.nombre_completo, u.email, u.activo,
            STRING_AGG(r.nombre, ', ') as roles
        FROM usuarios u
        LEFT JOIN usuario_roles ur ON u.id = ur.usuario_id
        LEFT JOIN roles r ON ur.rol_id = r.id
        GROUP BY u.id
        ORDER BY u.nombre_completo
    """

    cursor = db.cursor()
    cursor.execute(sql)
    usuarios = cursor.fetchall()
    cursor.close()

    log_action(
        'VER_USUARIOS',
        g.user['id'],
        'usuarios',
        None,
        "Visualizó la lista de usuarios.")
    return render_template(
        'admin/usuarios.html',
        usuarios=usuarios,
        titulo="Gestión de Usuarios")


@admin_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def nuevo_usuario():
    """Gestiona la creación de un nuevo usuario usando un formulario seguro de Flask-WTF."""
    form = UserForm()
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('SELECT nombre FROM roles ORDER BY nombre')
        form.roles.choices = [(r['nombre'], r['nombre'])
                              for r in cursor.fetchall()]

        if form.validate_on_submit():
            password_hash = generate_password_hash(form.password.data)

            sql_insert_user = 'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id'
            sql_get_rol = 'SELECT id FROM roles WHERE nombre = %s'
            sql_insert_rol = 'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)'

            params_user = (
                form.username.data,
                form.nombre_completo.data,
                form.email.data,
                password_hash,
                int(form.activo.data))
            cursor.execute(sql_insert_user, params_user)

            new_user_id = cursor.fetchone()['id']

            for rol_nombre in form.roles.data:
                cursor.execute(sql_get_rol, (rol_nombre,))
                rol_id = cursor.fetchone()['id']
                cursor.execute(sql_insert_rol, (new_user_id, rol_id))

            db.commit()
            log_action('CREAR_USUARIO', g.user['id'], 'usuarios', new_user_id,
                       (f"Usuario '{form.username.data}' creado con roles: "
                        f"{', '.join(form.roles.data)}."))
            current_app.logger.info(
                f"Admin '{g.user['username']}' creó el usuario '{form.username.data}'.")
            flash('Usuario creado con éxito.', 'success')
            return redirect(url_for('admin.listar_usuarios'))
    finally:
        cursor.close()

    return render_template(
        'admin/usuario_form.html',
        form=form,
        titulo="Nuevo Usuario")


@admin_bp.route('/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def editar_usuario(usuario_id):
    """Gestiona la edición de un usuario existente."""
    db = get_db()
    cursor = db.cursor()

    try:
        # Definir consultas seguras y portables
        sql_get_user = "SELECT * FROM usuarios WHERE id = %s"
        sql_get_all_roles = "SELECT nombre FROM roles ORDER BY nombre"
        sql_update_user = "UPDATE usuarios SET username = %s, nombre_completo = %s, email = %s, activo = %s WHERE id = %s"
        sql_update_pass = "UPDATE usuarios SET password_hash = %s WHERE id = %s"
        sql_get_user_roles = "SELECT r.nombre FROM roles r JOIN usuario_roles ur ON r.id = ur.rol_id WHERE ur.usuario_id = %s"
        sql_delete_user_roles = "DELETE FROM usuario_roles WHERE usuario_id = %s"
        sql_get_rol_id = "SELECT id FROM roles WHERE nombre = %s"
        sql_insert_user_role = "INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)"

        cursor.execute(sql_get_user, (usuario_id,))
        usuario = cursor.fetchone()
        if not usuario:
            abort(404)

        form = UserForm(
            obj=usuario,
            original_username=usuario['username'],
            original_email=usuario['email'])

        cursor.execute(sql_get_all_roles)
        all_roles = cursor.fetchall()
        form.roles.choices = [(r['nombre'], r['nombre']) for r in all_roles]

        if form.validate_on_submit():
            old_data = dict(usuario)

            cursor.execute(
                sql_update_user,
                (form.username.data,
                 form.nombre_completo.data,
                 form.email.data,
                 int(form.activo.data),
                 usuario_id))

            changes = {k: {'old': old_data[k],
                           'new': getattr(form,
                                          k).data} for k in ['username',
                       'nombre_completo',
                                                             'email',
                                                             'activo'] if getattr(form,
                                                                                  k).data != old_data[k]}

            if form.password.data:
                cursor.execute(
                    sql_update_pass,
                    (generate_password_hash(
                        form.password.data),
                        usuario_id))
                changes['password'] = 'changed'

            cursor.execute(sql_get_user_roles, (usuario_id,))
            current_roles = {row['nombre'] for row in cursor.fetchall()}
            new_roles = set(form.roles.data)

            if current_roles != new_roles:
                changes['roles'] = {
                    'old': list(current_roles),
                    'new': list(new_roles)}
                cursor.execute(sql_delete_user_roles, (usuario_id,))
                for rol_nombre in new_roles:
                    cursor.execute(sql_get_rol_id, (rol_nombre,))
                    rol_id = cursor.fetchone()['id']
                    cursor.execute(sql_insert_user_role, (usuario_id, rol_id))

            db.commit()
            if changes:
                log_action(
                    'EDITAR_USUARIO', g.user['id'], 'usuarios', usuario_id,
                    (f"Usuario '{old_data['username']}' editado. "
                     f"Cambios: {json.dumps(changes)}."))
            flash('Usuario actualizado con éxito.', 'success')
            return redirect(url_for('admin.listar_usuarios'))

        elif request.method == 'GET':
            form.username.data = usuario['username']
            form.nombre_completo.data = usuario['nombre_completo']
            form.email.data = usuario['email']
            form.activo.data = usuario['activo']

            cursor.execute(sql_get_user_roles, (usuario_id,))
            form.roles.data = [row['nombre'] for row in cursor.fetchall()]

    finally:
        cursor.close()

    return render_template(
        'admin/usuario_form.html',
        form=form,
        usuario=usuario,
        titulo="Editar Usuario")


@admin_bp.route('/usuarios/<int:usuario_id>/toggle_activo', methods=['POST'])
@roles_required('ADMINISTRADOR')
def toggle_activo(usuario_id):
    """Activa o desactiva una cuenta de usuario."""
    if usuario_id == g.user['id']:
        flash('No puedes desactivar tu propia cuenta.', 'danger')
        return redirect(url_for('admin.listar_usuarios'))

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            'SELECT activo, username FROM usuarios WHERE id = %s', (usuario_id,))
        usuario = cursor.fetchone()
        if usuario:
            nuevo_estado = not usuario['activo']
            cursor.execute(
                'UPDATE usuarios SET activo = %s WHERE id = %s',
                (nuevo_estado,
                 usuario_id))
            db.commit()
            estado_texto = 'activado' if nuevo_estado else 'desactivado'
            log_action('TOGGLE_USUARIO_ACTIVO', g.user['id'], 'usuarios',
                       usuario_id, f"Usuario '{usuario['username']}' ha sido {estado_texto}.")
            current_app.logger.info(
                f"Admin '{g.user['username']}' ha {estado_texto} al usuario '{usuario['username']}'.")
            flash(f"El usuario ha sido {estado_texto}.", 'success')
        else:
            flash("Usuario no encontrado.", "danger")
    finally:
        cursor.close()

    return redirect(url_for('admin.listar_usuarios'))


@admin_bp.route('/usuarios/<int:usuario_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_usuario(usuario_id):
    """Elimina un usuario (solo para administradores)."""
    db = get_db()
    cursor = db.cursor()

    try:
        if usuario_id == g.user['id']:
            flash('No puedes eliminar tu propia cuenta.', 'danger')
            return redirect(url_for('admin.listar_usuarios'))

        # Comprobar si el usuario es administrador
        sql_is_admin = "SELECT 1 FROM usuario_roles ur JOIN roles r ON ur.rol_id = r.id WHERE ur.usuario_id = %s AND r.nombre = 'ADMINISTRADOR'"
        cursor.execute(sql_is_admin, (usuario_id,))
        is_admin_query = cursor.fetchone()

        if is_admin_query:
            sql_admin_count = "SELECT COUNT(ur.usuario_id) as admin_count FROM usuario_roles ur JOIN roles r ON ur.rol_id = r.id WHERE r.nombre = 'ADMINISTRADOR'"
            cursor.execute(sql_admin_count)
            admin_count_query = cursor.fetchone()
            if admin_count_query and admin_count_query['admin_count'] <= 1:
                flash(
                    'No se puede eliminar al último administrador del sistema.',
                    'danger')
                return redirect(url_for('admin.listar_usuarios'))

        # Comprobar si está asignado a proyectos
        sql_proyectos = "SELECT COUNT(proyecto_id) as count FROM proyecto_usuarios WHERE usuario_id = %s"
        cursor.execute(sql_proyectos, (usuario_id,))
        proyectos_asignados = cursor.fetchone()
        if proyectos_asignados and proyectos_asignados['count'] > 0:
            flash(
                f"No se puede eliminar al usuario porque está asignado a {
                    proyectos_asignados['count']} proyecto(s).",
                'danger')
            return redirect(url_for('admin.listar_usuarios'))

        # Comprobar si tiene conexiones activas
        sql_conexiones = "SELECT COUNT(id) as count FROM conexiones WHERE realizador_id = %s AND estado IN ('EN_PROCESO', 'REALIZADO')"
        cursor.execute(sql_conexiones, (usuario_id,))
        conexiones_activas = cursor.fetchone()
        if conexiones_activas and conexiones_activas['count'] > 0:
            flash(
                f"No se puede eliminar al usuario porque tiene {
                    conexiones_activas['count']} conexión(es) activa(s) asignada(s).",
                'danger')
            return redirect(url_for('admin.listar_usuarios'))

        # Eliminar el usuario
        sql_get_user = 'SELECT username FROM usuarios WHERE id = %s'
        cursor.execute(sql_get_user, (usuario_id,))
        usuario = cursor.fetchone()
        if usuario:
            sql_delete_user = 'DELETE FROM usuarios WHERE id = %s'
            cursor.execute(sql_delete_user, (usuario_id,))
            db.commit()
            log_action('ELIMINAR_USUARIO', g.user['id'], 'usuarios',
                       usuario_id, f"Usuario '{usuario['username']}' eliminado.")
            flash(
                f"El usuario '{usuario['username']}' ha sido eliminado.", 'success')
        else:
            flash("Usuario no encontrado.", "danger")
    finally:
        cursor.close()

    return redirect(url_for('admin.listar_usuarios'))


@admin_bp.route('/proyectos/<int:proyecto_id>/permisos',
                methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def gestionar_permisos_proyecto(proyecto_id):
    """Gestiona qué usuarios tienen acceso a un proyecto específico."""
    db = get_db()
    cursor = db.cursor()

    try:
        sql_get_proyecto = 'SELECT * FROM proyectos WHERE id = %s'
        cursor.execute(sql_get_proyecto, (proyecto_id,))
        proyecto = cursor.fetchone()
        if not proyecto:
            abort(404)

        form = FlaskForm()

        if form.validate_on_submit():
            usuarios_asignados = request.form.getlist('usuarios_asignados')

            sql_get_assigned = 'SELECT usuario_id FROM proyecto_usuarios WHERE proyecto_id = %s'
            cursor.execute(sql_get_assigned, (proyecto_id,))
            current_assigned_users_ids = {
                row['usuario_id'] for row in cursor.fetchall()}
            new_assigned_users_ids = {int(uid) for uid in usuarios_asignados}

            sql_delete_perm = 'DELETE FROM proyecto_usuarios WHERE proyecto_id = %s'
            cursor.execute(sql_delete_perm, (proyecto_id,))

            sql_insert_perm = 'INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (%s, %s)'
            for user_id in usuarios_asignados:
                cursor.execute(sql_insert_perm, (proyecto_id, int(user_id)))
            db.commit()

            if current_assigned_users_ids != new_assigned_users_ids:
                changes = {
                    'usuarios_asignados': {
                        'old': list(current_assigned_users_ids),
                        'new': list(new_assigned_users_ids)}}
                log_action('ACTUALIZAR_PERMISOS_PROYECTO', g.user['id'], 'proyectos',
                           proyecto_id, (f"Permisos del proyecto '{proyecto['nombre']}' "
                                         f"actualizados. Cambios: {json.dumps(changes)}."))
            flash('Permisos del proyecto actualizados con éxito.', 'success')
            return redirect(
                url_for(
                    'admin.gestionar_permisos_proyecto',
                    proyecto_id=proyecto_id))

        sql_get_all_users = 'SELECT id, nombre_completo FROM usuarios WHERE activo = 1 ORDER BY nombre_completo'
        cursor.execute(sql_get_all_users)
        todos_usuarios = cursor.fetchall()

        sql_get_access = 'SELECT usuario_id FROM proyecto_usuarios WHERE proyecto_id = %s'
        cursor.execute(sql_get_access, (proyecto_id,))
        usuarios_con_acceso = {row['usuario_id']
                               for row in cursor.fetchall()}

        log_action('VER_PERMISOS_PROYECTO', g.user['id'], 'proyectos',
                   proyecto_id, f"Visualizó permisos del proyecto '{proyecto['nombre']}'.")
    finally:
        cursor.close()

    return render_template('admin/proyecto_permisos.html',
                           proyecto=proyecto,
                           todos_usuarios=todos_usuarios,
                           usuarios_con_acceso=usuarios_con_acceso,
                           titulo=f"Permisos para {proyecto['nombre']}",
                           form=form)


@admin_bp.route('/alias', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def gestionar_alias():
    """Gestiona la creación y listado de alias para perfiles."""
    form = AliasForm()
    db = get_db()
    cursor = db.cursor()

    try:
        if form.validate_on_submit():
            nombre_perfil = form.nombre_perfil.data
            alias = form.alias.data
            norma = form.norma.data

            sql_check = 'SELECT id FROM alias_perfiles WHERE nombre_perfil = %s OR alias = %s'
            cursor.execute(sql_check, (nombre_perfil, alias))
            existe = cursor.fetchone()

            if existe:
                flash('El nombre del perfil o el alias ya existen.', 'danger')
            else:
                sql_insert = 'INSERT INTO alias_perfiles (nombre_perfil, alias, norma) VALUES (%s, %s, %s) RETURNING id'
                cursor.execute(sql_insert, (nombre_perfil, alias, norma))

                new_alias_id = cursor.fetchone()['id']
                db.commit()
                log_action(
                    'CREAR_ALIAS_PERFIL', g.user['id'], 'alias_perfiles', new_alias_id,
                    f"Alias '{alias}' para perfil '{nombre_perfil}' (Norma: {norma}) creado.")
                flash('Alias guardado con éxito.', 'success')
            return redirect(url_for('admin.gestionar_alias'))

        cursor.execute('SELECT * FROM alias_perfiles ORDER BY nombre_perfil')
        aliases = cursor.fetchall()
        log_action('VER_ALIAS_PERFILES', g.user['id'], 'alias_perfiles',
                   None, "Visualizó la gestión de alias de perfiles.")
    finally:
        cursor.close()

    return render_template(
        'admin/alias_manager.html',
        aliases=aliases,
        form=form,
        titulo="Gestión de Alias de Perfiles")


@admin_bp.route('/alias/<int:alias_id>/editar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def editar_alias(alias_id):
    """Procesa la actualización de un alias existente."""
    nombre_perfil = request.form.get('nombre_perfil')
    alias = request.form.get('alias')
    norma = request.form.get('norma')
    db = get_db()
    cursor = db.cursor()

    try:
        sql_get_old = 'SELECT nombre_perfil, alias, norma FROM alias_perfiles WHERE id = %s'
        cursor.execute(sql_get_old, (alias_id,))
        old_alias_data = cursor.fetchone()

        sql_check = 'SELECT id FROM alias_perfiles WHERE (nombre_perfil = %s OR alias = %s) AND id != %s'
        cursor.execute(sql_check, (nombre_perfil, alias, alias_id))
        existe = cursor.fetchone()

        if existe:
            flash(
                'El nombre del perfil o el alias ya están en uso por otro registro.',
                'danger')
        else:
            sql_update = 'UPDATE alias_perfiles SET nombre_perfil = %s, alias = %s, norma = %s WHERE id = %s'
            cursor.execute(sql_update, (nombre_perfil, alias, norma, alias_id))
            db.commit()

            changes = {k: {'old': old_alias_data[k], 'new': v} for k, v in [
                ('nombre_perfil', nombre_perfil), ('alias', alias), ('norma', norma)] if old_alias_data[k] != v}
            if changes:
                log_action(
                    'EDITAR_ALIAS_PERFIL', g.user['id'], 'alias_perfiles', alias_id,
                    (f"Alias '{old_alias_data['alias']}' editado. "
                     f"Cambios: {json.dumps(changes)}."))
            flash('Alias actualizado con éxito.', 'success')
    finally:
        cursor.close()

    return redirect(url_for('admin.gestionar_alias'))


@admin_bp.route('/alias/<int:alias_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_alias(alias_id):
    """Elimina un alias de perfil existente."""
    db = get_db()
    cursor = db.cursor()

    try:
        sql_get = 'SELECT nombre_perfil, alias, norma FROM alias_perfiles WHERE id = %s'
        cursor.execute(sql_get, (alias_id,))
        alias_data = cursor.fetchone()

        if alias_data:
            sql_delete = 'DELETE FROM alias_perfiles WHERE id = %s'
            cursor.execute(sql_delete, (alias_id,))
            db.commit()
            log_action('ELIMINAR_ALIAS_PERFIL', g.user['id'], 'alias_perfiles', alias_id,
                       (f"Alias '{alias_data['alias']}' (Norma: {alias_data['norma']}) "
                        f"para perfil '{alias_data['nombre_perfil']}' eliminado."))
            flash('Alias eliminado con éxito.', 'success')
        else:
            flash('Alias no encontrado.', 'danger')
    finally:
        cursor.close()

    return redirect(url_for('admin.gestionar_alias'))


@admin_bp.route('/alias/importar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def importar_alias():
    """
    Gestiona la importación masiva de alias de perfiles desde un archivo Excel/CSV.
    """
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()

        try:
            if 'archivo_alias' not in request.files or not request.files['archivo_alias'].filename:
                flash('No se seleccionó ningún archivo para importar.', 'danger')
                return redirect(request.url)

            file = request.files['archivo_alias']
            filename = secure_filename(file.filename)

            if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
                flash(
                    'Formato de archivo no válido. Sube un archivo .xlsx o .csv.',
                    'warning')
                return redirect(request.url)

            imported_count = 0
            updated_count = 0
            error_rows = []

            df = pd.read_excel(file, engine='openpyxl') if filename.endswith(
                '.xlsx') else pd.read_csv(file)

            required_cols = ['NOMBRE_PERFIL', 'ALIAS', 'NORMA']
            df.columns = [col.upper().strip() for col in df.columns]

            if not all(col in df.columns for col in required_cols):
                flash(
                    'El archivo debe contener las columnas: NOMBRE_PERFIL, ALIAS, NORMA.',
                    'danger')
                return redirect(request.url)

            # Definir SQL fuera del bucle
            sql_check = 'SELECT id FROM alias_perfiles WHERE nombre_perfil = %s'
            sql_update = 'UPDATE alias_perfiles SET alias = %s, norma = %s WHERE id = %s'
            sql_insert = 'INSERT INTO alias_perfiles (nombre_perfil, alias, norma) VALUES (%s, %s, %s)'

            for index, row in df.iterrows():
                try:
                    nombre_perfil = str(row.get('NOMBRE_PERFIL', '')).strip()
                    alias = str(row.get('ALIAS', '')).strip()
                    norma = str(row.get('NORMA', '')).strip()
                    if norma == 'nan':
                        norma = ''

                    if not nombre_perfil or not alias:
                        error_rows.append(
                            f"Fila {
                                index +
                                2}: NOMBRE_PERFIL y ALIAS son obligatorios.")
                        continue

                    cursor.execute(sql_check, (nombre_perfil,))
                    existing_alias = cursor.fetchone()

                    if existing_alias:
                        cursor.execute(
                            sql_update, (alias, norma, existing_alias['id']))
                        updated_count += 1
                    else:
                        cursor.execute(
                            sql_insert, (nombre_perfil, alias, norma))
                        imported_count += 1
                except Exception as row_e:
                    error_rows.append(
                        f"Fila {index + 2}: Error al procesar - {row_e}")

            db.commit()

            # Lógica de mensajes flash...
            msg_parts = []
            if imported_count > 0:
                msg_parts.append(f"Se crearon {imported_count} nuevos alias.")
            if updated_count > 0:
                msg_parts.append(
                    f"Se actualizaron {updated_count} alias existentes.")
            if msg_parts:
                flash(
                    "Importación completada: " +
                    " ".join(msg_parts),
                    'success')
            if error_rows:
                flash(f"Errores en {len(error_rows)} fila(s): " +
                      "; ".join(error_rows[:5]), 'danger')

        except pd.errors.EmptyDataError:
            flash('El archivo está vacío.', 'danger')
        except Exception as e:
            flash(f"Ocurrió un error inesperado: {e}", "danger")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()

        return redirect(url_for('admin.gestionar_alias'))

    return render_template(
        'admin/importar_alias.html',
        titulo="Importar Alias de Perfiles")


@admin_bp.route('/eficiencia')
@roles_required('ADMINISTRADOR')
def eficiencia():
    """Calcula y muestra métricas de rendimiento y KPIs para el proceso de conexiones."""
    db = get_db()

    avg_time_query = db.execute("""
        SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_days
        FROM historial_estados h1
        JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id
        WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'
    """).fetchone()
    avg_approval_time = avg_time_query['avg_days'] if avg_time_query and avg_time_query['avg_days'] is not None else 0
    if isinstance(avg_approval_time, (int, float)):
        avg_approval_time = f"{avg_approval_time:.1f} días"
    else:
        avg_approval_time = 'N/A'

    processed_last_30d_row = db.execute(
        "SELECT COUNT(id) as total FROM conexiones WHERE fecha_modificacion >= date('now', '-30 days') AND estado = 'APROBADO'").fetchone()
    processed_last_30d = processed_last_30d_row['total'] if processed_last_30d_row else 0

    total_approved_row = db.execute(
        "SELECT COUNT(id) as total FROM conexiones WHERE estado = 'APROBADO'").fetchone()
    total_approved = total_approved_row['total'] if total_approved_row else 0

    total_rejected_history_row = db.execute(
        "SELECT COUNT(DISTINCT conexion_id) as total FROM historial_estados WHERE estado = 'RECHAZADO'").fetchone()
    total_rejected_history = total_rejected_history_row['total'] if total_rejected_history_row else 0

    rejection_rate = (total_rejected_history /
                      (total_approved +
                       total_rejected_history) *
                      100) if (total_approved +
                               total_rejected_history) > 0 else 0
    if isinstance(rejection_rate, (int, float)):
        rejection_rate = f"{rejection_rate:.1f}%"
    else:
        rejection_rate = '0.0%'

    kpis = {
        'avg_approval_time': avg_approval_time,
        'processed_in_range': processed_last_30d,
        'rejection_rate': rejection_rate
    }

    time_by_state = {'Solicitado': 8.5, 'En Proceso': 48.2, 'Realizado': 24.0}
    completed_by_user = db.execute(
        "SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.realizador_id = u.id WHERE c.estado = 'APROBADO' AND c.fecha_modificacion >= date('now', '-30 days') GROUP BY u.id ORDER BY total DESC").fetchall()

    charts_data = {'time_by_state': time_by_state,
                   'completed_by_user': [{'user': row['nombre_completo'],
                                          'total': row['total']} for row in completed_by_user]}

    filters = {
        'start': (
            datetime.now() -
            timedelta(
                days=30)).strftime('%Y-%m-%d'),
        'end': datetime.now().strftime('%Y-%m-%d')}

    slow_connections = db.execute("""
        SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre,
               u.nombre_completo as realizador_nombre,
               (julianday('now') - julianday(c.fecha_modificacion)) as dias_en_proceso
        FROM conexiones c
        JOIN proyectos p ON c.proyecto_id = p.id
        LEFT JOIN usuarios u ON c.realizador_id = u.id
        WHERE c.estado = 'EN_PROCESO'
        ORDER BY dias_en_proceso DESC
        LIMIT 5
    """).fetchall()

    log_action(
        'VER_EFICIENCIA',
        g.user['id'],
        'sistema',
        None,
        "Visualizó el panel de eficiencia.")
    return render_template('admin/eficiencia.html',
                           titulo="Análisis de Eficiencia",
                           kpis=kpis,
                           charts_data=charts_data,
                           slow_connections=slow_connections,
                           filters=filters)


@admin_bp.route('/logs')
@roles_required('ADMINISTRADOR')
def logs():
    """Página para visualizar los logs del sistema."""
    logs_path = os.path.join(
        current_app.root_path,
        'logs',
        'heptaconexiones.log')
    log_entries = []
    try:
        with open(logs_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-100:]
            lines.reverse()
            for line in lines:
                match = re.match(
                    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+): (.*)', line)
                if match:
                    log_entries.append({
                        'timestamp': match.group(1),
                        'level': match.group(2),
                        'message': match.group(3)
                    })
    except FileNotFoundError:
        flash(
            "No se encontró el archivo de log. Puede que aún no se haya generado.",
            "info")

    log_action(
        'VER_LOGS',
        g.user['id'],
        'sistema',
        None,
        "Visualizó los logs del sistema.")
    return render_template(
        'admin/logs.html',
        logs=log_entries,
        titulo="Logs del Sistema")


@admin_bp.route('/logs/clear', methods=['POST'])
@roles_required('ADMINISTRADOR')
def clear_logs():
    """Limpia el contenido del archivo de log."""
    logs_path = os.path.join(
        current_app.root_path,
        'logs',
        'heptaconexiones.log')
    try:
        with open(logs_path, 'w') as f:
            pass
        log_action('LIMPIAR_LOGS', g.user['id'], 'sistema',
                   None, "Limpió el archivo de logs.")
        current_app.logger.warning(
            f"Admin '{g.user['username']}' ha limpiado el archivo de logs.")
        flash("El archivo de logs ha sido limpiado con éxito.", 'success')
    except Exception as e:
        current_app.logger.error(
            f"Error al intentar limpiar el archivo de logs: {e}")
        flash("Ocurrió un error al intentar limpiar el archivo de logs.", 'danger')

    return redirect(url_for('admin.logs'))


@admin_bp.route('/auditoria')
@roles_required('ADMINISTRADOR')
def ver_auditoria():
    """Muestra el historial de auditoría de acciones en el sistema."""
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['PER_PAGE']
    offset = (page - 1) * per_page

    filtro_usuario_id = request.args.get('usuario_id', type=int)
    filtro_accion = request.args.get('accion')

    query = "SELECT a.*, u.nombre_completo as usuario_nombre FROM auditoria_acciones a JOIN usuarios u ON a.usuario_id = u.id WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM auditoria_acciones a JOIN usuarios u ON a.usuario_id = u.id WHERE 1=1"
    params = []

    if filtro_usuario_id:
        query += " AND a.usuario_id = %s"
        count_query += " AND a.usuario_id = %s"
        params.append(filtro_usuario_id)
    if filtro_accion:
        query += " AND a.accion = %s"
        count_query += " AND a.accion = %s"
        params.append(filtro_accion)

    query += " ORDER BY a.fecha DESC LIMIT %s OFFSET %s"

    params_count = params[:]

    params.extend([per_page, offset])

    acciones = db.execute(query, tuple(params)).fetchall()
    total_acciones = db.execute(count_query, tuple(params_count)).fetchone()[0]

    usuarios_para_filtro = db.execute(
        'SELECT id, nombre_completo FROM usuarios ORDER BY nombre_completo').fetchall()
    acciones_para_filtro = db.execute(
        'SELECT DISTINCT accion FROM auditoria_acciones ORDER BY accion').fetchall()

    log_action(
        'VER_AUDITORIA',
        g.user['id'],
        'sistema',
        None,
        "Visualizó el historial de auditoría.")
    return render_template('admin/auditoria.html',
                           acciones=acciones,
                           usuarios_para_filtro=usuarios_para_filtro,
                           acciones_para_filtro=acciones_para_filtro,
                           filtro_usuario_id=filtro_usuario_id,
                           filtro_accion=filtro_accion,
                           page=page,
                           per_page=per_page,
                           total=total_acciones,
                           titulo="Historial de Auditoría")


@admin_bp.route('/storage')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def storage_management():
    """Muestra estadísticas de uso de almacenamiento y herramientas de gestión."""
    uploads_path = current_app.config['UPLOAD_FOLDER']
    total_size_bytes = 0
    num_files = 0
    files_by_ext = defaultdict(int)

    try:
        for dirpath, dirnames, filenames in os.walk(uploads_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    size = os.path.getsize(fp)
                    total_size_bytes += size
                    num_files += 1
                    ext = os.path.splitext(f)[1].lower()
                    files_by_ext[ext if ext else "sin_extension"] += 1

    except Exception as e:
        current_app.logger.error(
            f"Error al calcular el uso de almacenamiento: {e}")
        flash(f"Error al calcular el uso de almacenamiento: {e}", "danger")

    def format_bytes(size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    log_action(
        'VER_ALMACENAMIENTO',
        g.user['id'],
        'sistema',
        None,
        "Visualizó la gestión de almacenamiento.")
    return render_template('admin/storage.html',
                           titulo="Gestión de Almacenamiento",
                           total_size=format_bytes(total_size_bytes),
                           num_files=num_files,
                           files_by_ext=dict(files_by_ext))


def _generate_computos_file(
        report_data,
        gran_total,
        file_format,
        filtros,
        proyecto_nombre_filtro):
    """
    Genera un archivo (PDF o XLSX) a partir de los datos del reporte de cómputos.
    """
    filename_base = f"reporte_computos_{datetime.now().strftime('%Y%m%d')}"

    if file_format == 'xlsx':
        records = []
        for proyecto, data in report_data.items():
            for perfil, p_data in data['perfiles'].items():
                records.append({
                    'Proyecto': proyecto,
                    'Perfil': perfil,
                    'Cantidad': p_data['cantidad'],
                    'Peso Total (kg)': p_data['peso_total']
                })

        df = pd.DataFrame(records)
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')

        file_content = output.getvalue()
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{filename_base}.xlsx"
        return filename, mimetype, file_content

    elif file_format == 'pdf':
        rendered_html = render_template(
            'admin/reporte_computos_agregado.html',
            report_data=report_data,
            gran_total_peso=gran_total,
            proyecto_nombre_filtro=proyecto_nombre_filtro,
            filtros=filtros,
            titulo="Reporte de Cómputos Métricos")

        pdf_bytes = HTML(
            string=rendered_html,
            base_url=request.base_url).write_pdf()
        mimetype = "application/pdf"
        filename = f"{filename_base}.pdf"
        return filename, mimetype, pdf_bytes

    return None, None, None


@admin_bp.route('/reportes/computos', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def reporte_computos():
    form_data = request.args if request.method == 'GET' else request.form
    form = ComputosReportForm(form_data)

    db = get_db()
    proyectos = db.execute(
        'SELECT id, nombre FROM proyectos ORDER BY nombre').fetchall()
    form.proyecto_id.choices = [(0,
                                 'Todos los Proyectos')] + [(p['id'],
                                                             p['nombre']) for p in proyectos]

    if form_data and form.validate():
        proyecto_id = form.proyecto_id.data
        fecha_inicio = form.fecha_inicio.data
        fecha_fin = form.fecha_fin.data

        query = "SELECT c.detalles_json, p.nombre as proyecto_nombre FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.detalles_json IS NOT NULL AND c.detalles_json != ''"
        params = []
        if proyecto_id != 0:
            query += " AND c.proyecto_id = %s"
            params.append(proyecto_id)
        if fecha_inicio:
            query += " AND date(c.fecha_creacion) >= %s"
            params.append(fecha_inicio.strftime('%Y-%m-%d'))
        if fecha_fin:
            query += " AND date(c.fecha_creacion) <= %s"
            params.append(fecha_fin.strftime('%Y-%m-%d'))

        conexiones = db.execute(query, tuple(params)).fetchall()

        if not conexiones and request.method == 'POST':
            flash(
                "No se encontraron conexiones con datos computables para los filtros seleccionados.",
                "info")
            return redirect(url_for('admin.reporte_computos'))

        report_data = defaultdict(
            lambda: {
                'perfiles': defaultdict(
                    lambda: {
                        'cantidad': 0,
                        'peso_total': 0.0}),
                'peso_total_proyecto': 0.0})
        gran_total_peso = 0.0

        def process_element(element, proyecto_nombre):
            nonlocal gran_total_peso
            if isinstance(
                    element,
                    dict) and 'perfil' in element and 'longitud' in element:
                nombre_perfil = element.get('perfil')
                longitud_mm = element.get('longitud')
                cantidad = element.get('cantidad', 1)
                if not nombre_perfil or not longitud_mm:
                    return
                try:
                    longitud_mm = float(longitud_mm)
                    cantidad = int(cantidad)
                except (ValueError, TypeError):
                    return

                peso_total_elemento = calcular_peso_perfil(
                    nombre_perfil, longitud_mm) * cantidad
                report_data[proyecto_nombre]['perfiles'][nombre_perfil]['cantidad'] += cantidad
                report_data[proyecto_nombre]['perfiles'][nombre_perfil]['peso_total'] += peso_total_elemento
                report_data[proyecto_nombre]['peso_total_proyecto'] += peso_total_elemento
                gran_total_peso += peso_total_elemento

        for conexion in conexiones:
            try:
                detalles = json.loads(conexion['detalles_json'])
                for value in detalles.values():
                    if isinstance(value, dict):
                        process_element(value, conexion['proyecto_nombre'])
                    elif isinstance(value, list):
                        for item in value:
                            process_element(item, conexion['proyecto_nombre'])
            except (json.JSONDecodeError, TypeError):
                continue

        for data in report_data.values():
            data['peso_total_proyecto'] = round(data['peso_total_proyecto'], 2)
            for p_data in data['perfiles'].values():
                p_data['peso_total'] = round(p_data['peso_total'], 2)
        gran_total_peso = round(gran_total_peso, 2)

        proyecto_nombre_filtro = "Todos los Proyectos"
        if proyecto_id != 0:
            p = db.execute(
                'SELECT nombre FROM proyectos WHERE id = %s',
                (proyecto_id,
                 )).fetchone()
            if p:
                proyecto_nombre_filtro = p['nombre']

        file_format = request.args.get('format')
        if file_format in ['pdf', 'xlsx']:
            filename, mimetype, content = _generate_computos_file(
                dict(report_data), gran_total_peso, file_format, form.data, proyecto_nombre_filtro)
            if content:
                response = make_response(content)
                response.headers["Content-Disposition"] = f"attachment; filename={filename}"
                response.headers["Content-Type"] = mimetype
                return response
            else:
                flash("Error al generar el archivo descargable.", "danger")
                return redirect(url_for('admin.reporte_computos'))

        if request.method == 'POST':
            log_action(
                'GENERAR_REPORTE_COMPUTOS',
                g.user['id'],
                'reportes',
                proyecto_id,
                f"Generó reporte de cómputos para proyecto ID: {proyecto_id}")
            return render_template(
                'admin/reporte_computos_agregado.html',
                report_data=dict(report_data),
                gran_total_peso=gran_total_peso,
                filtros=form.data,
                proyecto_nombre_filtro=proyecto_nombre_filtro,
                titulo="Resultados del Reporte de Cómputos Métricos")

    log_action(
        'VER_REPORTE_COMPUTOS_FORM',
        g.user['id'],
        'reportes',
        None,
        "Visualizó el formulario de reporte de cómputos.")
    return render_template(
        'admin/reporte_computos_form.html',
        form=form,
        titulo="Reporte de Cómputos Métricos")


@admin_bp.route('/reportes')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def listar_reportes():
    """Página para la gestión de reportes."""
    db = get_db()
    reportes = db.execute(
        "SELECT r.*, u.nombre_completo as creador_nombre FROM reportes r JOIN usuarios u ON r.creador_id = u.id ORDER BY r.nombre").fetchall()
    log_action(
        'VER_REPORTES',
        g.user['id'],
        'reportes',
        None,
        "Visualizó la lista de reportes.")
    return render_template('admin/reportes.html',
                           reportes=reportes,
                           titulo="Gestión de Reportes")


@admin_bp.route('/reportes/nuevo', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def nuevo_reporte():
    """Gestiona la creación de un nuevo reporte personalizado."""
    form = ReportForm()
    db = get_db()

    proyectos = db.execute(
        'SELECT id, nombre FROM proyectos ORDER BY nombre').fetchall()
    form.proyecto_id.choices = [(0,
                                 'Todos los Proyectos')] + [(p['id'],
                                                             p['nombre']) for p in proyectos]

    realizadores = db.execute(
        "SELECT u.id, u.nombre_completo FROM usuarios u JOIN usuario_roles ur ON u.id = ur.usuario_id JOIN roles r ON ur.rol_id = r.id WHERE r.nombre = 'REALIZADOR' ORDER BY u.nombre_completo").fetchall()
    form.realizador_id.choices = [(0,
                                   'Todos los Realizadores')] + [(r['id'],
                                                                  r['nombre_completo']) for r in realizadores]

    if form.validate_on_submit():
        filtros = {
            'proyecto_id': form.proyecto_id.data,
            'estado': form.estado.data,
            'realizador_id': form.realizador_id.data,
            'fecha_inicio': form.fecha_inicio.data.strftime('%Y-%m-%d') if form.fecha_inicio.data else None,
            'fecha_fin': form.fecha_fin.data.strftime('%Y-%m-%d') if form.fecha_fin.data else None,
            'columnas': form.columnas.data,
            'output_format': form.output_format.data}
        filtros_json = json.dumps(filtros)

        cursor = db.execute(
            "INSERT INTO reportes (nombre, descripcion, creador_id, filtros, programado, frecuencia, destinatarios) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (form.nombre.data,
             form.descripcion.data,
             g.user['id'],
                filtros_json,
                form.programado.data,
                form.frecuencia.data,
                form.destinatarios.data))
        new_report_id = cursor.fetchone()['id']
        db.commit()

        if form.programado.data:
            job_id = f"report_{new_report_id}"
            interval_map = {
                'diaria': {'days': 1},
                'semanal': {'weeks': 1},
                'mensual': {'months': 1}
            }
            if form.frecuencia.data in interval_map:
                try:
                    current_app.scheduler.add_job(
                        id=job_id,
                        func='routes.admin:scheduled_report_job',
                        trigger='interval',
                        **interval_map[form.frecuencia.data],
                        args=[new_report_id],
                        replace_existing=True
                    )
                    current_app.logger.info(
                        f"Reporte '{
                            form.nombre.data}' (ID: {new_report_id}) programado con éxito.")
                except Exception as e:
                    current_app.logger.error(
                        f"Error al programar el reporte '{
                            form.nombre.data}': {e}", exc_info=True)
                    flash(
                        f"Error al programar el reporte: {e}. El reporte se guardó pero no se pudo programar.",
                        "warning")

        log_action('CREAR_REPORTE', g.user['id'], 'reportes', new_report_id,
                   f"Reporte '{form.nombre.data}' creado.")
        flash('Reporte guardado con éxito.', 'success')
        return redirect(url_for('admin.listar_reportes'))

    return render_template(
        'admin/reporte_form.html',
        form=form,
        titulo="Nuevo Reporte")


@admin_bp.route('/reportes/<int:reporte_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def editar_reporte(reporte_id):
    """
    Gestiona la edición de un reporte existente.
    """
    db = get_db()
    reporte = db.execute(
        'SELECT * FROM reportes WHERE id = %s',
        (reporte_id,
         )).fetchone()
    if not reporte:
        abort(404)

    form = ReportForm()

    proyectos = db.execute(
        'SELECT id, nombre FROM proyectos ORDER BY nombre').fetchall()
    form.proyecto_id.choices = [(0,
                                 'Todos los Proyectos')] + [(p['id'],
                                                             p['nombre']) for p in proyectos]

    realizadores = db.execute(
        "SELECT u.id, u.nombre_completo FROM usuarios u JOIN usuario_roles ur ON u.id = ur.usuario_id JOIN roles r ON ur.rol_id = r.id WHERE r.nombre = 'REALIZADOR' ORDER BY u.nombre_completo").fetchall()
    form.realizador_id.choices = [(0,
                                   'Todos los Realizadores')] + [(r['id'],
                                                                  r['nombre_completo']) for r in realizadores]

    if request.method == 'GET':
        form.nombre.data = reporte['nombre']
        form.descripcion.data = reporte['descripcion']

        filtros = json.loads(reporte['filtros'])
        form.proyecto_id.data = filtros.get('proyecto_id', 0)
        form.estado.data = filtros.get('estado', '')
        form.realizador_id.data = filtros.get('realizador_id', 0)
        if filtros.get('fecha_inicio'):
            form.fecha_inicio.data = datetime.strptime(
                filtros.get('fecha_inicio'), '%Y-%m-%d').date()
        if filtros.get('fecha_fin'):
            form.fecha_fin.data = datetime.strptime(
                filtros.get('fecha_fin'), '%Y-%m-%d').date()
        form.columnas.data = filtros.get('columnas', [])
        form.output_format.data = filtros.get('output_format', 'csv')

        form.programado.data = reporte['programado']
        form.frecuencia.data = reporte['frecuencia']
        form.destinatarios.data = reporte['destinatarios']

    elif form.validate_on_submit():
        filtros = {
            'proyecto_id': form.proyecto_id.data,
            'estado': form.estado.data,
            'realizador_id': form.realizador_id.data,
            'fecha_inicio': form.fecha_inicio.data.strftime('%Y-%m-%d') if form.fecha_inicio.data else None,
            'fecha_fin': form.fecha_fin.data.strftime('%Y-%m-%d') if form.fecha_fin.data else None,
            'columnas': form.columnas.data,
            'output_format': form.output_format.data}
        filtros_json = json.dumps(filtros)

        db.execute(
            "UPDATE reportes SET nombre = %s, descripcion = %s, filtros = %s, programado = %s, frecuencia = %s, destinatarios = %s WHERE id = %s",
            (form.nombre.data,
             form.descripcion.data,
             filtros_json,
             form.programado.data,
             form.frecuencia.data,
             form.destinatarios.data,
             reporte_id))
        db.commit()

        job_id = f"report_{reporte_id}"
        if form.programado.data:
            interval_map = {
                'diaria': {'days': 1},
                'semanal': {'weeks': 1},
                'mensual': {'months': 1}
            }
            if form.frecuencia.data in interval_map:
                try:
                    current_app.scheduler.add_job(
                        id=job_id,
                        func='routes.admin:scheduled_report_job',
                        trigger='interval',
                        **interval_map[form.frecuencia.data],
                        args=[reporte_id],
                        replace_existing=True
                    )
                    current_app.logger.info(
                        f"Reporte '{
                            form.nombre.data}' (ID: {reporte_id}) reprogramado con éxito.")
                except Exception as e:
                    current_app.logger.error(
                        f"Error al reprogramar el reporte '{
                            form.nombre.data}': {e}", exc_info=True)
                    flash(
                        f"Error al reprogramar el reporte: {e}. El reporte se guardó pero no se pudo programar.",
                        "warning")
        else:
            if current_app.scheduler.get_job(job_id):
                try:
                    current_app.scheduler.remove_job(job_id)
                    current_app.logger.info(
                        f"Job de reporte '{job_id}' desprogramado.")
                except Exception as e:
                    current_app.logger.error(
                        f"Error al desprogramar el job '{job_id}': {e}", exc_info=True)

        log_action('EDITAR_REPORTE', g.user['id'], 'reportes', reporte_id,
                   f"Reporte '{form.nombre.data}' editado.")
        flash('Reporte actualizado con éxito.', 'success')
        return redirect(url_for('admin.listar_reportes'))

    return render_template(
        'admin/reporte_form.html',
        form=form,
        titulo=f"Editar Reporte: {
            reporte['nombre']}")


@admin_bp.route('/reportes/<int:reporte_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_reporte(reporte_id):
    """Elimina un reporte guardado."""
    db = get_db()
    reporte = db.execute(
        'SELECT * FROM reportes WHERE id = %s',
        (reporte_id,
         )).fetchone()
    if reporte:
        job_id = f"report_{reporte_id}"
        if current_app.scheduler.get_job(job_id):
            try:
                current_app.scheduler.remove_job(job_id)
                current_app.logger.info(
                    f"Job de reporte '{job_id}' desprogramado.")
            except Exception as e:
                current_app.logger.error(
                    f"Error al desprogramar el job '{job_id}': {e}", exc_info=True)

        db.execute('DELETE FROM reportes WHERE id = %s', (reporte_id,))
        db.commit()
        log_action('ELIMINAR_REPORTE', g.user['id'], 'reportes', reporte_id,
                   f"El reporte '{reporte['nombre']}' ha sido eliminado.")
        flash(
            f"El reporte '{
                reporte['nombre']}' ha sido eliminado.",
            'success')
    else:
        flash("El reporte no fue encontrado.", 'danger')
    return redirect(url_for('admin.listar_reportes'))


@admin_bp.route('/reportes/<int:reporte_id>/ejecutar')
@roles_required('ADMINISTRADOR')
def ejecutar_reporte(reporte_id):
    """
    Ejecuta un reporte guardado, genera un archivo en el formato seleccionado
    y lo envía al navegador para su descarga.
    """
    db = get_db()
    reporte = db.execute(
        'SELECT * FROM reportes WHERE id = %s',
        (reporte_id,
         )).fetchone()
    if not reporte:
        abort(404)

    filename, mimetype, file_content, _ = _generate_report_data_and_file(
        reporte_id, current_app.app_context())

    if not file_content:
        flash(
            "No se pudo generar el reporte. Verifique la configuración o los datos.",
            'danger')
        return redirect(url_for('admin.listar_reportes'))

    log_action('EJECUTAR_REPORTE', g.user['id'], 'reportes', reporte_id,
               f"Reporte '{reporte['nombre']}' ejecutado y descargado.")
    response = make_response(file_content)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = mimetype

    return response


@admin_bp.route('/configuracion', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def configuracion():
    """Página para la configuración del sistema."""
    form = ConfigurationForm()
    db = get_db()

    if form.validate_on_submit():
        old_per_page = db.execute(
            "SELECT valor FROM configuracion WHERE clave = 'PER_PAGE'").fetchone()
        old_maintenance = db.execute(
            "SELECT valor FROM configuracion WHERE clave = 'MAINTENANCE_MODE'").fetchone()

        db.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (%s, %s) ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor", ('PER_PAGE', str(
                form.per_page.data)))
        db.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (%s, %s) ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor",
            ('MAINTENANCE_MODE',
             '1' if form.maintenance_mode.data else '0'))
        db.commit()

        changes = {}
        if old_per_page and str(form.per_page.data) != old_per_page['valor']:
            changes['per_page'] = {
                'old': old_per_page['valor'], 'new': str(
                    form.per_page.data)}
        if old_maintenance and (
                '1' if form.maintenance_mode.data else '0') != old_maintenance['valor']:
            changes['maintenance_mode'] = {
                'old': old_maintenance['valor'], 'new': (
                    '1' if form.maintenance_mode.data else '0')}

        if changes:
            log_action('ACTUALIZAR_CONFIGURACION', g.user['id'], 'sistema', None,
                       f"Configuración del sistema actualizada. Cambios: {json.dumps(changes)}.")

        current_app.config['PER_PAGE'] = form.per_page.data
        current_app.config['MAINTENANCE_MODE'] = form.maintenance_mode.data
        flash('Configuración guardada con éxito.', 'success')
        return redirect(url_for('admin.configuracion'))

    elif request.method == 'GET':
        per_page_row = db.execute(
            "SELECT valor FROM configuracion WHERE clave = 'PER_PAGE'").fetchone()
        maintenance_row = db.execute(
            "SELECT valor FROM configuracion WHERE clave = 'MAINTENANCE_MODE'").fetchone()

        form.per_page.data = int(
            per_page_row['valor']) if per_page_row and per_page_row['valor'].isdigit() else current_app.config.get(
            'PER_PAGE', 10)
        form.maintenance_mode.data = maintenance_row['valor'] == '1' if maintenance_row else False

    log_action('VER_CONFIGURACION', g.user['id'], 'sistema',
               None, "Visualizó la configuración del sistema.")
    return render_template(
        'admin/configuracion.html',
        form=form,
        titulo="Configuración del Sistema")

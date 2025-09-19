from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    g,
    flash,
    abort,
    make_response)
from forms import UserForm, ConfigurationForm, ReportForm, AliasForm, ComputosReportForm
from flask_wtf import FlaskForm
from dal.sqlite_dal import SQLiteDAL
import services.user_service as user_s
import services.report_service as report_s
import services.alias_service as alias_s
import services.system_service as system_s
from . import roles_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/usuarios')
@roles_required('ADMINISTRADOR')
def listar_usuarios():
    usuarios = user_s.get_all_users_with_roles()
    return render_template('admin/usuarios.html', usuarios=usuarios, titulo="Gestión de Usuarios")

@admin_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def nuevo_usuario():
    form = UserForm()
    dal = SQLiteDAL()
    form.roles.choices = [(r['nombre'], r['nombre']) for r in dal.get_roles()]
    if form.validate_on_submit():
        success, message = user_s.create_user(form)
        if success:
            flash(message, 'success')
            return redirect(url_for('admin.listar_usuarios'))
        else:
            flash(message, 'danger')
    return render_template('admin/usuario_form.html', form=form, titulo="Nuevo Usuario")

@admin_bp.route('/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def editar_usuario(usuario_id):
    usuario, roles = user_s.get_user_for_edit(usuario_id)
    if not usuario:
        abort(404)

    form = UserForm(obj=usuario, original_username=usuario['username'], original_email=usuario['email'])
    dal = SQLiteDAL()
    form.roles.choices = [(r['nombre'], r['nombre']) for r in dal.get_roles()]

    if form.validate_on_submit():
        success, message = user_s.update_user(usuario_id, form, g.user['id'])
        if success:
            flash(message, 'success')
            return redirect(url_for('admin.listar_usuarios'))
        else:
            flash(message, 'danger')

    if request.method == 'GET':
        form.username.data = usuario['username']
        form.nombre_completo.data = usuario['nombre_completo']
        form.email.data = usuario['email']
        form.activo.data = usuario['activo']
        form.roles.data = roles

    return render_template('admin/usuario_form.html', form=form, usuario=usuario, titulo="Editar Usuario")

@admin_bp.route('/usuarios/<int:usuario_id>/toggle_activo', methods=['POST'])
@roles_required('ADMINISTRADOR')
def toggle_activo(usuario_id):
    success, message = user_s.toggle_user_active_status(usuario_id, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.listar_usuarios'))

@admin_bp.route('/usuarios/<int:usuario_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_usuario(usuario_id):
    success, message = user_s.delete_user(usuario_id, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.listar_usuarios'))

@admin_bp.route('/alias', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def gestionar_alias():
    form = AliasForm()
    if form.validate_on_submit():
        success, message = alias_s.create_alias(form, g.user['id'])
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('admin.gestionar_alias'))

    aliases = alias_s.get_all_aliases()
    return render_template('admin/alias_manager.html', aliases=aliases, form=form, titulo="Gestión de Alias de Perfiles")

@admin_bp.route('/alias/<int:alias_id>/editar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def editar_alias(alias_id):
    success, message = alias_s.update_alias(alias_id, request.form, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.gestionar_alias'))

@admin_bp.route('/alias/<int:alias_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_alias(alias_id):
    success, message = alias_s.delete_alias(alias_id, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.gestionar_alias'))

@admin_bp.route('/alias/importar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def importar_alias():
    if request.method == 'POST':
        file = request.files.get('archivo_alias')
        if not file or not file.filename:
            flash('No se seleccionó ningún archivo para importar.', 'danger')
            return redirect(request.url)

        imported, updated, errors, message = alias_s.import_aliases(file)
        if message:
            flash(message, 'danger')
        else:
            msg_parts = []
            if imported > 0:
                msg_parts.append(f"Se crearon {imported} nuevos alias.")
            if updated > 0:
                msg_parts.append(f"Se actualizaron {updated} alias existentes.")
            if msg_parts:
                flash("Importación completada: " + " ".join(msg_parts), 'success')
            if errors:
                flash(f"Errores en {len(errors)} fila(s): " + "; ".join(errors[:5]), 'danger')
        return redirect(url_for('admin.gestionar_alias'))

    return render_template('admin/importar_alias.html', titulo="Importar Alias de Perfiles")

@admin_bp.route('/eficiencia')
@roles_required('ADMINISTRADOR')
def eficiencia():
    data, error = system_s.get_efficiency_data()
    if error:
        flash(error, 'danger')
        return render_template('admin/eficiencia.html', titulo="Análisis de Eficiencia", kpis={}, charts_data={}, slow_connections=[], filters={})
    return render_template('admin/eficiencia.html', titulo="Análisis de Eficiencia", **data)

@admin_bp.route('/logs')
@roles_required('ADMINISTRADOR')
def logs():
    logs, error = system_s.get_logs()
    if error:
        flash(error, 'info')
    return render_template('admin/logs.html', logs=logs, titulo="Logs del Sistema")

@admin_bp.route('/logs/clear', methods=['POST'])
@roles_required('ADMINISTRADOR')
def clear_logs():
    success, message = system_s.clear_logs(g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.logs'))

@admin_bp.route('/storage')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def storage_management():
    stats, error = system_s.get_storage_stats()
    if error:
        flash(error, 'danger')
        return render_template('admin/storage.html', titulo="Gestión de Almacenamiento", total_size='N/A', num_files=0, files_by_ext={})
    return render_template('admin/storage.html', titulo="Gestión de Almacenamiento", **stats)

@admin_bp.route('/auditoria')
@roles_required('ADMINISTRADOR')
def ver_auditoria():
    page = request.args.get('page', 1, type=int)
    per_page = 20 # Or from config
    filtro_usuario_id = request.args.get('usuario_id', type=int)
    filtro_accion = request.args.get('accion')

    data = system_s.get_audit_data(page, per_page, filtro_usuario_id, filtro_accion)

    log_action('VER_AUDITORIA', g.user['id'], 'sistema', None, "Visualizó el historial de auditoría.")
    return render_template('admin/auditoria.html',
                           **data,
                           filtro_usuario_id=filtro_usuario_id,
                           filtro_accion=filtro_accion,
                           page=page,
                           per_page=per_page,
                           titulo="Historial de Auditoría")

@admin_bp.route('/reportes')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def listar_reportes():
    reportes = report_s.get_all_reports()
    return render_template('admin/reportes.html', reportes=reportes, titulo="Gestión de Reportes")

@admin_bp.route('/reportes/nuevo', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def nuevo_reporte():
    form = ReportForm()
    dal = SQLiteDAL()
    form.proyecto_id.choices = [(0, 'Todos los Proyectos')] + [(p['id'], p['nombre']) for p in dal.get_proyectos_for_user(g.user['id'], True)]
    form.realizador_id.choices = [(0, 'Todos los Realizadores')] + [(r['id'], r['nombre_completo']) for r in dal.get_all_users_with_roles() if 'REALIZADOR' in r['roles']]

    if form.validate_on_submit():
        success, message = report_s.create_report(form, g.user['id'])
        if success:
            flash(message, 'success')
            return redirect(url_for('admin.listar_reportes'))
        else:
            flash(message, 'danger')
    return render_template('admin/reporte_form.html', form=form, titulo="Nuevo Reporte")

@admin_bp.route('/reportes/<int:reporte_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def editar_reporte(reporte_id):
    reporte = report_s.get_report_for_edit(reporte_id)
    if not reporte:
        abort(404)

    form = ReportForm()
    dal = SQLiteDAL()
    form.proyecto_id.choices = [(0, 'Todos los Proyectos')] + [(p['id'], p['nombre']) for p in dal.get_proyectos_for_user(g.user['id'], True)]
    form.realizador_id.choices = [(0, 'Todos los Realizadores')] + [(r['id'], r['nombre_completo']) for r in dal.get_all_users_with_roles() if 'REALIZADOR' in r['roles']]

    if form.validate_on_submit():
        success, message = report_s.update_report(reporte_id, form)
        if success:
            flash(message, 'success')
            return redirect(url_for('admin.listar_reportes'))
        else:
            flash(message, 'danger')

    if request.method == 'GET':
        # Populate form from reporte data
        pass

    return render_template('admin/reporte_form.html', form=form, titulo=f"Editar Reporte: {reporte['nombre']}")

@admin_bp.route('/reportes/<int:reporte_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_reporte(reporte_id):
    success, message = report_s.delete_report(reporte_id, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.listar_reportes'))

@admin_bp.route('/proyectos/<int:proyecto_id>/permisos', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def gestionar_permisos_proyecto(proyecto_id):
    dal = SQLiteDAL()
    proyecto = dal.get_proyecto(proyecto_id)
    if not proyecto:
        abort(404)

    form = FlaskForm()
    if form.validate_on_submit():
        usuarios_asignados = request.form.getlist('usuarios_asignados')
        # Here I should call a service to update the permissions
        dal.assign_users_to_project(proyecto_id, usuarios_asignados)
        flash('Permisos del proyecto actualizados con éxito.', 'success')
        return redirect(url_for('admin.gestionar_permisos_proyecto', proyecto_id=proyecto_id))

    todos_usuarios = dal.get_all_users_with_roles()
    usuarios_con_acceso = dal.get_users_for_project(proyecto_id)

    return render_template('admin/proyecto_permisos.html',
                           proyecto=proyecto,
                           todos_usuarios=todos_usuarios,
                           usuarios_con_acceso=usuarios_con_acceso,
                           titulo=f"Permisos para {proyecto['nombre']}",
                           form=form)

@admin_bp.route('/reportes/<int:reporte_id>/ejecutar')
@roles_required('ADMINISTRADOR')
def ejecutar_reporte(reporte_id):
    filename, mimetype, content, message = report_s.run_report(reporte_id, g.user['id'])
    if not content:
        flash(message, 'danger')
        return redirect(url_for('admin.listar_reportes'))

    response = make_response(content)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = mimetype
    return response

@admin_bp.route('/configuracion', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def configuracion():
    form = ConfigurationForm()
    if form.validate_on_submit():
        success, message = system_s.update_config(request.form, g.user['id'])
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('admin.configuracion'))

    config_data = system_s.get_config_data()
    form.per_page.data = int(config_data.get('PER_PAGE', 10))
    form.maintenance_mode.data = config_data.get('MAINTENANCE_MODE') == '1'

    return render_template('admin/configuracion.html', form=form, titulo="Configuración del Sistema")

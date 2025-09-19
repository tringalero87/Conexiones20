from flask import (
    Blueprint, render_template, request, redirect, url_for, g, flash, abort, make_response
)
from forms import UserForm, ConfigurationForm, ReportForm, AliasForm
from flask_wtf import FlaskForm
from extensions import db
from models import Rol, Proyecto, Usuario
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
    form.roles.choices = [r.nombre for r in db.session.query(Rol).order_by(Rol.nombre).all()]
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
    form = UserForm(obj=usuario, original_username=usuario.username, original_email=usuario.email)
    form.roles.choices = [r.nombre for r in db.session.query(Rol.nombre).order_by(Rol.nombre).all()]
    if request.method == 'POST' and form.validate_on_submit():
        success, message = user_s.update_user(usuario_id, form, g.user.id)
        if success:
            flash(message, 'success')
            return redirect(url_for('admin.listar_usuarios'))
        else:
            flash(message, 'danger')
    if request.method == 'GET':
        form.roles.data = roles
    return render_template('admin/usuario_form.html', form=form, usuario=usuario, titulo="Editar Usuario")

@admin_bp.route('/usuarios/<int:usuario_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_usuario(usuario_id):
    success, message = user_s.delete_user(usuario_id, g.user.id)
    if success: flash(message, 'success')
    else: flash(message, 'danger')
    return redirect(url_for('admin.listar_usuarios'))

@admin_bp.route('/usuarios/<int:usuario_id>/toggle_activo', methods=['POST'])
@roles_required('ADMINISTRADOR')
def toggle_activo(usuario_id):
    """Activa o desactiva un usuario."""
    success, message = user_s.toggle_user_active_status(usuario_id, g.user.id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.listar_usuarios'))

@admin_bp.route('/alias')
@roles_required('ADMINISTRADOR')
def gestionar_alias():
    form = AliasForm()
    if form.validate_on_submit():
        success, message = alias_s.create_alias(form, g.user.id)
        if success: flash(message, 'success')
        else: flash(message, 'danger')
        return redirect(url_for('admin.gestionar_alias'))
    aliases = alias_s.get_all_aliases()
    return render_template('admin/alias_manager.html', aliases=aliases, form=form, titulo="Gestión de Alias")

@admin_bp.route('/reportes')
@roles_required('ADMINISTRADOR')
def listar_reportes():
    reportes = report_s.get_all_reports()
    return render_template('admin/reportes.html', reportes=reportes, titulo="Gestión de Reportes")

@admin_bp.route('/configuracion', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def configuracion():
    form = ConfigurationForm()
    if form.validate_on_submit():
        system_s.update_config(form.data, g.user.id)
        flash('Configuración guardada.', 'success')
        return redirect(url_for('admin.configuracion'))
    config_data = system_s.get_config_data()
    form.per_page.data = int(config_data.get('PER_PAGE', 10))
    form.maintenance_mode.data = config_data.get('MAINTENANCE_MODE') == '1'
    return render_template('admin/configuracion.html', form=form, titulo="Configuración")

@admin_bp.route('/eficiencia')
@roles_required('ADMINISTRADOR')
def eficiencia():
    data, _ = system_s.get_efficiency_data()
    return render_template('admin/eficiencia.html', titulo="Análisis de Eficiencia", **data)

@admin_bp.route('/auditoria')
@roles_required('ADMINISTRADOR')
def ver_auditoria():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    pagination = system_s.get_audit_data(page, per_page, None, None)
    return render_template('admin/auditoria.html', pagination=pagination, titulo="Historial de Auditoría")

@admin_bp.route('/storage')
@roles_required('ADMINISTRADOR')
def storage_management():
    stats, _ = system_s.get_storage_stats()
    return render_template('admin/storage.html', titulo="Gestión de Almacenamiento", **stats)

@admin_bp.route('/proyectos/<int:proyecto_id>/permisos', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR')
def gestionar_permisos_proyecto(proyecto_id):
    proyecto = db.session.get(Proyecto, proyecto_id)
    if not proyecto: abort(404)
    form = FlaskForm()
    if form.validate_on_submit():
        user_ids = request.form.getlist('usuarios_asignados')
        usuarios = db.session.query(Usuario).filter(Usuario.id.in_(user_ids)).all()
        proyecto.usuarios_asignados = usuarios
        db.session.commit()
        flash('Permisos actualizados.', 'success')
        return redirect(url_for('admin.gestionar_permisos_proyecto', proyecto_id=proyecto_id))
    todos_usuarios = user_s.get_all_users_with_roles()
    usuarios_con_acceso_ids = {u.id for u in proyecto.usuarios_asignados}
    return render_template('admin/proyecto_permisos.html', proyecto=proyecto, todos_usuarios=todos_usuarios, usuarios_con_acceso=usuarios_con_acceso_ids, form=form, titulo="Permisos de Proyecto")

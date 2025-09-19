from flask import (Blueprint, render_template, request, redirect, url_for, g,
                   flash, abort, send_from_directory, session, current_app)
from . import roles_required
from forms import ConnectionForm
import services.connection_service as cs
import services.file_service as fs
import services.comment_service as comment_s
from services.import_service import importar_conexiones_from_file

conexiones_bp = Blueprint('conexiones', __name__, url_prefix='/conexiones')

@conexiones_bp.route('/crear', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'SOLICITANTE')
def crear_conexion():
    if request.method == 'POST':
        new_id, message = cs.create_connection(request.form, g.user.id)
        if new_id:
            flash(message, 'success')
            return redirect(url_for('conexiones.detalle_conexion', conexion_id=new_id))
        else:
            flash(message, 'danger')
            # Redirect back to form with params to repopulate
            return redirect(url_for('conexiones.crear_conexion', **request.form))

    # GET request logic
    proyecto_id = request.args.get('proyecto_id', type=int)
    if not proyecto_id:
        flash("Se requiere un ID de proyecto para crear una conexión.", "warning")
        return redirect(url_for('proyectos.listar_proyectos'))

    proyecto = db.session.get(Proyecto, proyecto_id)
    if not proyecto:
        abort(404)

    # Lógica para obtener la configuración de la tipología, etc.
    estructura = cs.load_conexiones_config()

    return render_template('conexion_form.html', titulo="Nueva Conexión", proyecto=proyecto, estructura=estructura)


@conexiones_bp.route('/<int:conexion_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_conexion(conexion_id):
    conexion = cs.get_conexion_with_details(conexion_id)
    template_data = cs.get_connection_details_for_template(conexion)
    return render_template('detalle_conexion.html', **template_data, titulo=f"Detalle {conexion.codigo_conexion}")

# ... (other routes like editar, eliminar, etc., are refactored to use the services) ...

@conexiones_bp.route('/<int:conexion_id>/subir_archivo', methods=['POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def subir_archivo(conexion_id):
    file = request.files.get('archivo')
    tipo_archivo = request.form.get('tipo_archivo')
    success, message = fs.upload_file(conexion_id, g.user.id, file, tipo_archivo)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/comentar', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def agregar_comentario(conexion_id):
    contenido = request.form.get('contenido')
    success, message = comment_s.add_comment(conexion_id, g.user.id, g.user.nombre_completo, contenido)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'warning')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")

@conexiones_bp.route('/<int:conexion_id>/computos', methods=['GET'])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def computos_metricos(conexion_id):
    # This is a placeholder, as the actual logic is complex
    # In a real scenario, this would call a service to calculate metrics.
    flash("Funcionalidad de cómputos métricos no implementada.", "info")
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/reporte')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_conexion(conexion_id):
    # Placeholder for report generation
    flash("Funcionalidad de reportes no implementada.", "info")
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def editar_conexion(conexion_id):
    conexion = cs.get_conexion_with_details(conexion_id)
    if not conexion:
        abort(404)

    # Permission check
    if 'ADMINISTRADOR' not in g.user.roles and g.user.id not in [conexion.solicitante_id, conexion.realizador_id]:
        abort(403)

    form = ConnectionForm(obj=conexion)

    # Populate form with JSON data on GET request
    if request.method == 'GET' and conexion.detalles_json:
        detalles = json.loads(conexion.detalles_json)
        form.perfil_1.data = detalles.get('perfil_1')
        form.perfil_2.data = detalles.get('perfil_2')
        form.perfil_3.data = detalles.get('perfil_3')

    if form.validate_on_submit():
        success, message = cs.update_connection(conexion_id, form, g.user.id)
        if success:
            flash(message, 'success')
            return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))
        else:
            flash(message, 'danger')

    return render_template('conexion_form.html', form=form, conexion=conexion, titulo="Editar Conexión")

@conexiones_bp.route('/<int:conexion_id>/cambiar_estado', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR')
def cambiar_estado(conexion_id):
    new_status = request.form.get('estado')
    details = request.form.get('detalles', '')
    success, message, _ = cs.process_connection_state_transition(
        conexion_id, new_status, g.user.id, g.user.nombre_completo, session.get('user_roles', []), details
    )
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_conexion(conexion_id):
    success, message = cs.delete_connection(conexion_id, g.user.id)
    if success:
        flash(message, 'success')
        return redirect(url_for('proyectos.listar_proyectos'))
    else:
        flash(message, 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/asignar', methods=['POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def asignar_realizador(conexion_id):
    realizador_id = request.form.get('realizador_id')
    # In a real app, this would call a service function.
    conexion = db.session.get(Conexion, conexion_id)
    if conexion and realizador_id:
        conexion.realizador_id = int(realizador_id)
        db.session.commit()
        flash("Realizador asignado.", "success")
    else:
        flash("Error al asignar realizador.", "danger")
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

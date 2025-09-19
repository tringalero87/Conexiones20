from collections import defaultdict
import json
from flask import (Blueprint, render_template, request, redirect, url_for, g,
                   flash, abort, send_from_directory, session, current_app)
from . import roles_required
from forms import ConnectionForm
from db import get_db, log_action
from dal.sqlite_dal import SQLiteDAL
from services.computos_service import get_computos_results, calculate_and_save_computos
import services.connection_service as cs
import services.file_service as fs
import services.comment_service as comment_s
from services.import_service import importar_conexiones_from_file

conexiones_bp = Blueprint('conexiones', __name__, url_prefix='/conexiones')


@conexiones_bp.route('/crear', methods=['GET'])
@roles_required('ADMINISTRADOR', 'SOLICITANTE')
def crear_conexion_form():
    proyecto_id = request.args.get('proyecto_id', type=int)
    tipo = request.args.get('tipo')
    subtipo = request.args.get('subtipo')
    tipologia_nombre = request.args.get('tipologia')

    if not all([proyecto_id, tipo, subtipo, tipologia_nombre]):
        flash("Faltan parámetros para crear la conexión. Por favor, selecciona desde el catálogo.", "danger")
        return redirect(url_for('main.catalogo'))

    dal = SQLiteDAL()
    proyecto = dal.get_proyecto(proyecto_id)
    if not proyecto:
        abort(404)

    lista_de_alias = dal.get_all_aliases()
    tipologia_seleccionada = cs.get_tipologia_config(
        tipo, subtipo, tipologia_nombre)
    if not tipologia_seleccionada:
        flash("Error: No se pudo encontrar la configuración para la tipología seleccionada.", "danger")
        return redirect(url_for('main.catalogo'))

    return render_template('conexion_form.html',
                           proyecto=proyecto,
                           tipo=tipo,
                           subtipo=subtipo,
                           tipologia=tipologia_seleccionada,
                           lista_alias=lista_de_alias,
                           titulo=f"Nueva Conexión: {tipologia_nombre}")


@conexiones_bp.route('/crear', methods=['POST'])
@roles_required('ADMINISTRADOR', 'SOLICITANTE')
def procesar_creacion_conexion():
    new_id, message = cs.create_connection(request.form, g.user['id'])
    if new_id:
        flash(message, 'success')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=new_id))
    else:
        flash(message, 'danger')
        # Redirect back to form with params to repopulate
        return redirect(url_for('conexiones.crear_conexion_form',
                                proyecto_id=request.form.get('proyecto_id'),
                                tipo=request.form.get('tipo'),
                                subtipo=request.form.get('subtipo'),
                                tipologia=request.form.get('tipologia_nombre')))


@conexiones_bp.route('/<int:conexion_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_conexion(conexion_id):
    details = cs.get_connection_details(conexion_id)
    return render_template('detalle_conexion.html',
                           **details,
                           titulo=f"Detalle {details['conexion']['codigo_conexion']}")


@conexiones_bp.route('/<int:conexion_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE')
def editar_conexion(conexion_id):
    conexion = cs.get_conexion(conexion_id)

    user_roles = session.get('user_roles', [])
    can_edit = ('ADMINISTRADOR' in user_roles or
                ('SOLICITANTE' in user_roles and conexion['estado'] == 'SOLICITADO' and conexion['solicitante_id'] == g.user['id']) or
                ('REALIZADOR' in user_roles and conexion['estado'] == 'EN_PROCESO' and conexion['realizador_id'] == g.user['id']))
    if not can_edit:
        abort(403)

    tipologia_config = cs.get_tipologia_config(
        conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    if not tipologia_config:
        flash(
            "Error: No se encontró la configuración de la tipología para editar.", "danger")
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    num_perfiles = tipologia_config.get('perfiles', 0)
    form = ConnectionForm()
    for i in range(3, 1, -1):
        if num_perfiles < i and hasattr(form, f'perfil_{i}'):
            delattr(form, f'perfil_{i}')

    if form.validate_on_submit():
        success, message, flash_message = cs.update_connection(
            conexion_id, form, g.user, session.get('user_roles', []))
        if success:
            flash(message, 'success')
            if flash_message:
                flash(flash_message, 'info')
            return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))
        else:
            flash(message, 'danger')

    if request.method == 'GET':
        details = cs.get_connection_details(conexion_id)
        form.descripcion.data = conexion['descripcion']
        for i in range(1, num_perfiles + 1):
            if hasattr(form, f'perfil_{i}'):
                getattr(form, f'perfil_{i}').data = details['detalles'].get(
                    f'Perfil {i}', '')

    return render_template('conexion_form_edit.html', form=form, conexion=conexion, tipologia=tipologia_config, titulo="Editar Conexión")


@conexiones_bp.route('/<int:conexion_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_conexion(conexion_id):
    conexion = cs.get_conexion(conexion_id)
    success, message = cs.delete_connection(conexion_id, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('proyectos.detalle_proyecto', proyecto_id=conexion['proyecto_id']))


@conexiones_bp.route('/<int:proyecto_id>/importar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def importar_conexiones(proyecto_id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute('SELECT * FROM proyectos WHERE id = ?', (proyecto_id,))
        proyecto = cursor.fetchone()
    finally:
        cursor.close()

    if not proyecto:
        abort(404)

    if request.method == 'POST':
        if 'archivo_importacion' not in request.files or not request.files['archivo_importacion'].filename:
            flash('No se seleccionó ningún archivo.', 'danger')
            return redirect(request.url)

        file = request.files['archivo_importacion']
        if file and file.filename.endswith('.xlsx'):
            imported_count, error_rows, error_message = importar_conexiones_from_file(
                file, proyecto_id, g.user['id'])

            if error_message:
                flash(error_message, 'danger')
            else:
                if imported_count > 0:
                    flash(
                        f"Importación completada: Se crearon {imported_count} conexiones.", 'success')
                if error_rows:
                    flash(
                        f"Se encontraron problemas en {len(error_rows)} fila(s) durante la importación. Detalles: {'; '.join(error_rows)}", "warning")
                if imported_count == 0 and not error_rows:
                    flash(
                        "No se crearon nuevas conexiones. Revisa el formato de tu archivo o los datos.", "info")
        else:
            flash(
                'Formato de archivo no válido. Por favor, sube un archivo .xlsx.', 'warning')

        return redirect(url_for('proyectos.detalle_proyecto', proyecto_id=proyecto_id))

    return render_template('importar_conexiones.html', proyecto=proyecto, titulo="Importar Conexiones")


@conexiones_bp.route('/<int:conexion_id>/cambiar_estado', methods=('POST',))
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'APROBADOR')
def cambiar_estado(conexion_id):
    nuevo_estado_form = request.form.get('estado')
    detalles_form = request.form.get('detalles', '')
    success, message, _ = cs.process_connection_state_transition(
        conexion_id, nuevo_estado_form, g.user['id'],
        g.user['nombre_completo'], session.get('user_roles', []), detalles_form
    )
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/asignar', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def asignar_realizador(conexion_id):
    username_a_asignar = request.form.get('username_a_asignar', '').lstrip('@')
    if not username_a_asignar:
        flash('Debes especificar un nombre de usuario para asignar la tarea.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    success, message = cs.assign_realizador(
        conexion_id, username_a_asignar, g.user)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/subir_archivo', methods=('POST',))
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def subir_archivo(conexion_id):
    file = request.files.get('archivo')
    tipo_archivo = request.form.get('tipo_archivo')
    success, message = fs.upload_file(
        conexion_id, g.user['id'], file, tipo_archivo)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/descargar/<path:filename>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def descargar_archivo(conexion_id, filename):
    directory = fs.get_file_for_download(conexion_id, filename, g.user['id'])
    return send_from_directory(directory, filename, as_attachment=True)


@conexiones_bp.route('/<int:conexion_id>/eliminar_archivo/<int:archivo_id>', methods=['POST',])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def eliminar_archivo(conexion_id, archivo_id):
    success, message = fs.delete_file(
        conexion_id, archivo_id, g.user, session.get('user_roles', []))
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/comentar', methods=('POST',))
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def agregar_comentario(conexion_id):
    contenido = request.form.get('contenido')
    success, message = comment_s.add_comment(
        conexion_id, g.user['id'], g.user['nombre_completo'], contenido)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'warning')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")


@conexiones_bp.route('/<int:conexion_id>/eliminar_comentario/<int:comentario_id>', methods=['POST',])
@roles_required('ADMINISTRADOR')
def eliminar_comentario(conexion_id, comentario_id):
    success, message = comment_s.delete_comment(
        conexion_id, comentario_id, g.user['id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")


@conexiones_bp.route('/<int:conexion_id>/computos', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def computos_metricos(conexion_id):
    conexion = cs.get_conexion(conexion_id)

    if request.method == 'POST':
        resultados, success_message, error_messages, perfiles = calculate_and_save_computos(
            conexion_id, request.form, g.user['id'])
        if success_message:
            flash('Cómputos guardados con éxito.', 'success')
        if error_messages:
            for error in error_messages:
                flash(error, 'danger')
        return redirect(url_for('conexiones.computos_metricos', conexion_id=conexion_id))

    resultados, detalles = get_computos_results(conexion)
    perfiles = [(key, value)
                for key, value in detalles.items() if key.startswith('Perfil')]

    return render_template('computos_metricos.html',
                           titulo="Cómputos Métricos",
                           conexion=conexion, perfiles=perfiles,
                           resultados=resultados, detalles=detalles)


@conexiones_bp.route('/<int:conexion_id>/reporte_computos')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_computos(conexion_id):
    conexion = cs.get_conexion(conexion_id)
    resultados, _ = get_computos_results(conexion)
    log_action('GENERAR_REPORTE_COMPUTOS',
               g.user['id'], 'conexiones', conexion_id, "Reporte de cómputos generado.")
    return render_template('reporte_computos.html',
                           titulo=f"Reporte de Cómputos para {conexion['codigo_conexion']}",
                           conexion=conexion, resultados=resultados)


@conexiones_bp.route('/<int:conexion_id>/reporte')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_conexion(conexion_id):
    db = get_db()
    conexion = cs.get_conexion(conexion_id)

    cursor = db.cursor()
    try:
        sql_historial = """
            SELECT h.*, u.nombre_completo FROM historial_estados h
            JOIN usuarios u ON h.usuario_id = u.id
            WHERE h.conexion_id = ? ORDER BY h.fecha ASC
        """
        cursor.execute(sql_historial, (conexion_id,))
        historial = cursor.fetchall()

        sql_comentarios = """
            SELECT c.*, u.nombre_completo FROM comentarios c
            JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.conexion_id = ? ORDER BY c.fecha_creacion ASC
        """
        cursor.execute(sql_comentarios, (conexion_id,))
        comentarios = cursor.fetchall()

        sql_archivos = """
            SELECT a.*, u.nombre_completo as subido_por FROM archivos a
            JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.conexion_id = ? ORDER BY a.fecha_subida ASC
        """
        cursor.execute(sql_archivos, (conexion_id,))
        archivos_raw = cursor.fetchall()
    finally:
        cursor.close()

    archivos_agrupados = defaultdict(list)
    for archivo in archivos_raw:
        archivos_agrupados[archivo['tipo_archivo']].append(archivo)

    detalles = json.loads(
        conexion['detalles_json']) if conexion['detalles_json'] else {}
    tipologia_config = cs.get_tipologia_config(conexion['tipo'],
                                               conexion['subtipo'],
                                               conexion['tipologia'])
    log_action('GENERAR_REPORTE_CONEXION', g.user['id'], 'conexiones',
               conexion_id, "Reporte de conexión generado.")

    return render_template(
        'reporte_conexion.html',
        conexion=conexion,
        historial=historial,
        comentarios=comentarios,
        archivos_agrupados=archivos_agrupados,
        detalles=detalles,
        tipologia_config=tipologia_config,
        titulo=f"Reporte de Conexión: {conexion['codigo_conexion']}"
    )

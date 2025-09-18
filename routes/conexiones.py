import os
import json
import bleach
from flask import (Blueprint, render_template, request, redirect, url_for, g,
                   current_app, flash, abort, send_from_directory, session)
from werkzeug.utils import secure_filename
from collections import defaultdict

from db import get_db, log_action
from . import roles_required
from forms import ConnectionForm

# Importa el servicio de cómputos
from services.computos_service import get_computos_results, calculate_and_save_computos
from services.connection_service import (
    process_connection_state_transition, _get_conexion, _notify_users, get_tipologia_config
)

conexiones_bp = Blueprint('conexiones', __name__, url_prefix='/conexiones')

ALLOWED_EXTENSIONS = {
    'pdf', 'xlsx', 'xls', 'docx', 'doc', 'csv', 'txt', 'ppt', 'pptx', 'ideacon'
}

def allowed_file(filename):
    """Función auxiliar para verificar si la extensión de un archivo es válida."""
    if '.' not in filename or filename.startswith('.'):
        return False

    extension = filename.rsplit('.', 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS

@conexiones_bp.route('/crear', methods=['GET'])
@roles_required('ADMINISTRADOR', 'SOLICITANTE')
def crear_conexion_form():
    """Muestra un formulario dinámico para crear una nueva conexión."""
    proyecto_id = request.args.get('proyecto_id', type=int)
    tipo = request.args.get('tipo')
    subtipo = request.args.get('subtipo')
    tipologia_nombre = request.args.get('tipologia')

    if not all([proyecto_id, tipo, subtipo, tipologia_nombre]):
        flash("Faltan parámetros para crear la conexión. Por favor, selecciona desde el catálogo.", "danger")
        return redirect(url_for('main.catalogo'))

    db = get_db()
    cursor = db.cursor()

    try:
        sql_get_proyecto = 'SELECT * FROM proyectos WHERE id = ?'
        cursor.execute(sql_get_proyecto, (proyecto_id,))
        proyecto = cursor.fetchone()
        if not proyecto:
            abort(404)

        cursor.execute("SELECT alias, nombre_perfil FROM alias_perfiles ORDER BY nombre_perfil")
        lista_de_alias = cursor.fetchall()
    finally:
        cursor.close()

    tipologia_seleccionada = get_tipologia_config(tipo, subtipo, tipologia_nombre)
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
    """Procesa el formulario y crea una nueva conexión de forma segura y portable."""
    db = get_db()
    cursor = db.cursor()

    try:
        proyecto_id = request.form.get('proyecto_id', type=int)
        tipo = request.form.get('tipo')
        subtipo = request.form.get('subtipo')
        tipologia_nombre = request.form.get('tipologia_nombre')
        descripcion = request.form.get('descripcion')

        tipologia_config = get_tipologia_config(tipo, subtipo, tipologia_nombre)
        if not tipologia_config:
            flash("Error: Configuración de tipología no encontrada.", "danger")
            return redirect(url_for('main.catalogo'))

        # Validar perfiles
        num_perfiles = tipologia_config.get('perfiles', 0)
        perfiles_para_plantilla, perfiles_para_detalles = {}, {}
        sql_get_alias = 'SELECT alias FROM alias_perfiles WHERE nombre_perfil = ?'

        for i in range(1, num_perfiles + 1):
            nombre_campo = f'perfil_{i}'
            nombre_completo_perfil = request.form.get(nombre_campo)
            if not nombre_completo_perfil:
                flash(f"El campo 'Perfil {i}' es obligatorio.", "danger")
                return redirect(url_for('conexiones.crear_conexion_form', proyecto_id=proyecto_id, tipo=tipo, subtipo=subtipo, tipologia=tipologia_nombre))

            cursor.execute(sql_get_alias, (nombre_completo_perfil,))
            alias_row = cursor.fetchone()
            perfiles_para_plantilla[f'p{i}'] = alias_row['alias'] if alias_row else nombre_completo_perfil
            perfiles_para_detalles[f'Perfil {i}'] = nombre_completo_perfil

        # Generar código de conexión único
        codigo_conexion_base = tipologia_config.get('plantilla', '').format(**perfiles_para_plantilla)
        codigo_conexion_final = codigo_conexion_base
        contador = 1
        sql_check_code = 'SELECT 1 FROM conexiones WHERE codigo_conexion = ?'
        while True:
            cursor.execute(sql_check_code, (codigo_conexion_final,))
            if not cursor.fetchone():
                break
            contador += 1
            codigo_conexion_final = f"{codigo_conexion_base}-{contador}"

        # Insertar conexión
        detalles_json = json.dumps(perfiles_para_detalles)
        sql_insert_conexion = "INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, descripcion, detalles_json, solicitante_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        
        params_conexion = (codigo_conexion_final, proyecto_id, tipo, subtipo, tipologia_nombre, descripcion, detalles_json, g.user['id'])
        cursor.execute(sql_insert_conexion, params_conexion)

        new_conexion_id = cursor.lastrowid

        # Insertar historial
        sql_insert_historial = "INSERT INTO historial_estados (conexion_id, usuario_id, estado) VALUES (?, ?, ?)"
        cursor.execute(sql_insert_historial, (new_conexion_id, g.user['id'], 'SOLICITADO'))

        db.commit()
    finally:
        cursor.close()

    log_action('CREAR_CONEXION', g.user['id'], 'conexiones', new_conexion_id, f"Conexión '{codigo_conexion_final}' creada.")
    _notify_users(db, new_conexion_id, f"Nueva conexión '{codigo_conexion_final}' lista para ser tomada.", "", ['REALIZADOR', 'ADMINISTRADOR'])
    flash(f'Conexión {codigo_conexion_final} creada con éxito.', 'success')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=new_conexion_id))

@conexiones_bp.route('/<int:conexion_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_conexion(conexion_id):
    db = get_db()
    conexion = _get_conexion(conexion_id)
    
    cursor = db.cursor()
    try:
        sql_archivos = 'SELECT a.*, u.nombre_completo as subido_por FROM archivos a JOIN usuarios u ON a.usuario_id = u.id WHERE a.conexion_id = ? ORDER BY a.fecha_subida DESC'
        cursor.execute(sql_archivos, (conexion_id,))
        archivos_raw = cursor.fetchall()

        sql_comentarios = "SELECT c.*, u.nombre_completo FROM comentarios c JOIN usuarios u ON c.usuario_id = u.id WHERE c.conexion_id = ? ORDER BY c.fecha_creacion DESC"
        cursor.execute(sql_comentarios, (conexion_id,))
        comentarios = cursor.fetchall()

        sql_historial = "SELECT h.*, u.nombre_completo FROM historial_estados h JOIN usuarios u ON h.usuario_id = u.id WHERE h.conexion_id = ? ORDER BY h.fecha DESC"
        cursor.execute(sql_historial, (conexion_id,))
        historial = cursor.fetchall()
    finally:
        cursor.close()
    
    archivos_agrupados = defaultdict(list)
    for archivo in archivos_raw:
        archivos_agrupados[archivo['tipo_archivo']].append(archivo)

    detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
    tipologia_config = get_tipologia_config(conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    plantilla_archivos = tipologia_config.get('plantilla_archivos', []) if tipologia_config else []

    return render_template('detalle_conexion.html',
                           conexion=conexion,
                           archivos_agrupados=archivos_agrupados,
                           comentarios=comentarios,
                           historial=historial,
                           plantilla_archivos=plantilla_archivos,
                           detalles=detalles,
                           titulo=f"Detalle {conexion['codigo_conexion']}")

@conexiones_bp.route('/<int:conexion_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE')
def editar_conexion(conexion_id):
    db = get_db()
    conexion = _get_conexion(conexion_id)
    user_roles = session.get('user_roles', [])
    user_id = g.user['id']

    can_edit = ('ADMINISTRADOR' in user_roles or
                ('SOLICITANTE' in user_roles and conexion['estado'] == 'SOLICITADO' and conexion['solicitante_id'] == user_id) or
                ('REALIZADOR' in user_roles and conexion['estado'] == 'EN_PROCESO' and conexion['realizador_id'] == user_id))

    if not can_edit:
        abort(403)

    tipologia_config = get_tipologia_config(conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    if not tipologia_config:
        flash("Error: No se encontró la configuración de la tipología para editar.", "danger")
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))
    
    num_perfiles = tipologia_config.get('perfiles', 0)
    form = ConnectionForm()
    # Dynamically remove unused form fields if they exist
    for i in range(3, 1, -1):
        if num_perfiles < i and hasattr(form, f'perfil_{i}'):
            delattr(form, f'perfil_{i}')

    if form.validate_on_submit():
        cursor = db.cursor()
        try:
            # --- Lógica de regeneración de código ---
            perfiles_nuevos_dict_alias = {}
            perfiles_nuevos_dict_full_name = {}
            sql_get_alias = 'SELECT alias FROM alias_perfiles WHERE nombre_perfil = ?'
            for i in range(1, num_perfiles + 1):
                nombre_completo_perfil_nuevo = getattr(form, f'perfil_{i}').data.strip()
                cursor.execute(sql_get_alias, (nombre_completo_perfil_nuevo,))
                alias_row = cursor.fetchone()
                perfiles_nuevos_dict_alias[f'p{i}'] = alias_row['alias'] if alias_row else nombre_completo_perfil_nuevo
                perfiles_nuevos_dict_full_name[f'Perfil {i}'] = nombre_completo_perfil_nuevo

            nuevo_codigo_base = tipologia_config['plantilla'].format(**perfiles_nuevos_dict_alias)
            codigo_a_guardar = conexion['codigo_conexion']
            
            # Regenerate code only if base has changed
            if not conexion['codigo_conexion'].startswith(nuevo_codigo_base):
                codigo_a_guardar = nuevo_codigo_base
                contador = 1
                sql_check_code = 'SELECT 1 FROM conexiones WHERE codigo_conexion = ?'
                while True:
                    cursor.execute(sql_check_code, (codigo_a_guardar,))
                    if not cursor.fetchone():
                        break
                    contador += 1
                    codigo_a_guardar = f"{nuevo_codigo_base}-{contador}"
                flash(f"El código de la conexión se ha actualizado a '{codigo_a_guardar}'.", "info")

            # --- Actualización en la base de datos ---
            nuevos_detalles_json = json.dumps(perfiles_nuevos_dict_full_name)

            sql_update = """UPDATE conexiones SET codigo_conexion = ?, descripcion = ?,
                             detalles_json = ?, fecha_modificacion = CURRENT_TIMESTAMP
                             WHERE id = ?"""
            params_update = (codigo_a_guardar, form.descripcion.data, nuevos_detalles_json, conexion_id)
            cursor.execute(sql_update, params_update)
            db.commit()

            log_action('EDITAR_CONEXION', g.user['id'], 'conexiones', conexion_id, f"Conexión '{conexion['codigo_conexion']}' editada a '{codigo_a_guardar}'.")
            flash('Conexión actualizada con éxito.', 'success')
            return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

        finally:
            cursor.close()

    if request.method == 'GET':
        detalles_actuales = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
        form.descripcion.data = conexion['descripcion']
        for i in range(1, num_perfiles + 1):
            if hasattr(form, f'perfil_{i}'):
                getattr(form, f'perfil_{i}').data = detalles_actuales.get(f'Perfil {i}', '')

    return render_template('conexion_form_edit.html', form=form, conexion=conexion, tipologia=tipologia_config, titulo="Editar Conexión")


@conexiones_bp.route('/<int:conexion_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_conexion(conexion_id):
    conexion = _get_conexion(conexion_id)
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute('DELETE FROM conexiones WHERE id = ?', (conexion_id,))
        db.commit()
    finally:
        cursor.close()

    log_action('ELIMINAR_CONEXION', g.user['id'], 'conexiones', conexion_id, f"Conexión '{conexion['codigo_conexion']}' eliminada.")
    flash(f"La conexión {conexion['codigo_conexion']} ha sido eliminada.", 'success')
    return redirect(url_for('proyectos.detalle_proyecto', proyecto_id=conexion['proyecto_id']))

from services.import_service import importar_conexiones_from_file

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
            imported_count, error_rows, error_message = importar_conexiones_from_file(file, proyecto_id, g.user['id'])

            if error_message:
                flash(error_message, 'danger')
            else:
                if imported_count > 0:
                    flash(f"Importación completada: Se crearon {imported_count} conexiones.", 'success')
                if error_rows:
                    flash(f"Se encontraron problemas en {len(error_rows)} fila(s) durante la importación. Detalles: {'; '.join(error_rows)}", "warning")
                if imported_count == 0 and not error_rows:
                     flash("No se crearon nuevas conexiones. Revisa el formato de tu archivo o los datos.", "info")
        else:
            flash('Formato de archivo no válido. Por favor, sube un archivo .xlsx.', 'warning')

        return redirect(url_for('proyectos.detalle_proyecto', proyecto_id=proyecto_id))

    return render_template('importar_conexiones.html', proyecto=proyecto, titulo="Importar Conexiones")


@conexiones_bp.route('/<int:conexion_id>/cambiar_estado', methods=('POST',))
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'APROBADOR')
def cambiar_estado(conexion_id):
    db = get_db()
    nuevo_estado_form = request.form.get('estado')
    detalles_form = request.form.get('detalles', '')

    success, message, _ = process_connection_state_transition(
        db, conexion_id, nuevo_estado_form, g.user['id'],
        g.user['nombre_completo'], session.get('user_roles', []), detalles_form
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('conexiones.detalle_conexion',
                            conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/asignar', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def asignar_realizador(conexion_id):
    db = get_db()
    conexion = _get_conexion(conexion_id)

    user_roles = session.get('user_roles', [])

    can_assign = (
        'ADMINISTRADOR' in user_roles or
        ('SOLICITANTE' in user_roles and g.user['id'] == conexion['solicitante_id']) or
        ('REALIZADOR' in user_roles and g.user['id'] == conexion['realizador_id']) or
        ('APROBADOR' in user_roles and conexion['estado'] == 'REALIZADO')
    )

    if not can_assign:
        flash('No tienes permisos para asignar esta conexión.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    username_a_asignar = request.form.get('username_a_asignar')

    if not username_a_asignar:
        flash('Debes especificar un nombre de usuario para asignar la tarea.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    username_a_asignar_limpio = username_a_asignar.lstrip('@')
    cursor = db.cursor()

    try:
        sql_get_user = 'SELECT id, nombre_completo FROM usuarios WHERE username = ? AND activo = 1'
        cursor.execute(sql_get_user, (username_a_asignar_limpio,))
        usuario_a_asignar = cursor.fetchone()

        if not usuario_a_asignar:
            flash(f"Usuario '{username_a_asignar}' no encontrado o inactivo.", 'danger')
            return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

        if conexion['estado'] == 'SOLICITADO':
            nuevo_estado = 'EN_PROCESO'
            sql_update = 'UPDATE conexiones SET realizador_id = ?, estado = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?'
            cursor.execute(sql_update, (usuario_a_asignar['id'], nuevo_estado, conexion_id))

            sql_insert = 'INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES (?, ?, ?, ?)'
            cursor.execute(sql_insert, (conexion_id, g.user['id'], nuevo_estado, f"Asignada a {usuario_a_asignar['nombre_completo']}"))

            _notify_users(db, conexion_id, f"La conexión {conexion['codigo_conexion']} ha sido asignada.", "", ['SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'])
            flash(f"Conexión asignada a {usuario_a_asignar['nombre_completo']}.", 'success')
        else:
            sql_update = 'UPDATE conexiones SET realizador_id = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?'
            cursor.execute(sql_update, (usuario_a_asignar['id'], conexion_id))
            log_action('REASIGNAR_CONEXION', g.user['id'], 'conexiones', conexion_id, f"Conexión reasignada a '{usuario_a_asignar['nombre_completo']}'.")
            _notify_users(db, conexion_id, f"La conexión {conexion['codigo_conexion']} ha sido reasignada.", "", ['SOLICITANTE', 'REALIZADOR', 'ADMINISTRADOR'])
            flash('Realizador de la conexión actualizado.', 'success')

        db.commit()
    finally:
        cursor.close()

    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/subir_archivo', methods=('POST',))
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def subir_archivo(conexion_id):
    db = get_db()
    conexion = _get_conexion(conexion_id)

    if 'archivo' not in request.files or not request.files['archivo'].filename:
        flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    file = request.files['archivo']
    tipo_archivo = request.form.get('tipo_archivo')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id))
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))

        sql = 'INSERT INTO archivos (conexion_id, usuario_id, tipo_archivo, nombre_archivo) VALUES (?, ?, ?, ?)'
        params = (conexion_id, g.user['id'], tipo_archivo, filename)

        cursor = db.cursor()
        try:
            cursor.execute(sql, params)
            db.commit()
        finally:
            cursor.close()

        log_action('SUBIR_ARCHIVO', g.user['id'], 'archivos', conexion_id, f"Archivo '{filename}' ({tipo_archivo}) subido.")
        flash(f"Archivo '{tipo_archivo}' subido con éxito.", 'success')
    else:
        flash('Tipo de archivo no permitido.', 'danger')

    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/descargar/<path:filename>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def descargar_archivo(conexion_id, filename):
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id))
    db = get_db()
    sql = 'SELECT id FROM archivos WHERE conexion_id = ? AND nombre_archivo = ?'

    cursor = db.cursor()
    try:
        cursor.execute(sql, (conexion_id, filename))
        archivo_db = cursor.fetchone()
    finally:
        cursor.close()

    if not archivo_db:
        abort(404, description="El archivo no existe o no está asociado a esta conexión.")

    log_action('DESCARGAR_ARCHIVO', g.user['id'], 'archivos', conexion_id, f"Archivo '{filename}' descargado.")
    return send_from_directory(directory, filename, as_attachment=True)


@conexiones_bp.route('/<int:conexion_id>/eliminar_archivo/<int:archivo_id>', methods=['POST',])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def eliminar_archivo(conexion_id, archivo_id):
    db = get_db()
    cursor = db.cursor()
    try:
        sql_get_archivo = 'SELECT * FROM archivos WHERE id = ? AND conexion_id = ?'
        cursor.execute(sql_get_archivo, (archivo_id, conexion_id))
        archivo = cursor.fetchone()

        if archivo:
            conexion = _get_conexion(conexion_id)
            is_admin = 'ADMINISTRADOR' in session.get('user_roles', [])
            is_owner = g.user['id'] == archivo['usuario_id']
            is_realizador = g.user['id'] == conexion['realizador_id']

            if not (is_admin or is_owner or is_realizador):
                flash('No tienes permiso para eliminar este archivo.', 'danger')
                return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

            sql_delete = 'DELETE FROM archivos WHERE id = ?'
            cursor.execute(sql_delete, (archivo_id,))
            db.commit()

            # Sanitize filename to prevent path traversal
            safe_filename = secure_filename(archivo['nombre_archivo'])
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id), safe_filename)

            if os.path.exists(file_path):
                os.remove(file_path)

            flash('Archivo eliminado con éxito.', 'success')
        else:
            flash('El archivo no existe.', 'danger')
    finally:
        cursor.close()

    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))


@conexiones_bp.route('/<int:conexion_id>/comentar', methods=('POST',))
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def agregar_comentario(conexion_id):
    contenido = request.form.get('contenido')
    if contenido:
        sanitized_content = bleach.clean(contenido, tags=bleach.sanitizer.ALLOWED_TAGS + ['p', 'br'], strip=True)
        db = get_db()
        cursor = db.cursor()
        try:
            sql = 'INSERT INTO comentarios (conexion_id, usuario_id, contenido) VALUES (?, ?, ?)'
            cursor.execute(sql, (conexion_id, g.user['id'], sanitized_content))
            db.commit()
        finally:
            cursor.close()

        log_action('AGREGAR_COMENTARIO', g.user['id'], 'conexiones', conexion_id, "Comentario añadido.")
        _notify_users(db, conexion_id, f"{g.user['nombre_completo']} ha comentado.", "#comentarios", ['SOLICITANTE', 'REALIZADOR', 'APROBADOR', 'ADMINISTRADOR'])
        flash('Comentario añadido.', 'success')
    else:
        flash('El comentario no puede estar vacío.', 'warning')

    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")


@conexiones_bp.route('/<int:conexion_id>/eliminar_comentario/<int:comentario_id>', methods=['POST',])
@roles_required('ADMINISTRADOR')
def eliminar_comentario(conexion_id, comentario_id):
    db = get_db()
    cursor = db.cursor()
    try:
        sql = 'DELETE FROM comentarios WHERE id = ? AND conexion_id = ?'
        cursor.execute(sql, (comentario_id, conexion_id))
        db.commit()
        log_action('ELIMINAR_COMENTARIO', g.user['id'], 'comentarios', comentario_id, f"Comentario (ID: {comentario_id}) eliminado.")
        flash('Comentario eliminado.', 'success')
    except Exception as e:
        flash('El comentario no existe o hubo un error.', 'danger')
    finally:
        cursor.close()

    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")


@conexiones_bp.route('/<int:conexion_id>/computos', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def computos_metricos(conexion_id):
    conexion = _get_conexion(conexion_id)

    if request.method == 'POST':
        resultados, success_message, error_messages, perfiles = calculate_and_save_computos(conexion_id, request.form, g.user['id'])
        if success_message:
            flash('Cómputos guardados con éxito.', 'success')
        if error_messages:
            for error in error_messages:
                flash(error, 'danger')
        return redirect(url_for('conexiones.computos_metricos', conexion_id=conexion_id))

    resultados, detalles = get_computos_results(conexion)
    perfiles = [(key, value) for key, value in detalles.items() if key.startswith('Perfil')]

    return render_template('computos_metricos.html',
                           titulo="Cómputos Métricos",
                           conexion=conexion, perfiles=perfiles,
                           resultados=resultados, detalles=detalles)


@conexiones_bp.route('/<int:conexion_id>/reporte_computos')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_computos(conexion_id):
    conexion = _get_conexion(conexion_id)
    resultados, _ = get_computos_results(conexion)
    log_action('GENERAR_REPORTE_COMPUTOS', g.user['id'], 'conexiones', conexion_id, "Reporte de cómputos generado.")
    return render_template('reporte_computos.html',
                           titulo=f"Reporte de Cómputos para {conexion['codigo_conexion']}",
                           conexion=conexion, resultados=resultados)


@conexiones_bp.route('/<int:conexion_id>/reporte')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_conexion(conexion_id):
    db = get_db()
    conexion = _get_conexion(conexion_id)

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

    detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
    tipologia_config = get_tipologia_config(conexion['tipo'],
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
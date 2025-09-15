from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session, current_app
)
from werkzeug.exceptions import abort

from db import get_db, log_action
from . import roles_required
from forms import ProjectForm
import json

proyectos_bp = Blueprint('proyectos', __name__, url_prefix='/proyectos')

@proyectos_bp.route('/')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def listar_proyectos():
    """
    Muestra una lista de todos los proyectos.
    - Los administradores ven todos los proyectos existentes en el sistema.
    - Los demás usuarios solo ven los proyectos a los que tienen acceso asignado.
    """
    db = get_db()
    user_roles = session.get('user_roles', [])
    
    if 'ADMINISTRADOR' in user_roles:
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion, u.nombre_completo as creador,
                          (SELECT COUNT(c.id) FROM conexiones c WHERE c.proyecto_id = p.id) as num_conexiones
                   FROM proyectos p LEFT JOIN usuarios u ON p.creador_id = u.id
                   ORDER BY p.fecha_creacion DESC"""
            )
            proyectos = cursor.fetchall()
    else:
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion, u.nombre_completo as creador,
                          (SELECT COUNT(c.id) FROM conexiones c WHERE c.proyecto_id = p.id) as num_conexiones
                   FROM proyectos p
                   JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
                   LEFT JOIN usuarios u ON p.creador_id = u.id
                   WHERE pu.usuario_id = %s
                   ORDER BY p.fecha_creacion DESC""",
                (g.user['id'],)
            )
            proyectos = cursor.fetchall()
    
    log_action('VER_PROYECTOS', g.user['id'], 'proyectos', None, 
               f"Visualizó la lista de proyectos.")
    return render_template('proyectos.html', proyectos=proyectos, titulo="Proyectos")


@proyectos_bp.route('/<int:proyecto_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_proyecto(proyecto_id):
    """
    Muestra la página de detalle de un proyecto específico, incluyendo una
    lista paginada de todas sus conexiones.
    """
    db = get_db()
    
    with db.cursor() as cursor:
        cursor.execute(
            'SELECT p.*, u.nombre_completo as creador FROM proyectos p '
            'LEFT JOIN usuarios u ON p.creador_id = u.id WHERE p.id = %s', (proyecto_id,)
        )
        proyecto = cursor.fetchone()

    if proyecto is None:
        abort(404, f"El proyecto con id {proyecto_id} no existe.")

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['PER_PAGE']
    offset = (page - 1) * per_page

    with db.cursor() as cursor:
        cursor.execute(
            'SELECT c.*, u.nombre_completo as solicitante_nombre '
            'FROM conexiones c LEFT JOIN usuarios u ON c.solicitante_id = u.id '
            'WHERE c.proyecto_id = %s ORDER BY c.fecha_creacion DESC LIMIT %s OFFSET %s',
            (proyecto_id, per_page, offset)
        )
        conexiones = cursor.fetchall()

    with db.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(id) as total FROM conexiones WHERE proyecto_id = %s', (proyecto_id,)
        )
        total_conexiones = cursor.fetchone()['total']

    log_action('VER_DETALLE_PROYECTO', g.user['id'], 'proyectos', proyecto_id, 
               f"Visualizó el detalle del proyecto '{proyecto['nombre']}'.")
    return render_template(
        'proyecto_detalle.html',
        proyecto=proyecto,
        conexiones=conexiones,
        page=page,
        per_page=per_page,
        total=total_conexiones,
        titulo=f"Detalle de {proyecto['nombre']}"
    )

@proyectos_bp.route('/nuevo', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR')
def nuevo_proyecto():
    """
    Gestiona la creación de un nuevo proyecto.
    Solo los administradores pueden crear proyectos.
    """
    form = ProjectForm()
    if form.validate_on_submit():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute('SELECT id FROM proyectos WHERE LOWER(nombre) = %s', (form.nombre.data.lower(),))
            if cursor.fetchone() is not None:
                flash(f"El proyecto '{form.nombre.data}' ya existe.", 'danger')
            else:
                cursor.execute(
                    'INSERT INTO proyectos (nombre, descripcion, creador_id) VALUES (%s, %s, %s) RETURNING id',
                    (form.nombre.data, form.descripcion.data, g.user['id'])
                )
                new_project_id = cursor.fetchone()['id']
                db.commit()
                log_action('CREAR_PROYECTO', g.user['id'], 'proyectos', new_project_id,
                           f"Proyecto '{form.nombre.data}' creado.")
                current_app.logger.info(f"Admin '{g.user['username']}' creó el proyecto '{form.nombre.data}'.")
                flash('Proyecto creado con éxito.', 'success')
                return redirect(url_for('proyectos.listar_proyectos'))

    return render_template('proyecto_form.html', form=form, titulo="Nuevo Proyecto")

@proyectos_bp.route('/<int:proyecto_id>/editar', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR')
def editar_proyecto(proyecto_id):
    """
    Gestiona la edición de un proyecto existente.
    Solo los administradores pueden editar proyectos.
    """
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM proyectos WHERE id = %s', (proyecto_id,))
        proyecto = cursor.fetchone()
    if not proyecto:
        abort(404)

    form = ProjectForm(obj=proyecto)
    if form.validate_on_submit():
        with db.cursor() as cursor:
            cursor.execute(
                'SELECT id FROM proyectos WHERE LOWER(nombre) = %s AND id != %s',
                (form.nombre.data.lower(), proyecto_id)
            )
            conflicto = cursor.fetchone()
        if conflicto:
            flash(f"Ya existe otro proyecto con el nombre '{form.nombre.data}'.", 'danger')
        else:
            old_data = dict(proyecto)
            
            with db.cursor() as cursor:
                cursor.execute(
                    'UPDATE proyectos SET nombre = %s, descripcion = %s WHERE id = %s',
                    (form.nombre.data, form.descripcion.data, proyecto_id)
                )
            db.commit()
            
            changes = {}
            if form.nombre.data != old_data['nombre']:
                changes['nombre'] = {'old': old_data['nombre'], 'new': form.nombre.data}
            if form.descripcion.data != old_data['descripcion']:
                changes['descripcion'] = {'old': old_data['descripcion'], 'new': form.descripcion.data}

            if changes:
                log_action('EDITAR_PROYECTO', g.user['id'], 'proyectos', proyecto_id, 
                           f"Proyecto '{old_data['nombre']}' editado. Cambios: {json.dumps(changes)}")
            current_app.logger.info(f"Admin '{g.user['username']}' editó el proyecto '{form.nombre.data}'.")
            flash('Proyecto actualizado con éxito.', 'success')
            return redirect(url_for('proyectos.listar_proyectos'))
    
    if request.method == 'GET':
        form.nombre.data = proyecto['nombre']
        form.descripcion.data = proyecto['descripcion']

    return render_template('proyecto_form.html', form=form, proyecto=proyecto, titulo="Editar Proyecto")

@proyectos_bp.route('/<int:proyecto_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_proyecto(proyecto_id):
    """
    Procesa la eliminación de un proyecto y todas sus conexiones asociadas
    gracias a la configuración 'ON DELETE CASCADE' en la base de datos, que elimina
    automáticamente todos los registros hijos.
    """
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('SELECT nombre FROM proyectos WHERE id = %s', (proyecto_id,))
        proyecto = cursor.fetchone()
    if proyecto:
        with db.cursor() as cursor:
            cursor.execute('DELETE FROM proyectos WHERE id = %s', (proyecto_id,))
        db.commit()
        log_action('ELIMINAR_PROYECTO', g.user['id'], 'proyectos', proyecto_id, 
                   f"Proyecto '{proyecto['nombre']}' eliminado (y sus conexiones).") # Auditoría
        current_app.logger.warning(f"Admin '{g.user['username']}' eliminó el proyecto '{proyecto['nombre']}' y todas sus conexiones.")
        flash(f"El proyecto '{proyecto['nombre']}' y todas sus conexiones han sido eliminados.", 'success')
    else:
        flash("El proyecto no fue encontrado.", "danger")
        
    return redirect(url_for('proyectos.listar_proyectos'))
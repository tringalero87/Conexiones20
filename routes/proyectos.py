"""
routes/proyectos.py

Este archivo contiene todas las rutas y la lógica de negocio relacionadas con
la gestión de proyectos en la aplicación Hepta-Conexiones. Incluye la creación,
listado, visualización de detalles, edición y eliminación de proyectos.
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session, current_app
)
from werkzeug.exceptions import abort

# Se importa el módulo de base de datos, el decorador de roles y el formulario de proyecto.
from db import get_db, log_action # Importar log_action
from . import roles_required
from forms import ProjectForm
import json # Importar json para log_action

# Se define el Blueprint para agrupar todas las rutas de este módulo.
# El prefijo /proyectos asegura que todas las rutas aquí definidas comiencen con esa URL.
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
    
    # Si el usuario es ADMINISTRADOR, se le muestran todos los proyectos.
    if 'ADMINISTRADOR' in user_roles:
        proyectos = db.execute(
            """SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion, u.nombre_completo as creador,
                      (SELECT COUNT(c.id) FROM conexiones c WHERE c.proyecto_id = p.id) as num_conexiones
               FROM proyectos p LEFT JOIN usuarios u ON p.creador_id = u.id
               ORDER BY p.fecha_creacion DESC"""
        ).fetchall()
    # Si no, se muestran solo los proyectos a los que el usuario está explícitamente asignado.
    else:
        proyectos = db.execute(
            """SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion, u.nombre_completo as creador,
                      (SELECT COUNT(c.id) FROM conexiones c WHERE c.proyecto_id = p.id) as num_conexiones
               FROM proyectos p
               JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
               LEFT JOIN usuarios u ON p.creador_id = u.id
               WHERE pu.usuario_id = ?
               ORDER BY p.fecha_creacion DESC""",
            (g.user['id'],)
        ).fetchall()
    
    log_action('VER_PROYECTOS', g.user['id'], 'proyectos', None, 
               f"Visualizó la lista de proyectos.") # Auditoría
    return render_template('proyectos.html', proyectos=proyectos, titulo="Proyectos")


@proyectos_bp.route('/<int:proyecto_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_proyecto(proyecto_id):
    """
    Muestra la página de detalle de un proyecto específico, incluyendo una
    lista paginada de todas sus conexiones.
    """
    db = get_db()
    
    # Se obtienen los detalles del proyecto.
    proyecto = db.execute(
        'SELECT p.*, u.nombre_completo as creador FROM proyectos p '
        'LEFT JOIN usuarios u ON p.creador_id = u.id WHERE p.id = ?', (proyecto_id,)
    ).fetchone()

    if proyecto is None:
        abort(404, f"El proyecto con id {proyecto_id} no existe.")

    # Lógica de paginación para las conexiones del proyecto.
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['PER_PAGE']
    offset = (page - 1) * per_page

    # Consulta para obtener las conexiones de la página actual.
    conexiones = db.execute(
        'SELECT c.*, u.nombre_completo as solicitante_nombre '
        'FROM conexiones c LEFT JOIN usuarios u ON c.solicitante_id = u.id '
        'WHERE c.proyecto_id = ? ORDER BY c.fecha_creacion DESC LIMIT ? OFFSET ?',
        (proyecto_id, per_page, offset)
    ).fetchall()

    # Consulta para obtener el número total de conexiones para construir los controles de paginación.
    total_conexiones = db.execute(
        'SELECT COUNT(id) as total FROM conexiones WHERE proyecto_id = ?', (proyecto_id,)
    ).fetchone()['total']

    log_action('VER_DETALLE_PROYECTO', g.user['id'], 'proyectos', proyecto_id, 
               f"Visualizó el detalle del proyecto '{proyecto['nombre']}'.") # Auditoría
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
        # Se verifica que no exista otro proyecto con el mismo nombre (insensible a mayúsculas y minúsculas).
        if db.execute('SELECT id FROM proyectos WHERE LOWER(nombre) = ?', (form.nombre.data.lower(),)).fetchone() is not None:
            flash(f"El proyecto '{form.nombre.data}' ya existe.", 'danger')
        else:
            cursor = db.execute(
                'INSERT INTO proyectos (nombre, descripcion, creador_id) VALUES (?, ?, ?)',
                (form.nombre.data, form.descripcion.data, g.user['id'])
            )
            new_project_id = cursor.lastrowid
            db.commit()
            log_action('CREAR_PROYECTO', g.user['id'], 'proyectos', new_project_id, 
                       f"Proyecto '{form.nombre.data}' creado.") # Auditoría
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
    proyecto = db.execute('SELECT * FROM proyectos WHERE id = ?', (proyecto_id,)).fetchone()
    if not proyecto:
        abort(404)

    form = ProjectForm(obj=proyecto) # Carga los datos del proyecto en el formulario para pre-rellenarlo.
    if form.validate_on_submit():
        # Se verifica que el nuevo nombre no entre en conflicto con otro proyecto (insensible a mayúsculas y minúsculas).
        conflicto = db.execute(
            'SELECT id FROM proyectos WHERE LOWER(nombre) = ? AND id != ?',
            (form.nombre.data.lower(), proyecto_id)
        ).fetchone()
        if conflicto:
            flash(f"Ya existe otro proyecto con el nombre '{form.nombre.data}'.", 'danger')
        else:
            old_data = dict(proyecto) # Guardar datos antiguos para auditoría
            
            db.execute(
                'UPDATE proyectos SET nombre = ?, descripcion = ? WHERE id = ?',
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
                           f"Proyecto '{old_data['nombre']}' editado. Cambios: {json.dumps(changes)}") # Auditoría
            current_app.logger.info(f"Admin '{g.user['username']}' editó el proyecto '{form.nombre.data}'.")
            flash('Proyecto actualizado con éxito.', 'success')
            return redirect(url_for('proyectos.listar_proyectos'))
    
    # Para una solicitud GET, o si el formulario no se ha enviado, se rellena con los datos existentes.
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
    proyecto = db.execute('SELECT nombre FROM proyectos WHERE id = ?', (proyecto_id,)).fetchone()
    if proyecto:
        db.execute('DELETE FROM proyectos WHERE id = ?', (proyecto_id,))
        db.commit()
        log_action('ELIMINAR_PROYECTO', g.user['id'], 'proyectos', proyecto_id, 
                   f"Proyecto '{proyecto['nombre']}' eliminado (y sus conexiones).") # Auditoría
        current_app.logger.warning(f"Admin '{g.user['username']}' eliminó el proyecto '{proyecto['nombre']}' y todas sus conexiones.")
        flash(f"El proyecto '{proyecto['nombre']}' y todas sus conexiones han sido eliminados.", 'success')
    else:
        flash("El proyecto no fue encontrado.", "danger")
        
    return redirect(url_for('proyectos.listar_proyectos'))
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
    db = get_db()
    cursor = db.cursor()
    try:
        user_roles = session.get('user_roles', [])

        if 'ADMINISTRADOR' in user_roles:
            sql = """SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion, u.nombre_completo as creador,
                          (SELECT COUNT(c.id) FROM conexiones c WHERE c.proyecto_id = p.id) as num_conexiones
                   FROM proyectos p LEFT JOIN usuarios u ON p.creador_id = u.id
                   ORDER BY p.fecha_creacion DESC"""
            params = ()
        else:
            sql = """SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion, u.nombre_completo as creador,
                          (SELECT COUNT(c.id) FROM conexiones c WHERE c.proyecto_id = p.id) as num_conexiones
                   FROM proyectos p
                   JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
                   LEFT JOIN usuarios u ON p.creador_id = u.id
                   WHERE pu.usuario_id = %s
                   ORDER BY p.fecha_creacion DESC"""
            params = (g.user['id'],)

        cursor.execute(sql, params)
        proyectos = cursor.fetchall()
    finally:
        cursor.close()

    log_action('VER_PROYECTOS', g.user['id'], 'proyectos', None, "Visualizó la lista de proyectos.")
    return render_template('proyectos.html', proyectos=proyectos, titulo="Proyectos")

@proyectos_bp.route('/<int:proyecto_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_proyecto(proyecto_id):
    db = get_db()
    cursor = db.cursor()
    
    try:
        query_proyecto = 'SELECT p.*, u.nombre_completo as creador FROM proyectos p LEFT JOIN usuarios u ON p.creador_id = u.id WHERE p.id = %s'
        cursor.execute(query_proyecto, (proyecto_id,))
        proyecto = cursor.fetchone()

        if proyecto is None:
            abort(404, f"El proyecto con id {proyecto_id} no existe.")

        page = request.args.get('page', 1, type=int)
        per_page = current_app.config.get('PER_PAGE', 10)
        offset = (page - 1) * per_page

        query_conexiones = 'SELECT c.*, u.nombre_completo as solicitante_nombre FROM conexiones c LEFT JOIN usuarios u ON c.solicitante_id = u.id WHERE c.proyecto_id = %s ORDER BY c.fecha_creacion DESC LIMIT %s OFFSET %s'
        cursor.execute(query_conexiones, (proyecto_id, per_page, offset))
        conexiones = cursor.fetchall()

        query_total = 'SELECT COUNT(id) as total FROM conexiones WHERE proyecto_id = %s'
        cursor.execute(query_total, (proyecto_id,))
        total_conexiones = cursor.fetchone()['total']
    finally:
        cursor.close()

    log_action('VER_DETALLE_PROYECTO', g.user['id'], 'proyectos', proyecto_id, f"Visualizó el detalle del proyecto '{proyecto['nombre']}'.")
    return render_template('proyecto_detalle.html', proyecto=proyecto, conexiones=conexiones, page=page, per_page=per_page, total=total_conexiones, titulo=f"Detalle de {proyecto['nombre']}")

@proyectos_bp.route('/nuevo', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR')
def nuevo_proyecto():
    form = ProjectForm()
    if form.validate_on_submit():
        db = get_db()
        cursor = db.cursor()
        try:
            check_sql = 'SELECT id FROM proyectos WHERE LOWER(nombre) = %s'
            cursor.execute(check_sql, (form.nombre.data.lower(),))
            if cursor.fetchone() is not None:
                flash(f"El proyecto '{form.nombre.data}' ya existe.", 'danger')
            else:
                sql = 'INSERT INTO proyectos (nombre, descripcion, creador_id) VALUES (%s, %s, %s) RETURNING id'
                cursor.execute(sql, (form.nombre.data, form.descripcion.data, g.user['id']))
                new_project_id = cursor.fetchone()['id']
                db.commit()
                log_action('CREAR_PROYECTO', g.user['id'], 'proyectos', new_project_id, f"Proyecto '{form.nombre.data}' creado.")
                flash('Proyecto creado con éxito.', 'success')
                return redirect(url_for('proyectos.listar_proyectos'))
        finally:
            cursor.close()

    return render_template('proyecto_form.html', form=form, titulo="Nuevo Proyecto")

@proyectos_bp.route('/<int:proyecto_id>/editar', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR')
def editar_proyecto(proyecto_id):
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('SELECT * FROM proyectos WHERE id = %s', (proyecto_id,))
        proyecto = cursor.fetchone()
        if not proyecto:
            abort(404)

        form = ProjectForm(obj=proyecto)
        if form.validate_on_submit():
            check_sql = 'SELECT id FROM proyectos WHERE LOWER(nombre) = %s AND id != %s'
            cursor.execute(check_sql, (form.nombre.data.lower(), proyecto_id))
            if cursor.fetchone():
                flash(f"Ya existe otro proyecto con el nombre '{form.nombre.data}'.", 'danger')
            else:
                update_sql = 'UPDATE proyectos SET nombre = %s, descripcion = %s WHERE id = %s'
                cursor.execute(update_sql, (form.nombre.data, form.descripcion.data, proyecto_id))
                db.commit()
                log_action('EDITAR_PROYECTO', g.user['id'], 'proyectos', proyecto_id, f"Proyecto '{form.nombre.data}' actualizado.")
                flash('Proyecto actualizado con éxito.', 'success')
                return redirect(url_for('proyectos.listar_proyectos'))

        if request.method == 'GET':
            form.nombre.data = proyecto['nombre']
            form.descripcion.data = proyecto['descripcion']
    finally:
        cursor.close()

    return render_template('proyecto_form.html', form=form, proyecto=proyecto, titulo="Editar Proyecto")

@proyectos_bp.route('/<int:proyecto_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_proyecto(proyecto_id):
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('SELECT nombre FROM proyectos WHERE id = %s', (proyecto_id,))
        proyecto = cursor.fetchone()
        if proyecto:
            cursor.execute('DELETE FROM proyectos WHERE id = %s', (proyecto_id,))
            db.commit()
            log_action('ELIMINAR_PROYECTO', g.user['id'], 'proyectos', proyecto_id, f"Proyecto '{proyecto['nombre']}' eliminado.")
            flash(f"El proyecto '{proyecto['nombre']}' y todas sus conexiones han sido eliminados.", 'success')
        else:
            flash("El proyecto no fue encontrado.", "danger")
    finally:
        cursor.close()
        
    return redirect(url_for('proyectos.listar_proyectos'))
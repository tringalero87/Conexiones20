from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session, current_app
)
from werkzeug.exceptions import abort
from sqlalchemy import func
from extensions import db
from models import Proyecto, Conexion, Usuario
from . import roles_required
from forms import ProjectForm
from db import log_action

proyectos_bp = Blueprint('proyectos', __name__, url_prefix='/proyectos')

@proyectos_bp.route('/')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def listar_proyectos():
    if 'ADMINISTRADOR' in session.get('user_roles', []):
        proyectos = db.session.query(Proyecto).options(db.joinedload(Proyecto.creador)).order_by(Proyecto.fecha_creacion.desc()).all()
    else:
        proyectos = db.session.query(Proyecto).join(Proyecto.usuarios_asignados).filter(Usuario.id == g.user.id).options(db.joinedload(Proyecto.creador)).order_by(Proyecto.fecha_creacion.desc()).all()

    log_action('VER_PROYECTOS', g.user.id, 'proyectos', None, "Visualizó la lista de proyectos.")
    return render_template('proyectos.html', proyectos=proyectos, titulo="Proyectos")

@proyectos_bp.route('/<int:proyecto_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_proyecto(proyecto_id):
    proyecto = db.session.query(Proyecto).options(db.joinedload(Proyecto.creador)).get(proyecto_id)
    if not proyecto:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('PER_PAGE', 10)
    pagination = db.session.query(Conexion).filter_by(proyecto_id=proyecto_id).order_by(Conexion.fecha_creacion.desc()).paginate(page=page, per_page=per_page, error_out=False)
    conexiones = pagination.items

    log_action('VER_DETALLE_PROYECTO', g.user.id, 'proyectos', proyecto_id, f"Visualizó el detalle del proyecto '{proyecto.nombre}'.")
    return render_template('proyecto_detalle.html', proyecto=proyecto, conexiones=conexiones, pagination=pagination, titulo=f"Detalle de {proyecto.nombre}")

@proyectos_bp.route('/nuevo', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR')
def nuevo_proyecto():
    form = ProjectForm()
    if form.validate_on_submit():
        if db.session.query(Proyecto).filter(func.lower(Proyecto.nombre) == form.nombre.data.lower()).first():
            flash(f"El proyecto '{form.nombre.data}' ya existe.", 'danger')
        else:
            new_project = Proyecto(nombre=form.nombre.data, descripcion=form.descripcion.data, creador_id=g.user.id)
            db.session.add(new_project)
            db.session.commit()
            log_action('CREAR_PROYECTO', g.user.id, 'proyectos', new_project.id, f"Proyecto '{form.nombre.data}' creado.")
            flash('Proyecto creado con éxito.', 'success')
            return redirect(url_for('proyectos.listar_proyectos'))
    return render_template('proyecto_form.html', form=form, titulo="Nuevo Proyecto")

@proyectos_bp.route('/<int:proyecto_id>/editar', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR')
def editar_proyecto(proyecto_id):
    proyecto = db.session.get(Proyecto, proyecto_id)
    if not proyecto:
        abort(404)
    form = ProjectForm(obj=proyecto)
    if form.validate_on_submit():
        # Lógica para evitar duplicados si el nombre cambia
        existing_project = db.session.query(Proyecto).filter(func.lower(Proyecto.nombre) == form.nombre.data.lower(), Proyecto.id != proyecto_id).first()
        if existing_project:
            flash(f"Ya existe otro proyecto con el nombre '{form.nombre.data}'.", 'danger')
        else:
            proyecto.nombre = form.nombre.data
            proyecto.descripcion = form.descripcion.data
            db.session.commit()
            log_action('EDITAR_PROYECTO', g.user.id, 'proyectos', proyecto_id, f"Proyecto '{proyecto.nombre}' editado.")
            flash('Proyecto actualizado con éxito.', 'success')
            return redirect(url_for('proyectos.listar_proyectos'))
    return render_template('proyecto_form.html', form=form, proyecto=proyecto, titulo="Editar Proyecto")

@proyectos_bp.route('/<int:proyecto_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_proyecto(proyecto_id):
    proyecto = db.session.get(Proyecto, proyecto_id)
    if not proyecto:
        flash('Proyecto no encontrado.', 'danger')
        return redirect(url_for('proyectos.listar_proyectos'))

    if proyecto.conexiones:
        flash('No se puede eliminar un proyecto que tiene conexiones asociadas.', 'danger')
        return redirect(url_for('proyectos.listar_proyectos'))

    try:
        nombre_proyecto = proyecto.nombre
        db.session.delete(proyecto)
        db.session.commit()
        log_action('ELIMINAR_PROYECTO', g.user.id, 'proyectos', proyecto_id, f"Proyecto '{nombre_proyecto}' eliminado.")
        flash(f"El proyecto '{nombre_proyecto}' ha sido eliminado.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocurrió un error al eliminar el proyecto: {e}', 'danger')

    return redirect(url_for('proyectos.listar_proyectos'))

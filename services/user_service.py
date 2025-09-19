from werkzeug.security import generate_password_hash
from sqlalchemy import func
from extensions import db
from models import Usuario, Rol, Proyecto, Conexion
from db import log_action
from flask import g

def get_all_users_with_roles():
    """Obtiene todos los usuarios con sus roles usando el ORM."""
    return db.session.query(Usuario).options(db.joinedload(Usuario.roles)).order_by(Usuario.nombre_completo).all()

def create_user(form):
    """Crea un nuevo usuario usando el ORM."""
    try:
        password_hash = generate_password_hash(form.password.data)
        new_user = Usuario(
            username=form.username.data,
            nombre_completo=form.nombre_completo.data,
            email=form.email.data,
            password_hash=password_hash,
            activo=form.activo.data
        )

        roles_nombres = form.roles.data
        roles = db.session.query(Rol).filter(Rol.nombre.in_(roles_nombres)).all()
        new_user.roles.extend(roles)

        db.session.add(new_user)
        db.session.commit()

        log_action('CREAR_USUARIO', g.user.id, 'usuarios', new_user.id,
                   f"Usuario '{new_user.username}' creado con roles: {', '.join(roles_nombres)}.")
        return True, 'Usuario creado con éxito.'
    except Exception as e:
        db.session.rollback()
        # En un sistema real, se registraría el error 'e'
        return False, f'Ocurrió un error al crear el usuario: {e}'

def get_user_for_edit(user_id):
    """Obtiene un usuario y sus roles para edición."""
    user = db.session.get(Usuario, user_id)
    if not user:
        return None, None

    # Los roles ya están cargados a través de la relación, no se necesita una segunda consulta.
    return user, [role.nombre for role in user.roles]

def update_user(user_id, form, current_user_id):
    """Actualiza un usuario existente usando el ORM."""
    user_to_update = db.session.get(Usuario, user_id)
    if not user_to_update:
        return False, 'Usuario no encontrado.'

    try:
        user_to_update.username = form.username.data
        user_to_update.nombre_completo = form.nombre_completo.data
        user_to_update.email = form.email.data
        user_to_update.activo = form.activo.data

        if form.password.data:
            user_to_update.password_hash = generate_password_hash(form.password.data)

        # Actualizar roles
        new_roles_nombres = set(form.roles.data)
        new_roles = db.session.query(Rol).filter(Rol.nombre.in_(new_roles_nombres)).all()
        user_to_update.roles = new_roles

        db.session.commit()
        log_action('ACTUALIZAR_USUARIO', current_user_id, 'usuarios', user_id, f"Usuario '{user_to_update.username}' actualizado.")
        return True, 'Usuario actualizado con éxito.'
    except Exception as e:
        db.session.rollback()
        return False, f'Ocurrió un error al actualizar el usuario: {e}'

def toggle_user_active_status(user_id, current_user_id):
    """Activa o desactiva un usuario."""
    if user_id == current_user_id:
        return False, 'No puedes desactivar tu propia cuenta.'

    user = db.session.get(Usuario, user_id)
    if not user:
        return False, "Usuario no encontrado."

    try:
        user.activo = not user.activo
        db.session.commit()
        estado_texto = 'activado' if user.activo else 'desactivado'
        log_action('TOGGLE_USUARIO_ACTIVO', current_user_id, 'usuarios', user_id, f"Usuario '{user.username}' ha sido {estado_texto}.")
        return True, f"El usuario ha sido {estado_texto}."
    except Exception as e:
        db.session.rollback()
        return False, f"Ocurrió un error al cambiar el estado del usuario: {e}"

def delete_user(user_id, current_user_id):
    """Elimina un usuario, con validaciones de seguridad."""
    if user_id == current_user_id:
        return False, 'No puedes eliminar tu propia cuenta.'

    user = db.session.get(Usuario, user_id)
    if not user:
        return False, "Usuario no encontrado."

    # Validaciones
    is_admin = any(role.nombre == 'ADMINISTRADOR' for role in user.roles)
    if is_admin:
        admin_count = db.session.query(func.count(Usuario.id)).join(Usuario.roles).filter(Rol.nombre == 'ADMINISTRADOR').scalar()
        if admin_count <= 1:
            return False, 'No se puede eliminar al último administrador del sistema.'

    project_count = db.session.query(func.count(Proyecto.id)).filter(Proyecto.usuarios_asignados.any(id=user_id)).scalar()
    if project_count > 0:
        return False, f"No se puede eliminar al usuario porque está asignado a {project_count} proyecto(s)."

    active_connections = db.session.query(func.count(Conexion.id)).filter(Conexion.realizador_id == user_id, Conexion.estado.in_(['EN_PROCESO', 'REALIZADO'])).scalar()
    if active_connections > 0:
        return False, f"No se puede eliminar al usuario porque tiene {active_connections} conexión(es) activa(s) asignada(s)."

    solicited_connections = db.session.query(func.count(Conexion.id)).filter(Conexion.solicitante_id == user_id).scalar()
    if solicited_connections > 0:
        return False, f"No se puede eliminar al usuario porque ha solicitado {solicited_connections} conexión(es)."

    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        log_action('ELIMINAR_USUARIO', current_user_id, 'usuarios', user_id, f"Usuario '{username}' eliminado.")
        return True, f"El usuario '{username}' ha sido eliminado."
    except Exception as e:
        db.session.rollback()
        return False, f"Ocurrió un error al eliminar el usuario: {e}"

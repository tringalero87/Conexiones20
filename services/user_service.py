from werkzeug.security import generate_password_hash
from dal.sqlite_dal import SQLiteDAL
from db import log_action
from flask import g


def get_all_users_with_roles():
    dal = SQLiteDAL()
    return dal.get_all_users_with_roles()


def create_user(form):
    dal = SQLiteDAL()
    password_hash = generate_password_hash(form.password.data)

    try:
        user_id = dal.create_user(
            form.username.data,
            form.nombre_completo.data,
            form.email.data,
            password_hash,
            int(form.activo.data)
        )
        for rol_nombre in form.roles.data:
            rol = dal.get_role_id_by_name(rol_nombre)
            if rol:
                dal.assign_role_to_user(user_id, rol['id'])

        log_action('CREAR_USUARIO', g.user['id'], 'usuarios', user_id,
                   f"Usuario '{form.username.data}' creado con roles: {', '.join(form.roles.data)}.")
        return True, 'Usuario creado con éxito.'
    except Exception:
        # log error e
        return False, 'Ocurrió un error al crear el usuario.'


def get_user_for_edit(user_id):
    dal = SQLiteDAL()
    user = dal.get_user_by_id(user_id)
    if not user:
        return None, None
    roles = dal.get_user_roles(user_id)
    return user, roles


def update_user(user_id, form, current_user_id):
    dal = SQLiteDAL()
    old_user, old_roles = get_user_for_edit(user_id)

    try:
        dal.update_user(
            user_id,
            form.username.data,
            form.nombre_completo.data,
            form.email.data,
            int(form.activo.data)
        )

        if form.password.data:
            dal.update_user_password(
                user_id, generate_password_hash(form.password.data))

        new_roles = set(form.roles.data)
        if set(old_roles) != new_roles:
            dal.remove_all_roles_from_user(user_id)
            for rol_nombre in new_roles:
                rol = dal.get_role_id_by_name(rol_nombre)
                if rol:
                    dal.assign_role_to_user(user_id, rol['id'])

        # Logging changes
        # ...
        return True, 'Usuario actualizado con éxito.'
    except Exception:
        # log error e
        return False, 'Ocurrió un error al actualizar el usuario.'


def toggle_user_active_status(user_id, current_user_id):
    dal = SQLiteDAL()
    if user_id == current_user_id:
        return False, 'No puedes desactivar tu propia cuenta.'

    user = dal.get_user_by_id(user_id)
    if not user:
        return False, "Usuario no encontrado."

    new_status = not user['activo']
    try:
        dal.toggle_user_active_status(user_id, new_status)
        estado_texto = 'activado' if new_status else 'desactivado'
        log_action('TOGGLE_USUARIO_ACTIVO', current_user_id, 'usuarios',
                   user_id, f"Usuario '{user['username']}' ha sido {estado_texto}.")
        return True, f"El usuario ha sido {estado_texto}."
    except Exception:
        return False, "Ocurrió un error al cambiar el estado del usuario."


def delete_user(user_id, current_user_id):
    dal = SQLiteDAL()
    if user_id == current_user_id:
        return False, 'No puedes eliminar tu propia cuenta.'

    is_admin = dal.is_user_admin(user_id)
    if is_admin:
        admin_count = dal.get_admin_count()
        if admin_count <= 1:
            return False, 'No se puede eliminar al último administrador del sistema.'

    project_count = dal.get_user_project_count(user_id)
    if project_count > 0:
        return False, f"No se puede eliminar al usuario porque está asignado a {project_count} proyecto(s)."

    active_connections = dal.get_user_active_connection_count(user_id)
    if active_connections > 0:
        return False, f"No se puede eliminar al usuario porque tiene {active_connections} conexión(es) activa(s) asignada(s)."

    solicited_connections = dal.get_user_solicited_connection_count(user_id)
    if solicited_connections > 0:
        return False, f"No se puede eliminar al usuario porque ha solicitado {solicited_connections} conexión(es)."

    user = dal.get_user_by_id(user_id)
    if not user:
        return False, "Usuario no encontrado."

    try:
        dal.delete_user(user_id)
        log_action('ELIMINAR_USUARIO', current_user_id, 'usuarios',
                   user_id, f"Usuario '{user['username']}' eliminado.")
        return True, f"El usuario '{user['username']}' ha sido eliminado."
    except Exception:
        return False, "Ocurrió un error al eliminar el usuario."

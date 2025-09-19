import bleach
from dal.sqlite_dal import SQLiteDAL
from db import log_action
from services.connection_service import _notify_users
from db import get_db

def add_comment(conexion_id, user_id, user_name, content):
    """
    Añade un comentario a una conexión, lo sanitiza y notifica a los usuarios.
    Retorna (True, mensaje_exito) o (False, mensaje_error).
    """
    if not content:
        return False, 'El comentario no puede estar vacío.'

    dal = SQLiteDAL()
    try:
        sanitized_content = bleach.clean(content, tags=bleach.sanitizer.ALLOWED_TAGS + ['p', 'br'], strip=True)
        dal.create_comentario(conexion_id, user_id, sanitized_content)

        log_action('AGREGAR_COMENTARIO', user_id, 'conexiones', conexion_id, "Comentario añadido.")

        # Usamos get_db() para pasar el objeto de conexión a _notify_users
        db = get_db()
        _notify_users(db, conexion_id, f"{user_name} ha comentado.", "#comentarios", ['SOLICITANTE', 'REALIZADOR', 'APROBADOR', 'ADMINISTRADOR'])

        return True, 'Comentario añadido.'
    except Exception as e:
        # En un sistema real, aquí se registraría el error 'e'
        return False, 'Ocurrió un error interno al añadir el comentario.'


def delete_comment(conexion_id, comentario_id, user_id):
    """
    Elimina un comentario de una conexión.
    Retorna (True, mensaje_exito) o (False, mensaje_error).
    """
    dal = SQLiteDAL()
    # Primero, verificamos que el comentario pertenezca a la conexión
    comentario = dal.get_comentario(comentario_id, conexion_id)
    if not comentario:
        return False, 'El comentario no existe o no pertenece a esta conexión.'

    try:
        dal.delete_comentario(comentario_id)
        log_action('ELIMINAR_COMENTARIO', user_id, 'comentarios', comentario_id, f"Comentario (ID: {comentario_id}) eliminado.")
        return True, 'Comentario eliminado.'
    except Exception as e:
        # En un sistema real, aquí se registraría el error 'e'
        return False, 'Ocurrió un error interno al eliminar el comentario.'

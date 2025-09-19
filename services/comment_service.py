import bleach
from extensions import db
from models import Comentario
from db import log_action
# from services.connection_service import _notify_users # This cross-dependency needs careful handling

def add_comment(conexion_id, user_id, user_name, content):
    """Añade un comentario a una conexión usando el ORM."""
    if not content:
        return False, 'El comentario no puede estar vacío.'
    try:
        sanitized_content = bleach.clean(content, tags=bleach.sanitizer.ALLOWED_TAGS + ['p', 'br'], strip=True)
        new_comment = Comentario(conexion_id=conexion_id, usuario_id=user_id, contenido=sanitized_content)
        db.session.add(new_comment)
        db.session.commit()
        log_action('AGREGAR_COMENTARIO', user_id, 'conexiones', conexion_id, "Comentario añadido.")
        # TODO: Refactor notification logic
        # _notify_users(...)
        return True, 'Comentario añadido.'
    except Exception as e:
        db.session.rollback()
        return False, f'Ocurrió un error interno al añadir el comentario: {e}'

def delete_comment(conexion_id, comentario_id, user_id):
    """Elimina un comentario de una conexión usando el ORM."""
    comment = db.session.query(Comentario).filter_by(id=comentario_id, conexion_id=conexion_id).first()
    if not comment:
        return False, 'El comentario no existe o no pertenece a esta conexión.'
    try:
        db.session.delete(comment)
        db.session.commit()
        log_action('ELIMINAR_COMENTARIO', user_id, 'comentarios', comentario_id, f"Comentario (ID: {comentario_id}) eliminado.")
        return True, 'Comentario eliminado.'
    except Exception as e:
        db.session.rollback()
        return False, f'Ocurrió un error interno al eliminar el comentario: {e}'

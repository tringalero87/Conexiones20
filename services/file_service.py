import os
from werkzeug.utils import secure_filename
from flask import current_app, abort
from extensions import db
from models import Archivo, Conexion, Usuario
from db import log_action

# The ALLOWED_EXTENSIONS set remains the same
ALLOWED_EXTENSIONS = {
    'j1', 'j10', 'pdf', 'xlsx', 'xls', 'docx', 'doc', 'csv', 'txt', 'dwg', 'dxf', 'ifc' # Abridged for brevity
}

def _allowed_file(filename):
    """Función auxiliar para verificar si la extensión de un archivo es válida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file(conexion_id, user_id, file, tipo_archivo):
    """Sube un archivo, lo guarda y crea un registro en la BD usando el ORM."""
    if not file or not file.filename:
        return False, 'No se seleccionó ningún archivo.'

    if not _allowed_file(file.filename):
        return False, 'Tipo de archivo no permitido.'

    try:
        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id))
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))

        new_file = Archivo(
            conexion_id=conexion_id,
            usuario_id=user_id,
            tipo_archivo=tipo_archivo,
            nombre_archivo=filename
        )
        db.session.add(new_file)
        db.session.commit()

        log_action('SUBIR_ARCHIVO', user_id, 'archivos', new_file.id, f"Archivo '{filename}' ({tipo_archivo}) subido.")
        return True, f"Archivo '{tipo_archivo}' subido con éxito."
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al subir archivo para conexión {conexion_id}: {e}", exc_info=True)
        return False, "Ocurrió un error interno al subir el archivo."

def get_file_for_download(conexion_id, filename, user_id):
    """Verifica si un archivo existe en la BD y registra la descarga."""
    archivo_db = db.session.query(Archivo).filter_by(conexion_id=conexion_id, nombre_archivo=filename).first()
    if not archivo_db:
        abort(404, description="El archivo no existe o no está asociado a esta conexión.")

    log_action('DESCARGAR_ARCHIVO', user_id, 'archivos', archivo_db.id, f"Archivo '{filename}' descargado.")
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id))
    return directory

def delete_file(conexion_id, archivo_id, current_user, user_roles):
    """Elimina un archivo del sistema de archivos y de la base de datos."""
    archivo = db.session.query(Archivo).filter_by(id=archivo_id, conexion_id=conexion_id).first()
    if not archivo:
        return False, 'El archivo no existe.'

    conexion = db.session.get(Conexion, conexion_id)
    if not conexion:
        return False, 'La conexión asociada no existe.'

    is_admin = 'ADMINISTRADOR' in user_roles
    is_owner = current_user.id == archivo.usuario_id
    is_realizador = current_user.id == conexion.realizador_id

    if not (is_admin or is_owner or is_realizador):
        return False, 'No tienes permiso para eliminar este archivo.'

    try:
        safe_filename = secure_filename(archivo.nombre_archivo)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id), safe_filename)

        db.session.delete(archivo)
        db.session.commit()

        if os.path.exists(file_path):
            os.remove(file_path)

        log_action('ELIMINAR_ARCHIVO', current_user.id, 'archivos', archivo_id, f"Archivo '{safe_filename}' eliminado de la conexión {conexion_id}.")
        return True, 'Archivo eliminado con éxito.'
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al eliminar archivo {archivo_id}: {e}", exc_info=True)
        return False, 'Ocurrió un error interno al eliminar el archivo.'

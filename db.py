import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext
import os

def get_db():
    """
    Obtiene una conexión a la base de datos SQLite para la solicitud actual.
    Crea la conexión si no existe y la almacena en 'g'.
    """
    if 'db' not in g:
        db_path = current_app.config['DATABASE_URL']
        # Asegurarse de que el directorio de la base de datos exista
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db

def close_db(e=None):
    """
    Cierra la conexión de la base de datos.
    """
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    """
    Inicializa la base de datos ejecutando el script SQL del archivo 'schema.sql'.
    """
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        # SQLite3's `executescript` puede manejar múltiples sentencias
        db.executescript(f.read().decode('utf8'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Define un comando de terminal 'flask init-db' para inicializar la base de datos."""
    init_db()
    click.echo('Base de datos SQLite inicializada.')

def init_app(app):
    """
    Registra las funciones de la base de datos con la instancia de la aplicación Flask.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

def log_action(accion, usuario_id, tipo_objeto, objeto_id, detalles=None):
    """
    Registra una acción de auditoría en la base de datos.
    """
    db = get_db()
    sql = """
        INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles)
        VALUES (?, ?, ?, ?, ?)
    """
    params = (usuario_id, accion, tipo_objeto, objeto_id, detalles)

    try:
        cursor = db.cursor()
        cursor.execute(sql, params)
        db.commit()
    except Exception as e:
        current_app.logger.error(f"Error al registrar acción de auditoría: {accion} por {usuario_id} - {e}")
        db.rollback()

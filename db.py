import click
from flask import current_app, g
from flask.cli import with_appcontext
import os
import psycopg2
from psycopg2.extras import DictCursor
import sqlite3
import datetime

# --- Adaptadores y Conversores para SQLite ---
# Soluciona DeprecationWarning en Python 3.12+ para timestamps.
def adapt_datetime_iso(val):
    """Adapta un objeto datetime.datetime a un formato de texto ISO 8601."""
    return val.isoformat()

def convert_timestamp(val):
    """Convierte una columna de tipo TIMESTAMP de la BD (bytes) a un objeto datetime."""
    return datetime.datetime.fromisoformat(val.decode())

sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
sqlite3.register_converter("timestamp", convert_timestamp)


def get_db():
    """
    Obtiene una conexión a la base de datos para la solicitud actual.
    Se conecta a SQLite si la app está en modo de prueba (TESTING=True).
    De lo contrario, se conecta a PostgreSQL usando DATABASE_URL.
    """
    if 'db' not in g:
        if current_app.config.get('TESTING'):
            # Conexión a la base de datos de prueba (SQLite)
            db_path = current_app.config.get('DATABASE')
            if not db_path:
                raise RuntimeError("La configuración 'DATABASE' es necesaria para las pruebas.")
            g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row
        else:
            # Conexión a la base de datos de producción (PostgreSQL)
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                raise RuntimeError("DATABASE_URL no está configurada. La aplicación no puede continuar.")
            g.db = psycopg2.connect(database_url, cursor_factory=DictCursor)
    
    return g.db

def close_db(e=None):
    """
    Cierra la conexión a la base de datos si existe.
    Esta función se registra para que Flask la llame automáticamente al final
    de cada solicitud, asegurando que la conexión a la base de datos siempre se cierre
    correctamente, incluso si ocurre un error durante el procesamiento de la solicitud.
    """
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    """
    Inicializa la base de datos ejecutando el script SQL del archivo 'schema.sql'.
    Este script crea todas las tablas y la estructura necesaria para la aplicación.
    Maneja la diferencia en la ejecución de scripts entre SQLite y PostgreSQL.
    """
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        sql_script = f.read().decode('utf8')

    # sqlite3 connection objects tienen 'executescript', psycopg2 no.
    # Usamos esto para determinar el tipo de conexión y ejecutar el script apropiadamente.
    if hasattr(db, 'executescript'):
        # Conexión SQLite (usada en pruebas)
        db.executescript(sql_script)
    else:
        # Conexión PostgreSQL (usada en producción)
        with db.cursor() as cursor:
            # PostgreSQL no maneja bien múltiples sentencias en un solo execute,
            # especialmente con algunos comandos DDL. Iterar es más seguro.
            for statement in sql_script.split(';'):
                if statement.strip():
                    cursor.execute(statement)
        db.commit()

@click.command('init-db')
@with_appcontext
def init_db_command():
    """
    Define un comando de terminal 'flask init-db' para inicializar la base de datos.
    Esto permite crear la base de datos desde la línea de comandos de una manera sencilla y estandarizada.
    @with_appcontext asegura que el contexto de la aplicación esté disponible, permitiendo
    el uso de 'current_app'.
    """
    init_db()
    click.echo('Base de datos inicializada.')

def init_app(app):
    """
    Registra las funciones de la base de datos con la instancia de la aplicación Flask.
    Esta función es llamada por la fábrica de aplicaciones en app.py.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

def log_action(accion, usuario_id, tipo_objeto, objeto_id, detalles=None):
    """
    Registra una acción de auditoría en la base de datos.
    """
    db = get_db()
    is_testing = current_app.config.get('TESTING', False)

    if is_testing:
        # Sintaxis para SQLite
        sql = """
            INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles)
            VALUES (?, ?, ?, ?, ?)
        """
    else:
        # Sintaxis para PostgreSQL
        sql = """
            INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles)
            VALUES (%s, %s, %s, %s, %s)
        """

    params = (usuario_id, accion, tipo_objeto, objeto_id, detalles)

    try:
        cursor = db.cursor()
        cursor.execute(sql, params)
        db.commit()
        cursor.close()
    except Exception as e:
        current_app.logger.error(f"Error al registrar acción de auditoría: {accion} por {usuario_id} - {e}")
        db.rollback()
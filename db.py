import click
from flask import current_app, g
from flask.cli import with_appcontext
import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool
import sqlite3
import datetime
import re
import atexit

# Variable global para el pool de conexiones
pool = None

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
    Si hay un pool de conexiones (PostgreSQL), obtiene una conexión de él.
    Si no, crea una conexión a SQLite para pruebas.
    """
    if 'db' not in g:
        if pool:
            # Obtener conexión del pool para PostgreSQL
            g.db = pool.getconn()
        elif current_app.config.get('TESTING'):
            # Conexión a SQLite para pruebas
            db_path = current_app.config.get('DATABASE')
            if not db_path:
                raise RuntimeError("La configuración 'DATABASE' es necesaria para las pruebas con SQLite.")
            g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row
        else:
            # Esto no debería ocurrir en un entorno de producción bien configurado
            raise RuntimeError("El pool de conexiones de la base de datos no está inicializado.")
    
    return g.db

def close_db(e=None):
    """
    Cierra la conexión a la base de datos.
    Si la conexión vino del pool, la devuelve al pool.
    Si es una conexión SQLite, la cierra.
    """
    db = g.pop('db', None)

    if db is not None:
        if pool and not isinstance(db, sqlite3.Connection):
            # Devolver la conexión al pool
            pool.putconn(db)
        else:
            # Cerrar la conexión (para SQLite)
            db.close()

def init_db():
    """
    Inicializa la base de datos ejecutando el script SQL del archivo 'schema.sql'.
    """
    db = get_db()
    try:
        with current_app.open_resource('schema.sql') as f:
            sql_script = f.read().decode('utf8')

        if hasattr(db, 'executescript'):
            # Conexión SQLite
            db.executescript(sql_script)
        else:
            # Conexión PostgreSQL
            with db.cursor(cursor_factory=DictCursor) as cursor:
                clean_script = re.sub(r'--.*$', '', sql_script, flags=re.MULTILINE)
                statements = [statement.strip() for statement in clean_script.split(';') if statement.strip()]

                for statement in statements:
                    cursor.execute(statement)
            db.commit()
    finally:
        # Asegurarse de que la conexión se devuelva/cierre después de la inicialización
        close_db()

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Define un comando de terminal 'flask init-db' para inicializar la base de datos."""
    init_db()
    click.echo('Base de datos inicializada.')

def init_app(app):
    """
    Registra las funciones de la base de datos con la instancia de la aplicación Flask.
    Inicializa el pool de conexiones para PostgreSQL si se proporciona una DATABASE_URL.
    """
    global pool
    database_url = app.config.get('DATABASE_URL') or os.environ.get('DATABASE_URL')

    if database_url:
        try:
            # Inicializar el pool. minconn=1, maxconn=15.
            # Se crea tanto para producción como para pruebas si DATABASE_URL está presente.
            pool = SimpleConnectionPool(1, 15, dsn=database_url)
            # Registrar una función para cerrar el pool cuando la app termine
            atexit.register(close_pool)
            app.logger.info("Pool de conexiones a PostgreSQL inicializado.")
        except psycopg2.OperationalError as e:
            app.logger.error(f"No se pudo conectar a la base de datos y crear el pool: {e}")
            pool = None

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

def close_pool():
    """Cierra todas las conexiones en el pool."""
    global pool
    if pool:
        pool.closeall()
        # No se puede usar current_app.logger aquí porque el contexto de la app puede no estar disponible
        print("Pool de conexiones a PostgreSQL cerrado.")

def log_action(accion, usuario_id, tipo_objeto, objeto_id, detalles=None):
    """
    Registra una acción de auditoría en la base de datos.
    """
    db = get_db()
    sql = """
        INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (usuario_id, accion, tipo_objeto, objeto_id, detalles)

    try:
        with db.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(sql, params)
        db.commit()
    except Exception as e:
        current_app.logger.error(f"Error al registrar acción de auditoría: {accion} por {usuario_id} - {e}")
        db.rollback()
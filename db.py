import click
from flask import current_app, g
from flask.cli import with_appcontext
import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool
import re
import atexit

# Variable global para el pool de conexiones
pool = None

def get_db():
    """
    Obtiene una conexión a la base de datos PostgreSQL del pool para la solicitud actual.
    """
    if 'db' not in g:
        if not pool:
            raise RuntimeError("El pool de conexiones de la base de datos no está inicializado. "
                               "Asegúrese de que la variable de entorno DATABASE_URL esté configurada.")
        g.db = pool.getconn()
    return g.db

def close_db(e=None):
    """
    Devuelve la conexión de la base de datos al pool.
    """
    db = g.pop('db', None)
    if db is not None:
        pool.putconn(db)

def init_db():
    """
    Inicializa la base de datos ejecutando el script SQL del archivo 'schema.sql'.
    """
    db = get_db()
    try:
        with current_app.open_resource('schema.sql') as f:
            sql_script = f.read().decode('utf8')

        with db.cursor(cursor_factory=DictCursor) as cursor:
            # Limpiar comentarios y dividir en sentencias individuales
            clean_script = re.sub(r'--.*$', '', sql_script, flags=re.MULTILINE)
            statements = [statement.strip() for statement in clean_script.split(';') if statement.strip()]

            for statement in statements:
                cursor.execute(statement)
        db.commit()
    finally:
        # Devuelve la conexión al pool
        close_db()

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Define un comando de terminal 'flask init-db' para inicializar la base de datos."""
    init_db()
    click.echo('Base de datos PostgreSQL inicializada.')

def init_app(app):
    """
    Registra las funciones de la base de datos con la instancia de la aplicación Flask.
    Inicializa el pool de conexiones para PostgreSQL.
    """
    global pool
    # Usa la configuración de la app primero, luego la variable de entorno
    database_url = app.config.get('DATABASE_URL') or os.environ.get('DATABASE_URL')

    if database_url:
        try:
            # Inicializar el pool con un mínimo de 1 y un máximo de 15 conexiones.
            pool = SimpleConnectionPool(1, 15, dsn=database_url)
            # Registrar una función para cerrar el pool cuando la app termine
            atexit.register(close_pool)
            app.logger.info("Pool de conexiones a PostgreSQL inicializado.")
        except psycopg2.OperationalError as e:
            app.logger.error(f"No se pudo conectar a la base de datos y crear el pool: {e}")
            pool = None
    else:
        # En el nuevo setup, DATABASE_URL es obligatorio.
        app.logger.warning("DATABASE_URL no está configurada. La conexión a la base de datos no funcionará.")

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
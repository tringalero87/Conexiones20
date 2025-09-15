import click
from flask import current_app, g
from flask.cli import with_appcontext
import os
import psycopg2
from psycopg2.extras import DictCursor

def get_db():
    """
    Obtiene una conexión a la base de datos para la solicitud actual.
    Utiliza PostgreSQL.
    """
    if 'db' not in g:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError("DATABASE_URL no está configurada. La aplicación no puede continuar.")

        g.db = psycopg2.connect(database_url)
    
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
    """
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        sql_script = f.read().decode('utf8')

    with db.cursor() as cursor:
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

    sql = """
        INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (usuario_id, accion, tipo_objeto, objeto_id, detalles)

    try:
        with db.cursor() as cursor:
            cursor.execute(sql, params)
        db.commit()
    except Exception as e:
        current_app.logger.error(f"Error al registrar acción de auditoría: {accion} por {usuario_id} - {e}")
        db.rollback()
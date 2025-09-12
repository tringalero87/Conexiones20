"""
db.py

Este módulo centraliza toda la lógica de conexión y gestión de la base de datos SQLite.
Su propósito es desacoplar la base de datos de la aplicación principal,
lo que previene errores de importación circular y sigue las mejores prácticas
recomendadas por Flask para el manejo de recursos.
"""

import sqlite3
import click
import datetime
from flask import current_app, g
from flask.cli import with_appcontext # ¡CORRECCIÓN: Añadir esta importación!

# --- FIX for DeprecationWarning ---
# Soluciona la DeprecationWarning de Python 3.12 para los convertidores de fecha/hora.
# Se registran adaptadores y convertidores explícitos como recomienda la documentación.

def adapt_datetime_iso(val):
    """Adapta un objeto datetime.datetime a una cadena ISO 8601."""
    return val.isoformat()

def convert_timestamp(val):
    """Convierte una cadena de texto de timestamp ISO 8601 a un objeto datetime.datetime."""
    return datetime.datetime.fromisoformat(val.decode())

# Registrar los nuevos adaptadores y convertidores
sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
sqlite3.register_converter("timestamp", convert_timestamp)

# --- End of FIX ---

import os
import psycopg2
from psycopg2.extras import DictCursor

def get_db():
    """
    Obtiene una conexión a la base de datos para la solicitud actual.
    Soporta tanto PostgreSQL como SQLite, dependiendo de la configuración.
    """
    if 'db' not in g:
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('postgres'):
            # Conexión a PostgreSQL
            g.db = psycopg2.connect(database_url)
            # No es necesario configurar cursor_factory aquí, se puede hacer al crear el cursor
        else:
            # Conexión a SQLite (comportamiento original)
            g.db = sqlite3.connect(
                current_app.config['DATABASE'],
                detect_types=sqlite3.PARSE_DECLTYPES,
                timeout=10
            )
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
            g.db.execute("PRAGMA journal_mode=WAL;")
    
    return g.db

def close_db(e=None):
    """
    Cierra la conexión a la base de datos si existe.
    Esta función se registra para que Flask la llame automáticamente al final
    de cada solicitud, asegurando que la conexión a la base de datos siempre se cierre
    correctamente, incluso si ocurre un error durante el procesamiento de la solicitud.
    """
    # g.pop() intenta obtener y eliminar 'db' de 'g'. Si no existe, devuelve None.
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

        # PostgreSQL (psycopg2) no tiene 'executescript', se debe ejecutar por separado.
        # SQLite sí lo tiene. Usamos la presencia de 'executescript' para diferenciar.
        if not hasattr(db, 'executescript'): # Es PostgreSQL
            with db.cursor() as cursor:
                # Simple split por ';' puede fallar si hay ';' dentro de strings.
                # Para este schema.sql específico, es seguro.
                for statement in sql_script.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
            db.commit()
        else: # Es SQLite
            db.executescript(sql_script)

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
    # Le dice a Flask que llame a 'close_db' cuando se limpie el contexto de la aplicación
    # después de que se haya devuelto la respuesta.
    app.teardown_appcontext(close_db)
    
    # Añade el nuevo comando 'init-db' a la interfaz de línea de comandos de Flask.
    app.cli.add_command(init_db_command)

def log_action(accion, usuario_id, tipo_objeto, objeto_id, detalles=None):
    """
    Registra una acción de auditoría en la base de datos.
    Soporta tanto PostgreSQL como SQLite.
    """
    db = get_db()

    # Determinar el estilo del placeholder
    is_postgres = hasattr(db, 'cursor')
    placeholder = '%s' if is_postgres else '?'

    sql = f"""
        INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
    """
    params = (usuario_id, accion, tipo_objeto, objeto_id, detalles)

    try:
        if is_postgres:
            with db.cursor() as cursor:
                cursor.execute(sql, params)
        else: # SQLite
            db.execute(sql, params)
        db.commit()
    except Exception as e:
        current_app.logger.error(f"Error al registrar acción de auditoría: {accion} por {usuario_id} - {e}")
        db.rollback()
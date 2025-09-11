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

def get_db():
    """
    Obtiene una conexión a la base de datos para la solicitud actual.
    
    Crea una nueva conexión si no existe una en el contexto 'g' de Flask.
    El contexto 'g' es un objeto especial que se utiliza para almacenar datos
    durante el ciclo de vida de una única solicitud. Esto asegura que solo se
    abra una conexión por solicitud, lo que es mucho más eficiente que abrir
    y cerrar una conexión por cada consulta a la base de datos.
    """
    if 'db' not in g:
        # Si no hay conexión para esta solicitud, se crea una nueva.
        # current_app apunta a la instancia de la aplicación Flask que está manejando la solicitud.
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=10 # Timeout de 10 segundos para evitar bloqueos largos
        )
        # Se configura 'row_factory' para que las filas devueltas por la base de datos
        # se comporten como diccionarios, permitiendo acceder a las columnas por su nombre.
        # Por ejemplo, en lugar de row[1], se puede usar row['nombre_completo'].
        g.db.row_factory = sqlite3.Row
        # Se habilita el soporte para claves foráneas (FOREIGN KEY) para esta conexión.
        # Esto es crucial para mantener la integridad de los datos entre las tablas.
        g.db.execute("PRAGMA foreign_keys = ON;")
        # Habilitar el modo Write-Ahead Logging (WAL) para mejorar la concurrencia.
        # Esto permite que las operaciones de lectura no bloqueen las de escritura y viceversa.
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
    # Se abre el archivo 'schema.sql' que se encuentra en la raíz del proyecto.
    # open_resource abre un recurso desde la carpeta raíz de la aplicación.
    with current_app.open_resource('schema.sql') as f:
        # Se ejecuta el script completo para crear las tablas.
        db.executescript(f.read().decode('utf8'))

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
    Args:
        accion (str): El tipo de acción realizada (ej. 'CREAR_USUARIO', 'APROBAR_CONEXION').
        usuario_id (int): ID del usuario que realizó la acción. Puede ser None para acciones sin autenticación.
        tipo_objeto (str): El tipo de entidad afectada (ej. 'usuarios', 'conexiones', 'proyectos', 'sistema').
        objeto_id (int): ID del objeto afectado. Puede ser None si la acción no se aplica a un objeto específico.
        detalles (str, optional): Detalles adicionales sobre la acción (ej. cambios, motivos).
    """
    db = get_db()
    try:
        db.execute(
            'INSERT INTO auditoria_acciones (usuario_id, accion, tipo_objeto, objeto_id, detalles) VALUES (?, ?, ?, ?, ?)',
            (usuario_id, accion, tipo_objeto, objeto_id, detalles)
        )
        db.commit()
    except Exception as e:
        current_app.logger.error(f"Error al registrar acción de auditoría: {accion} por {usuario_id} - {e}")
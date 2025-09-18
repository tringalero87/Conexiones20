import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
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

    # --- Creación del usuario administrador por defecto ---
    cursor = db.cursor()

    # Verificar si el usuario 'Admin' ya existe para evitar duplicados
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", ('Admin',))
    if cursor.fetchone() is None:
        # 1. Hashear la contraseña
        password_hash = generate_password_hash('624BGHwsj*')

        # 2. Insertar el nuevo usuario administrador
        cursor.execute(
            "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
            ('Admin', 'Admin', 'heptaconexiones@heptapro.com', password_hash, 1)
        )
        user_id = cursor.lastrowid

        # 3. Obtener el ID del rol 'ADMINISTRADOR'
        cursor.execute("SELECT id FROM roles WHERE nombre = ?", ('ADMINISTRADOR',))
        role = cursor.fetchone()

        if role:
            admin_role_id = role['id']
            # 4. Asignar el rol de administrador al nuevo usuario
            cursor.execute(
                "INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)",
                (user_id, admin_role_id)
            )
            click.echo("Usuario administrador por defecto 'Admin' creado.")
        else:
            click.echo("Advertencia: No se pudo encontrar el rol 'ADMINISTRADOR'. El usuario 'Admin' fue creado pero no tiene rol de administrador.")

        # 5. Guardar los cambios
        db.commit()


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

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from db import get_db
from flask import current_app

@click.command('crear-admin')
@with_appcontext
@click.argument('username')
@click.argument('password')
@click.argument('email')
@click.argument('nombre_completo')
def crear_admin_command(username, password, email, nombre_completo):
    """Crea un nuevo usuario administrador."""
    db = get_db()
    cursor = db.cursor()
    is_testing = not current_app or current_app.config.get('TESTING', False)

    # Determinar la sintaxis SQL y el placeholder según el entorno
    if is_testing:
        p = "?"
        sql_check_user = 'SELECT id FROM usuarios WHERE username = ? OR email = ?'
        sql_get_role = "SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'"
        sql_insert_user = 'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)'
        sql_insert_role = 'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)'
    else:
        p = "%s"
        sql_check_user = 'SELECT id FROM usuarios WHERE username = %s OR email = %s'
        sql_get_role = "SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'"
        sql_insert_user = 'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id'
        sql_insert_role = 'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)'

    try:
        cursor.execute(sql_check_user, (username, email))
        if cursor.fetchone():
            click.echo(f"Error: El usuario '{username}' o el email '{email}' ya existen.")
            return

        cursor.execute(sql_get_role)
        rol = cursor.fetchone()
        if not rol:
            click.echo("Error: El rol 'ADMINISTRADOR' no se encuentra. Asegúrate de que la base de datos esté inicializada.")
            return
        admin_rol_id = rol[0]

        password_hash = generate_password_hash(password)
        params_insert_user = (username, nombre_completo, email, password_hash, True)
        cursor.execute(sql_insert_user, params_insert_user)

        # Manejar la obtención del ID del nuevo usuario de forma diferente para SQLite y PostgreSQL
        if is_testing:
            new_user_id = cursor.lastrowid
        else:
            new_user_id = cursor.fetchone()[0]

        cursor.execute(sql_insert_role, (new_user_id, admin_rol_id))
        db.commit()
        click.echo(f"Usuario administrador '{username}' creado exitosamente.")

    except Exception as e:
        db.rollback()
        click.echo(f"Ocurrió un error: {e}")
    finally:
        if cursor:
            cursor.close()

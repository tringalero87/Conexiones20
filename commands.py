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
    try:
        # Verificar si el usuario o el email ya existen
        sql_check_user = "SELECT id FROM usuarios WHERE username = %s OR email = %s"
        cursor.execute(sql_check_user, (username, email))
        if cursor.fetchone():
            click.echo(f"Error: El usuario '{username}' o el email '{email}' ya existen.")
            return

        # Obtener el ID del rol de administrador
        sql_get_role = "SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'"
        cursor.execute(sql_get_role)
        rol = cursor.fetchone()
        if not rol:
            click.echo("Error: El rol 'ADMINISTRADOR' no se encuentra. Asegúrate de que la base de datos esté inicializada.")
            return
        admin_rol_id = rol['id']

        # Crear el hash de la contraseña e insertar el nuevo usuario
        password_hash = generate_password_hash(password)
        sql_insert_user = """
            INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """
        params_insert_user = (username, nombre_completo, email, password_hash, True)
        cursor.execute(sql_insert_user, params_insert_user)

        # Obtener el ID del usuario recién creado
        new_user_id = cursor.fetchone()['id']

        # Asignar el rol de administrador al nuevo usuario
        sql_insert_role = "INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)"
        cursor.execute(sql_insert_role, (new_user_id, admin_rol_id))
        db.commit()
        click.echo(f"Usuario administrador '{username}' creado exitosamente.")

    except Exception as e:
        db.rollback()
        click.echo(f"Ocurrió un error: {e}")
    finally:
        if cursor:
            cursor.close()

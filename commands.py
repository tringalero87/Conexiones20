import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from db import get_db

@click.command('crear-admin')
@with_appcontext
@click.argument('username')
@click.argument('password')
@click.argument('email')
@click.argument('nombre_completo')
def crear_admin_command(username, password, email, nombre_completo):
    """Crea un nuevo usuario administrador de forma compatible con SQLite y PostgreSQL."""
    db = get_db()
    cursor = db.cursor()

    try:
        # Determinar el estilo del placeholder y si la BD es PostgreSQL
        is_postgres = hasattr(db, 'cursor') and db.__class__.__module__.startswith('psycopg2')
        placeholder = '%s' if is_postgres else '?'

        # Verificar si el usuario o email ya existen
        sql_check_user = f'SELECT id FROM usuarios WHERE username = {placeholder} OR email = {placeholder}'
        cursor.execute(sql_check_user, (username, email))
        if cursor.fetchone():
            click.echo(f"Error: El usuario '{username}' o el email '{email}' ya existen.")
            return

        # Obtener el ID del rol 'ADMINISTRADOR'
        cursor.execute("SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'")
        rol = cursor.fetchone()
        if not rol:
            click.echo("Error: El rol 'ADMINISTRADOR' no se encuentra. Asegúrate de que la base de datos esté inicializada.")
            return

        admin_rol_id = rol[0]

        # Hashear la contraseña
        password_hash = generate_password_hash(password)

        # Insertar el nuevo usuario
        sql_insert_user = f'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})'
        params_insert_user = (username, nombre_completo, email, password_hash, 1)

        if is_postgres:
            sql_insert_user += ' RETURNING id'
            cursor.execute(sql_insert_user, params_insert_user)
            new_user_id = cursor.fetchone()[0]
        else:  # SQLite
            cursor.execute(sql_insert_user, params_insert_user)
            new_user_id = cursor.lastrowid

        # Asignar el rol de administrador
        sql_insert_role = f'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES ({placeholder}, {placeholder})'
        cursor.execute(sql_insert_role, (new_user_id, admin_rol_id))

        db.commit()
        click.echo(f"Usuario administrador '{username}' creado exitosamente.")

    except Exception as e:
        db.rollback()
        click.echo(f"Ocurrió un error: {e}")
    finally:
        if cursor:
            cursor.close()

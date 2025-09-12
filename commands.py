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
    """Crea un nuevo usuario administrador."""
    db = get_db()
    cursor = db.cursor()

    try:
        # Verificar si el usuario o email ya existen
        cursor.execute('SELECT id FROM usuarios WHERE username = %s OR email = %s', (username, email))
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
        cursor.execute(
            'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id',
            (username, nombre_completo, email, password_hash, 1)
        )
        new_user_id = cursor.fetchone()[0]

        # Asignar el rol de administrador
        cursor.execute(
            'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)',
            (new_user_id, admin_rol_id)
        )

        db.commit()
        click.echo(f"Usuario administrador '{username}' creado exitosamente.")

    except Exception as e:
        db.rollback()
        click.echo(f"Ocurrió un error: {e}")
    finally:
        cursor.close()

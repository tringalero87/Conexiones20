import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from extensions import db
from models import Usuario, Rol

@click.command('crear-admin')
@with_appcontext
@click.argument('username')
@click.argument('password')
@click.argument('email')
@click.argument('nombre_completo')
def crear_admin_command(username, password, email, nombre_completo):
    """Crea un nuevo usuario administrador usando el ORM."""
    try:
        if Usuario.query.filter((Usuario.username == username) | (Usuario.email == email)).first():
            click.secho(f"Error: El usuario '{username}' o el email '{email}' ya existen.", fg='red')
            return

        admin_role = Rol.query.filter_by(nombre='ADMINISTRADOR').first()
        if not admin_role:
            click.secho("Error: El rol 'ADMINISTRADOR' no se encuentra. Ejecute 'flask init-db' primero.", fg='red')
            return

        new_user = Usuario(
            username=username,
            nombre_completo=nombre_completo,
            email=email,
            password_hash=generate_password_hash(password),
            activo=True
        )
        new_user.roles.append(admin_role)

        db.session.add(new_user)
        db.session.commit()

        click.secho(f"Usuario administrador '{username}' creado exitosamente.", fg='green')

    except Exception as e:
        db.session.rollback()
        click.secho(f"Ocurrió un error al crear el administrador: {e}", fg='red')

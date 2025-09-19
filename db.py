import click
import os
import secrets
import string
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from extensions import db
from models import Usuario, Rol, Configuracion, AuditoriaAccion

@click.command('init-db')
@with_appcontext
def init_db_command():
    """
    Limpia los datos existentes y crea nuevas tablas y datos iniciales.
    ADVERTENCIA: Este comando destruirá todos los datos existentes.
    Para producción, use 'flask db upgrade'.
    """
    if os.environ.get('FLASK_ENV') == 'production':
        click.secho(
            'ADVERTENCIA: Estás en un entorno de producción. '
            'Ejecutar init-db destruirá todos los datos. '
            'Usa "flask db upgrade" en su lugar. '
            'Para continuar, establece la variable de entorno I_AM_SURE a "true".',
            fg='red'
        )
        if os.environ.get('I_AM_SURE') != 'true':
            return

    db.drop_all()
    db.create_all()

    create_initial_data()
    create_default_admin()
    click.secho('Base de datos inicializada con éxito.', fg='green')

def create_initial_data():
    """Crea los roles y la configuración por defecto."""
    roles = ['ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE']
    for role_name in roles:
        if not Rol.query.filter_by(nombre=role_name).first():
            db.session.add(Rol(nombre=role_name))

    configs = {'PER_PAGE': '10', 'MAINTENANCE_MODE': '0'}
    for key, value in configs.items():
        if not Configuracion.query.filter_by(clave=key).first():
            db.session.add(Configuracion(clave=key, valor=value))

    db.session.commit()
    click.echo("Roles y configuración por defecto creados.")

def create_default_admin():
    """Crea el usuario administrador por defecto si no existe."""
    if Usuario.query.filter_by(username='Admin').first():
        return

    admin_password = os.environ.get('DEFAULT_ADMIN_PASSWORD')
    if not admin_password:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        admin_password = ''.join(secrets.choice(alphabet) for _ in range(16))
        click.secho("ADVERTENCIA: DEFAULT_ADMIN_PASSWORD no está configurada.", fg='yellow')
        click.echo("Se ha generado una contraseña temporal segura para el usuario 'Admin'.")
        click.secho(f"Contraseña generada: {admin_password}", fg='green')

    admin_user = Usuario(
        username='Admin',
        nombre_completo='Admin',
        email='heptaconexiones@heptapro.com',
        password_hash=generate_password_hash(admin_password),
        activo=True
    )

    admin_role = Rol.query.filter_by(nombre='ADMINISTRADOR').first()
    if admin_role:
        admin_user.roles.append(admin_role)
    else:
        click.secho("Advertencia: No se pudo encontrar el rol 'ADMINISTRADOR'.", fg='red')

    db.session.add(admin_user)
    db.session.commit()
    click.echo("Usuario administrador por defecto 'Admin' creado.")

def init_app(app):
    """Registra los comandos de la base de datos con la aplicación Flask."""
    app.cli.add_command(init_db_command)

def log_action(accion, usuario_id, tipo_objeto, objeto_id, detalles=None):
    """Registra una acción de auditoría en la base de datos usando el ORM."""
    try:
        log_entry = AuditoriaAccion(
            usuario_id=usuario_id,
            accion=accion,
            tipo_objeto=tipo_objeto,
            objeto_id=objeto_id,
            detalles=detalles
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error al registrar acción de auditoría: {e}")

from wtforms.validators import ValidationError
from sqlalchemy import func
from extensions import db
from models import Usuario

def unique_username(form, field):
    """Valida que el nombre de usuario sea único."""
    if form.original_username and field.data.lower() == form.original_username.lower():
        return
    if db.session.query(Usuario).filter(func.lower(Usuario.username) == field.data.lower()).first():
        raise ValidationError('Este nombre de usuario ya está en uso. Por favor, elige otro.')

def unique_email(form, field):
    """Valida que el email sea único."""
    if form.original_email and field.data.lower() == form.original_email.lower():
        return
    if db.session.query(Usuario).filter(func.lower(Usuario.email) == field.data.lower()).first():
        raise ValidationError('Este correo electrónico ya está registrado. Por favor, elige otro.')

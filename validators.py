from wtforms.validators import ValidationError
from db import get_db

def unique_username(form, field):
    db = get_db()
    if hasattr(form, 'original_username') and (not form.original_username or field.data.lower() != form.original_username.lower()):
        sql = 'SELECT id FROM usuarios WHERE LOWER(username) = ?'
        cursor = db.cursor()
        cursor.execute(sql, (field.data.lower(),))
        user = cursor.fetchone()
        cursor.close()
        if user:
            raise ValidationError('Este nombre de usuario ya está en uso. Por favor, elige otro.')

def unique_email(form, field):
    db = get_db()
    if hasattr(form, 'original_email') and (not form.original_email or field.data.lower() != form.original_email.lower()):
        sql = 'SELECT id FROM usuarios WHERE LOWER(email) = ?'
        cursor = db.cursor()
        cursor.execute(sql, (field.data.lower(),))
        user = cursor.fetchone()
        cursor.close()
        if user:
            raise ValidationError('Este correo electrónico ya está registrado. Por favor, elige otro.')

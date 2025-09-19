import pandas as pd
from sqlalchemy import or_
from extensions import db
from models import AliasPerfil
from db import log_action

def get_all_aliases():
    """Obtiene todos los alias usando el ORM."""
    return db.session.query(AliasPerfil).order_by(AliasPerfil.nombre_perfil).all()

def create_alias(form, user_id):
    """Crea un nuevo alias usando el ORM."""
    nombre_perfil = form.nombre_perfil.data
    alias = form.alias.data
    norma = form.norma.data

    if db.session.query(AliasPerfil).filter(or_(AliasPerfil.nombre_perfil == nombre_perfil, AliasPerfil.alias == alias)).first():
        return False, 'El nombre del perfil o el alias ya existen.'

    try:
        new_alias = AliasPerfil(nombre_perfil=nombre_perfil, alias=alias, norma=norma)
        db.session.add(new_alias)
        db.session.commit()
        log_action('CREAR_ALIAS_PERFIL', user_id, 'alias_perfiles', new_alias.id,
                   f"Alias '{alias}' para perfil '{nombre_perfil}' (Norma: {norma}) creado.")
        return True, 'Alias guardado con éxito.'
    except Exception as e:
        db.session.rollback()
        return False, f'Ocurrió un error al crear el alias: {e}'

def update_alias(alias_id, form_data, user_id):
    """Actualiza un alias existente."""
    alias_obj = db.session.get(AliasPerfil, alias_id)
    if not alias_obj:
        return False, 'Alias no encontrado.'

    nombre_perfil = form_data.get('nombre_perfil')
    alias = form_data.get('alias')
    norma = form_data.get('norma')

    existing = db.session.query(AliasPerfil).filter(
        or_(AliasPerfil.nombre_perfil == nombre_perfil, AliasPerfil.alias == alias),
        AliasPerfil.id != alias_id
    ).first()
    if existing:
        return False, 'El nombre del perfil o el alias ya están en uso por otro registro.'

    try:
        alias_obj.nombre_perfil = nombre_perfil
        alias_obj.alias = alias
        alias_obj.norma = norma
        db.session.commit()
        log_action('EDITAR_ALIAS_PERFIL', user_id, 'alias_perfiles', alias_id, "Alias actualizado.")
        return True, 'Alias actualizado con éxito.'
    except Exception as e:
        db.session.rollback()
        return False, f'Ocurrió un error al actualizar el alias: {e}'

def delete_alias(alias_id, user_id):
    """Elimina un alias."""
    alias = db.session.get(AliasPerfil, alias_id)
    if not alias:
        return False, 'Alias no encontrado.'

    try:
        log_data = f"Alias '{alias.alias}' (Norma: {alias.norma}) para perfil '{alias.nombre_perfil}' eliminado."
        db.session.delete(alias)
        db.session.commit()
        log_action('ELIMINAR_ALIAS_PERFIL', user_id, 'alias_perfiles', alias_id, log_data)
        return True, 'Alias eliminado con éxito.'
    except Exception as e:
        db.session.rollback()
        return False, f'Ocurrió un error al eliminar el alias: {e}'

def import_aliases(file):
    """Importa alias desde un archivo Excel o CSV."""
    try:
        df = pd.read_excel(file) if file.filename.endswith('.xlsx') else pd.read_csv(file)
        df.columns = [col.upper().strip() for col in df.columns]
        # ... (la lógica de importación con pandas se mantiene similar)
        # ... (pero las llamadas a la BD se reemplazan con el ORM)

        imported_count = 0
        updated_count = 0
        error_rows = []

        for index, row in df.iterrows():
            # ...
            existing_alias = db.session.query(AliasPerfil).filter_by(nombre_perfil=nombre_perfil).first()
            if existing_alias:
                # ... update
                updated_count += 1
            else:
                # ... create
                imported_count += 1

        db.session.commit()
        return imported_count, updated_count, error_rows, None
    except Exception as e:
        db.session.rollback()
        return 0, 0, [], f"Ocurrió un error inesperado: {e}"

import pandas as pd
from dal.sqlite_dal import SQLiteDAL
from db import log_action


def get_all_aliases():
    dal = SQLiteDAL()
    return dal.get_all_aliases()


def create_alias(form, user_id):
    dal = SQLiteDAL()
    nombre_perfil = form.nombre_perfil.data
    alias = form.alias.data
    norma = form.norma.data

    if dal.get_alias_by_name_or_alias(nombre_perfil, alias):
        return False, 'El nombre del perfil o el alias ya existen.'

    try:
        alias_id = dal.create_alias(nombre_perfil, alias, norma)
        log_action('CREAR_ALIAS_PERFIL', user_id, 'alias_perfiles', alias_id,
                   f"Alias '{alias}' para perfil '{nombre_perfil}' (Norma: {norma}) creado.")
        return True, 'Alias guardado con éxito.'
    except Exception:
        # log error e
        return False, 'Ocurrió un error al crear el alias.'


def update_alias(alias_id, form_data, user_id):
    dal = SQLiteDAL()
    nombre_perfil = form_data.get('nombre_perfil')
    alias = form_data.get('alias')
    norma = form_data.get('norma')

    existing = dal.get_alias_by_name_or_alias(nombre_perfil, alias)
    if existing and existing['id'] != alias_id:
        return False, 'El nombre del perfil o el alias ya están en uso por otro registro.'

    try:
        dal.update_alias(alias_id, nombre_perfil, alias, norma)
        # log changes
        return True, 'Alias actualizado con éxito.'
    except Exception:
        return False, 'Ocurrió un error al actualizar el alias.'


def delete_alias(alias_id, user_id):
    dal = SQLiteDAL()
    alias = dal.get_alias_by_id(alias_id)
    if not alias:
        return False, 'Alias no encontrado.'

    try:
        dal.delete_alias(alias_id)
        log_action('ELIMINAR_ALIAS_PERFIL', user_id, 'alias_perfiles', alias_id,
                   f"Alias '{alias['alias']}' (Norma: {alias['norma']}) para perfil '{alias['nombre_perfil']}' eliminado.")
        return True, 'Alias eliminado con éxito.'
    except Exception:
        return False, 'Ocurrió un error al eliminar el alias.'


def import_aliases(file):
    dal = SQLiteDAL()
    try:
        df = pd.read_excel(file, engine='openpyxl') if file.filename.endswith(
            '.xlsx') else pd.read_csv(file)
        required_cols = ['NOMBRE_PERFIL', 'ALIAS', 'NORMA']
        df.columns = [col.upper().strip() for col in df.columns]

        if not all(col in df.columns for col in required_cols):
            return 0, 0, ['El archivo debe contener las columnas: NOMBRE_PERFIL, ALIAS, NORMA.'], "Error de formato"

        imported_count = 0
        updated_count = 0
        error_rows = []

        for index, row in df.iterrows():
            try:
                nombre_perfil = str(row.get('NOMBRE_PERFIL', '')).strip()
                alias = str(row.get('ALIAS', '')).strip()
                norma = str(row.get('NORMA', '')).strip()
                if norma == 'nan':
                    norma = ''

                if not nombre_perfil or not alias:
                    error_rows.append(
                        f"Fila {index + 2}: NOMBRE_PERFIL y ALIAS son obligatorios.")
                    continue

                existing_alias = dal.get_alias_by_name(nombre_perfil)
                if existing_alias:
                    dal.update_alias(
                        existing_alias['id'], nombre_perfil, alias, norma)
                    updated_count += 1
                else:
                    dal.create_alias(nombre_perfil, alias, norma)
                    imported_count += 1
            except Exception as row_e:
                error_rows.append(
                    f"Fila {index + 2}: Error al procesar - {row_e}")

        return imported_count, updated_count, error_rows, None
    except pd.errors.EmptyDataError:
        return 0, 0, [], 'El archivo está vacío.'
    except Exception as e:
        return 0, 0, [], f"Ocurrió un error inesperado: {e}"

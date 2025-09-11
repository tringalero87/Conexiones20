# Hepta_Conexiones/crear_admin.py
import os
import sqlite3
from werkzeug.security import generate_password_hash
import getpass # Para ocultar la contraseña mientras se escribe

# --- CONFIGURACIÓN ---
# CORRECCIÓN: Se actualiza la ruta para que coincida con la configuración de app.py.
# La base de datos se encuentra en la carpeta 'instance' que Flask crea automáticamente,
# la cual normalmente está en la raíz del proyecto, no necesariamente al lado de este script.
# Si el script se ejecuta desde la raíz del proyecto, os.path.dirname(__file__) devolverá
# "Hepta_Conexiones" y la ruta será correcta si "instance" está dentro de "Hepta_Conexiones".
# Sin embargo, si "instance" está en la raíz del proyecto (un nivel arriba), la ruta sería diferente.
# Se asume que la estructura de la aplicación es:
# /proyecto_raiz
#   /Hepta_Conexiones (donde está app.py, routes, etc.)
#   /instance (donde está heptaconexiones.sqlite)
#   crear_admin.py (si este script está en la raíz)
#
# Pero el código actual en app.py define DATABASE como os.path.join(app.instance_path, 'heptaconexiones.sqlite')
# donde app.instance_path es la carpeta `instance` *asociada a la aplicación*.
# Si crear_admin.py está en Hepta_Conexiones, entonces app.instance_path sería generalmente
# `Hepta_Conexiones/instance` por defecto si `instance_relative_config=True` se configura
# con la carpeta `instance` a la misma altura que `app.py`.

# Para asegurar que la ruta sea correcta, y asumiendo que `crear_admin.py` se encuentra
# en el directorio `Hepta_Conexiones` y la carpeta `instance` es una subcarpeta de `Hepta_Conexiones`.
# Si la carpeta `instance` está *fuera* de `Hepta_Conexiones` (en la raíz del proyecto),
# se necesitaría una ruta diferente o que el usuario pase la ruta manualmente.
# Manteniendo la lógica original, que funciona si 'instance' es un subdirectorio de donde está 'app.py' o 'crear_admin.py'
INSTANCE_FOLDER_PATH = os.path.join(os.path.dirname(__file__), 'instance')
DATABASE_PATH = os.path.join(INSTANCE_FOLDER_PATH, 'heptaconexiones.sqlite')
# --- FIN DE LA CONFIGURACIÓN ---

def get_db_connection():
    """Establece conexión con la base de datos."""
    # Primero, se asegura de que la carpeta 'instance' exista.
    if not os.path.exists(INSTANCE_FOLDER_PATH):
        print(f"Error: La carpeta 'instance' no existe en '{INSTANCE_FOLDER_PATH}'.")
        print("Por favor, asegúrate de que la aplicación Flask haya sido ejecutada al menos una vez (ej. 'flask run') para que se cree la carpeta 'instance' y, si no existe la DB, ejecuta 'flask init-db'.")
        return None
        
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: La base de datos no se encuentra en '{DATABASE_PATH}'.")
        print("Por favor, ejecuta primero el comando 'flask init-db' para crear la base de datos.")
        return None
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_admin():
    """Función principal para crear el usuario administrador."""
    print("--- Creación de Usuario Administrador ---")
    
    conn = get_db_connection()
    if conn is None:
        return

    try:
        # Pedir datos al usuario
        username = input("Nombre de usuario para el administrador: ").strip()
        nombre_completo = input("Nombre completo del administrador: ").strip()
        email = input("Email del administrador: ").strip()
        
        # Pedir contraseña de forma segura
        password = getpass.getpass("Contraseña para el administrador: ")
        password_confirm = getpass.getpass("Confirma la contraseña: ")

        if not all([username, nombre_completo, email, password]):
            print("\nError: Todos los campos son obligatorios.")
            return

        if password != password_confirm:
            print("\nError: Las contraseñas no coinciden.")
            return

        # Verificar si el usuario o email ya existen
        user_exists = conn.execute('SELECT id FROM usuarios WHERE username = ? OR email = ?', (username, email)).fetchone()
        if user_exists:
            print("\nError: El nombre de usuario o el email ya existen en la base de datos.")
            return
            
        # Obtener el ID del rol 'ADMINISTRADOR'
        rol = conn.execute("SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'").fetchone()
        if not rol:
            print("\nError: El rol 'ADMINISTRADOR' no se encuentra en la base de datos.")
            print("Asegúrate de haber ejecutado 'flask init-db' para poblar la tabla de roles.")
            return
        
        admin_rol_id = rol['id']

        # Hashear la contraseña
        password_hash = generate_password_hash(password)

        # Insertar el nuevo usuario
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)',
            (username, nombre_completo, email, password_hash, 1)
        )
        new_user_id = cursor.lastrowid
        
        # Asignar el rol de administrador
        cursor.execute(
            'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)',
            (new_user_id, admin_rol_id)
        )

        conn.commit()
        print(f"\n¡Éxito! El usuario administrador '{username}' ha sido creado.")

    except sqlite3.Error as e:
        print(f"\nOcurrió un error en la base de datos: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    create_admin()
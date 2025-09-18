import sqlite3

db_path = '//app/instance/heptaconexiones.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check for user
cursor.execute("SELECT * FROM usuarios WHERE username = 'Admin'")
user = cursor.fetchone()

if user:
    print("User 'Admin' found.")
    # Check for role
    cursor.execute("""
        SELECT r.nombre FROM roles r
        JOIN usuario_roles ur ON r.id = ur.rol_id
        WHERE ur.usuario_id = ?
    """, (user['id'],))
    role = cursor.fetchone()
    if role and role['nombre'] == 'ADMINISTRADOR':
        print("User 'Admin' has 'ADMINISTRADOR' role.")
    else:
        print("User 'Admin' does NOT have 'ADMINISTRADOR' role.")
else:
    print("User 'Admin' not found.")

conn.close()

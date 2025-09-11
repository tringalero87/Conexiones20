import pytest
from db import get_db
from werkzeug.security import generate_password_hash

# Fixtures are now in conftest.py

# --- Casos de Prueba ---

def test_config(app):
    assert app.config['TESTING']

def test_login_logout(client, auth):
    rv = auth.login('admin', 'password')
    assert rv.status_code == 200
    assert b'Bienvenido de nuevo' in rv.data 

    rv = auth.logout()
    assert rv.status_code == 200
    assert b'Has cerrado la sesi\xc3\xb3n.' in rv.data

def test_unauthorized_access(client):
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.location

def test_admin_permissions(client, auth):
    auth.login('admin', 'password')
    response = client.get('/admin/usuarios')
    assert response.status_code == 200
    assert b'Gesti\xc3\xb3n de Usuarios' in response.data

def test_non_admin_permissions(client, auth):
    auth.login('solicitante', 'password')
    response = client.get('/admin/usuarios', follow_redirects=False)
    assert response.status_code == 403
    # Check for the message in the 403 error template
    assert b'Lo sentimos, no tienes los permisos necesarios para acceder a esta p\xc3\xa1gina.' in response.data
    assert b'Gesti\xc3\xb3n de Usuarios' not in response.data

# --- Pruebas de Esqueleto para Futura Implementación ---

@pytest.mark.skip(reason="Prueba no implementada")
def test_connection_creation_and_code_generation(client, auth):
    """
    Prueba la creación de una conexión y verifica que el código
    descriptivo se genere correctamente.
    """
    auth.login()
    # 1. Navegar a nueva conexión desde el catálogo
    # 2. Enviar el formulario
    # 3. Verificar que la conexión existe en la DB
    # 4. Verificar que el código_conexion sigue el formato esperado
    pass

def test_full_connection_workflow(client, app, auth):
    """
    Prueba el ciclo de vida completo de una conexión:
    SOLICITADO -> EN_PROCESO -> REALIZADO -> APROBADO
    """
    with app.app_context():
        db = get_db()
        # 1. Setup: Crear usuarios, proyecto y una conexión
        solicitante_id = db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
                                   ('solicitante_full', generate_password_hash('password'), 'Solicitante Full', 'solicitante_full@test.com', 1)).lastrowid
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, (SELECT id FROM roles WHERE nombre = 'SOLICITANTE'))", (solicitante_id,))

        realizador_id = db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
                                   ('realizador_full', generate_password_hash('password'), 'Realizador Full', 'realizador_full@test.com', 1)).lastrowid
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, (SELECT id FROM roles WHERE nombre = 'REALIZADOR'))", (realizador_id,))

        aprobador_id = db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
                                  ('aprobador_full', generate_password_hash('password'), 'Aprobador Full', 'aprobador_full@test.com', 1)).lastrowid
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, (SELECT id FROM roles WHERE nombre = 'APROBADOR'))", (aprobador_id,))

        proyecto_id = db.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Proyecto Full Workflow', 'Desc')").lastrowid
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (proyecto_id, solicitante_id))
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (proyecto_id, realizador_id))
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (proyecto_id, aprobador_id))

        conexion_id = db.execute("INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id) VALUES (?, ?, ?, ?, ?, ?)",
                                 ('WORKFLOW-001', proyecto_id, 'Test', 'Test', 'T1', solicitante_id)).lastrowid
        db.commit()

    # 2. Login como Realizador, tomar tarea. Verificar estado 'EN_PROCESO'.
    auth.login('realizador_full', 'password')
    response = client.post(f'/conexiones/{conexion_id}/cambiar_estado', data={'estado': 'EN_PROCESO'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido tomada' in response.data
    with app.app_context():
        assert get_db().execute('SELECT estado FROM conexiones WHERE id = ?', (conexion_id,)).fetchone()['estado'] == 'EN_PROCESO'
        assert get_db().execute('SELECT realizador_id FROM conexiones WHERE id = ?', (conexion_id,)).fetchone()['realizador_id'] == realizador_id

    # 3. Marcar como realizada. Verificar estado 'REALIZADO'.
    response = client.post(f'/conexiones/{conexion_id}/cambiar_estado', data={'estado': 'REALIZADO'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'lista para ser aprobada' in response.data
    with app.app_context():
        assert get_db().execute('SELECT estado FROM conexiones WHERE id = ?', (conexion_id,)).fetchone()['estado'] == 'REALIZADO'
    auth.logout()

    # 4. Login como Aprobador, aprobar. Verificar estado 'APROBADO'.
    auth.login('aprobador_full', 'password')
    response = client.post(f'/conexiones/{conexion_id}/cambiar_estado', data={'estado': 'APROBADO'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido APROBADA' in response.data
    with app.app_context():
        conexion = get_db().execute('SELECT estado, aprobador_id FROM conexiones WHERE id = ?', (conexion_id,)).fetchone()
        assert conexion['estado'] == 'APROBADO'
        assert conexion['aprobador_id'] == aprobador_id

@pytest.mark.skip(reason="Prueba no implementada")
def test_file_upload_api(client, auth):
    """Prueba la API de subida de archivos, incluyendo casos de error."""
    # 1. Crear una conexión para tener un ID válido.
    # 2. Login como realizador.
    # 3. Enviar un archivo válido a /api/upload_file/...
    # 4. Verificar respuesta 201 y que el archivo existe en la DB y en disco.
    # 5. Intentar subir un archivo con extensión no permitida. Verificar error 400.
    # 6. Intentar subir un archivo con un usuario sin permisos. Verificar error 403.
    pass

@pytest.mark.skip(reason="Prueba no implementada")
def test_connection_rejection_workflow(client, auth):
    """Prueba el flujo de rechazo y corrección de una conexión."""
    # 1. Llevar una conexión hasta el estado 'REALIZADO'.
    # 2. Login como Aprobador, rechazarla con un motivo.
    # 3. Verificar que el estado vuelve a 'EN_PROCESO' y que 'detalles_rechazo' está poblado.
    # 4. Verificar que el realizador recibe una notificación.
    pass
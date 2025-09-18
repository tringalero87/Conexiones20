import pytest
from db import get_db
from werkzeug.security import generate_password_hash
import io
import json
import os

def test_current_realizador_can_delete_files(client, app, auth):
    """
    Tests that the currently assigned realizador can delete a file, even if
    they were not the original uploader.
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # 1. Create two 'REALIZADOR' users and a project
        password_hash = generate_password_hash('p')
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('realizador1', ?, 'Realizador One', 'r1@test.com', 1)", (password_hash,))
        realizador1_id = cursor.lastrowid
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('realizador2', ?, 'Realizador Two', 'r2@test.com', 1)", (password_hash,))
        realizador2_id = cursor.lastrowid

        cursor.execute("SELECT id FROM roles WHERE nombre = 'REALIZADOR'")
        realizador_role_id = cursor.fetchone()['id']
        cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (realizador1_id, realizador_role_id))
        cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (realizador2_id, realizador_role_id))

        cursor.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Test Project', 'Desc')")
        project_id = cursor.lastrowid

        # 2. Create a connection and assign to realizador1
        cursor.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id, realizador_id, estado) VALUES (?, ?, 'Test', 'Test', 'Test', ?, ?, 'EN_PROCESO')",
            ('CONN-001', project_id, realizador1_id, realizador1_id)
        )
        connection_id = cursor.lastrowid
        db.commit()

    # 3. Log in as realizador1 and upload a file
    auth.login('realizador1', 'p')
    response = client.post(
        f'/conexiones/{connection_id}/subir_archivo',
        data={
            'tipo_archivo': 'Memoria de Calculo',
            'archivo': (io.BytesIO(b"dummy file content"), 'testfile.pdf')
        },
        content_type='multipart/form-data',
        follow_redirects=False # Changed to False
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert 'Archivo \'Memoria de Calculo\' subido con éxito.' in [msg for cat, msg in session['_flashes']]

    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM archivos WHERE conexion_id = ?", (connection_id,))
        file = cursor.fetchone()
        assert file is not None
        file_id = file['id']

    auth.logout()

    # 4. Log in as admin and reassign the connection to realizador2
    auth.login('admin', 'password')
    client.post(f'/conexiones/{connection_id}/asignar', data={'username_a_asignar': 'realizador2'}, follow_redirects=True)
    auth.logout()

    # 5. Log in as realizador2 and try to delete the file
    auth.login('realizador2', 'p')
    response = client.post(f'/conexiones/{connection_id}/eliminar_archivo/{file_id}', follow_redirects=False) # Changed to False
    assert response.status_code == 302

    # With the buggy code, this fails with a "No tienes permiso" flash.
    # With the fix, this should succeed.
    with client.session_transaction() as session:
        flashes = [msg for cat, msg in session['_flashes']]
        assert 'Archivo eliminado con éxito.' in flashes

    # Verify the file is gone from the database
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM archivos WHERE id = ?", (file_id,))
        file = cursor.fetchone()
        assert file is None


def test_solicitante_cannot_edit_other_users_connection(client, app, auth):
    """
    Tests that a user with the 'SOLICITANTE' role cannot edit a connection
    created by another user.
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        password_hash = generate_password_hash('p')

        # Create two 'SOLICITANTE' users
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('solicitante1', ?, 'Solicitante One', 's1@test.com', 1)", (password_hash,))
        solicitante1_id = cursor.lastrowid
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('solicitante2', ?, 'Solicitante Two', 's2@test.com', 1)", (password_hash,))
        solicitante2_id = cursor.lastrowid

        cursor.execute("SELECT id FROM roles WHERE nombre = 'SOLICITANTE'")
        solicitante_role_id = cursor.fetchone()['id']
        cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (solicitante1_id, solicitante_role_id))
        cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (solicitante2_id, solicitante_role_id))

        # Create a project
        cursor.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Project Edit Test', 'Desc')")
        project_id = cursor.lastrowid

        # Create a connection by solicitante1
        cursor.execute(
            """
            INSERT INTO conexiones
            (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id, estado, detalles_json)
            VALUES (?, ?, 'MOMENTO', 'VIGA-COLUMNA (ALA)', 'T0', ?, 'SOLICITADO', ?)
            """,
            ('CONN-EDIT-TEST', project_id, solicitante1_id, '{"Perfil 1": "IPE300"}')
        )
        connection_id = cursor.lastrowid
        db.commit()

    # Log in as solicitante2
    auth.login('solicitante2', 'p')

    # Try to access the edit page (GET)
    response_get = client.get(f'/conexiones/{connection_id}/editar')
    # With the bug, this will be 200 OK. After the fix, it should be 403.
    assert response_get.status_code == 403

    # Try to submit an edit (POST)
    response_post = client.post(
        f'/conexiones/{connection_id}/editar',
        data={
            'descripcion': 'Intento de edicion no autorizada',
            'perfil_1': 'IPE300'
        },
        follow_redirects=True
    )
    # The current code redirects to the detail page with a success flash.
    # The fixed code should return 403.
    assert response_post.status_code == 403

    # Verify that the description was not changed
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT descripcion FROM conexiones WHERE id = ?", (connection_id,))
        conexion = cursor.fetchone()
        assert conexion['descripcion'] != 'Intento de edicion no autorizada'


def test_upload_dotfile_is_rejected(client, app, auth):
    """
    Tests that uploading a file starting with a dot (a 'dotfile') is rejected.
    """
    # Setup: Create a user and a connection
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        password_hash = generate_password_hash('p')
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('uploader', ?, 'File Uploader', 'uploader@test.com', 1)", (password_hash,))
        user_id = cursor.lastrowid
        cursor.execute("SELECT id FROM roles WHERE nombre = 'REALIZADOR'")
        realizador_role_id = cursor.fetchone()['id']
        cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (user_id, realizador_role_id))
        cursor.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Dotfile Test Project', 'Desc')")
        project_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id, realizador_id, estado) VALUES (?, ?, 'Test', 'Test', 'Test', ?, ?, 'EN_PROCESO')",
            ('CONN-DOTFILE', project_id, user_id, user_id)
        )
        connection_id = cursor.lastrowid
        db.commit()

    # Log in as the uploader
    auth.login('uploader', 'p')

    # Attempt to upload a dotfile
    response = client.post(
        f'/conexiones/{connection_id}/subir_archivo',
        data={
            'tipo_archivo': 'Plano',
            'archivo': (io.BytesIO(b"this is a dotfile"), '.testupload.pdf')
        },
        content_type='multipart/form-data',
        follow_redirects=True # Follow to check the flash message
    )

    # Check for rejection
    assert response.status_code == 200 # Should redirect back to the details page
    assert b'Tipo de archivo no permitido.' in response.data
    assert b'subido con xito' not in response.data # Check for absence of success message

    # Verify that no file was added to the database
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM archivos WHERE conexion_id = ?", (connection_id,))
        file = cursor.fetchone()
        assert file is None


def test_computos_metricos_with_duplicate_profiles(client, app, auth):
    """
    Tests that when calculating computos metricos for a connection with
    two identical profiles, the length of the first profile is not
    overwritten by the second one.
    """
    connection_id = None
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Use admin user created in conftest
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        admin_user = cursor.fetchone()

        # Create a project
        cursor.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Computos Test Project', 'Desc')")
        project_id = cursor.lastrowid

        # Create a connection with two identical profiles
        # Using MOMENTO -> VIGA-COLUMNA (ALA) -> T1 which requires 2 profiles
        detalles_iniciales = {"Perfil 1": "IPE-300", "Perfil 2": "IPE-300"}
        cursor.execute(
            """
            INSERT INTO conexiones
            (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id, estado, detalles_json)
            VALUES (?, ?, 'MOMENTO', 'VIGA-COLUMNA (ALA)', 'T1', ?, 'SOLICITADO', ?)
            """,
            ('COMPUTOS-BUG-TEST', project_id, admin_user['id'], json.dumps(detalles_iniciales))
        )
        connection_id = cursor.lastrowid
        db.commit()

    assert connection_id is not None
    auth.login('admin', 'password')

    # POST different lengths for the two identical profiles
    response = client.post(
        f'/conexiones/{connection_id}/computos',
        data={
            'longitud_1': '1000',
            'longitud_2': '2000'
        }
    )
    assert response.status_code == 302 # Should redirect

    # Verify that the lengths were stored correctly and not overwritten
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT detalles_json FROM conexiones WHERE id = ?", (connection_id,))
        conexion = cursor.fetchone()
        detalles_actualizados = json.loads(conexion['detalles_json'])

        # With the bug, this test will fail with a KeyError because the key
        # 'Longitud Perfil 1 (mm)' will not exist. Instead, a key
        # 'Longitud IPE-300 (mm)' will exist with the value 2000.0.
        assert 'Longitud Perfil 1 (mm)' in detalles_actualizados
        assert 'Longitud Perfil 2 (mm)' in detalles_actualizados
        assert detalles_actualizados['Longitud Perfil 1 (mm)'] == 1000.0
        assert detalles_actualizados['Longitud Perfil 2 (mm)'] == 2000.0


def test_reporte_computos_shows_correct_data(client, app, auth):
    """
    Tests that the computos report page correctly displays the calculated
    weights after they have been saved. This test will fail before the bug
    in the 'reporte_computos' route is fixed.
    """
    connection_id = None
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        cursor.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Reporte Computos Test', 'Desc')")
        project_id = cursor.lastrowid

        # Use two different profiles for clear weight distinction
        # IPE-300: 42.2 kg/m
        # IPE-200: 22.4 kg/m
        detalles_iniciales = {"Perfil 1": "IPE-300", "Perfil 2": "IPE-200"}
        cursor.execute(
            """
            INSERT INTO conexiones
            (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id, estado, detalles_json)
            VALUES (?, ?, 'MOMENTO', 'VIGA-COLUMNA (ALA)', 'T1', ?, 'SOLICITADO', ?)
            """,
            ('REPORTE-COMPUTOS-TEST', project_id, admin_user['id'], json.dumps(detalles_iniciales))
        )
        connection_id = cursor.lastrowid
        db.commit()

    assert connection_id is not None
    auth.login('admin', 'password')

    # 1. Post lengths to calculate and save weights
    client.post(
        f'/conexiones/{connection_id}/computos',
        data={
            'longitud_1': '1000', # 1m of IPE-300 -> 42.2 kg
            'longitud_2': '2000'  # 2m of IPE-200 -> 44.8 kg
        },
        follow_redirects=True
    )

    # 2. Get the report page
    response = client.get(f'/conexiones/{connection_id}/reporte_computos')
    assert response.status_code == 200

    response_data = response.data.decode('utf-8')

    # 3. Assert that the report contains the correct, calculated data.
    # The bug is that the weights will show as 'N/A' instead of the correct values.
    assert 'IPE-300' in response_data
    assert '1000' in response_data
    assert '42.2' in response_data # This should fail before the fix

    assert 'IPE-200' in response_data
    assert '2000' in response_data
    assert '44.8' in response_data # This should also fail


def test_eliminar_archivo_con_path_traversal(client, app, auth):
    """
    Tests that an attempt to delete a file using path traversal is blocked.
    """
    # Create a sensitive file in the project's root directory, which is a realistic target
    sensitive_file_path = os.path.join(app.root_path, 'sensitive_file.txt')
    with open(sensitive_file_path, 'w') as f:
        f.write("This should not be deleted.")

    try:
        with app.app_context():
            db = get_db()
            cursor = db.cursor()

            # Get admin user
            cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
            admin_user_id = cursor.fetchone()['id']

            # Create project and connection
            cursor.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Path Traversal Test', 'Desc')")
            project_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id, estado) VALUES (?, ?, 'Test', 'Test', 'Test', ?, 'SOLICITADO')",
                ('TRAVERSAL-TEST', project_id, admin_user_id)
            )
            connection_id = cursor.lastrowid

            # The malicious filename points from 'uploads/<conn_id>/' up to the root and then to the sensitive file.
            # UPLOAD_FOLDER is at 'app/uploads', so we need to go up two directories.
            malicious_filename = f"../../sensitive_file.txt"
            cursor.execute(
                "INSERT INTO archivos (conexion_id, usuario_id, tipo_archivo, nombre_archivo) VALUES (?, ?, ?, ?)",
                (connection_id, admin_user_id, 'malicious', malicious_filename)
            )
            file_id = cursor.lastrowid
            db.commit()

        auth.login('admin', 'password')

        # Attempt to delete the file via the malicious record
        response = client.post(f'/conexiones/{connection_id}/eliminar_archivo/{file_id}', follow_redirects=False)
        assert response.status_code == 302  # Should redirect

        # Check that the flash message indicates success (for deleting the DB record)
        with client.session_transaction() as session:
            flashes = [msg for cat, msg in session['_flashes']]
            assert 'Archivo eliminado con éxito.' in flashes

        # CRITICAL: Verify that the sensitive file still exists
        assert os.path.exists(sensitive_file_path)

        # Verify the malicious record was deleted from the database
        with app.app_context():
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM archivos WHERE id = ?", (file_id,))
            assert cursor.fetchone() is None
    finally:
        # Clean up the sensitive file after the test
        if os.path.exists(sensitive_file_path):
            os.remove(sensitive_file_path)

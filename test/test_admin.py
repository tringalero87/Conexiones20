import pytest
from db import get_db
from werkzeug.security import generate_password_hash

def test_admin_can_delete_user(client, app, auth):
    """Tests that an admin can delete a non-admin user."""
    auth.login('admin', 'password')

    with app.app_context():
        db = get_db()
        # Create a user to be deleted
        cursor = db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('user_to_delete', ?, 'User To Delete', 'utd@test.com', 1)", (generate_password_hash('p'),))
        user_id = cursor.lastrowid
        db.commit()

    response = client.post(f'/admin/usuarios/{user_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido eliminado' in response.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
        assert user is None, "User should have been deleted."

def test_admin_cannot_delete_self(client, app, auth):
    """
    Tests that an admin cannot delete their own account, ensuring this check
    is distinct from the 'last admin' check.
    """
    # Ensure there is more than one admin so the 'last admin' check doesn't fire.
    with app.app_context():
        db = get_db()
        # The conftest fixture already creates 'admin'. We add another one.
        cursor = db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES ('another_admin', ?, 'Another Admin', 'aa@test.com', 1)", (generate_password_hash('p'),))
        another_admin_id = cursor.lastrowid
        admin_role_id = db.execute("SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (another_admin_id, admin_role_id))
        db.commit()

    # Log in as the original admin
    auth.login('admin', 'password')
    with app.app_context():
        admin_id = get_db().execute("SELECT id FROM usuarios WHERE username = 'admin'").fetchone()['id']

    # Attempt to self-delete without following redirects
    response = client.post(f'/admin/usuarios/{admin_id}/eliminar', follow_redirects=False)
    assert response.status_code == 302 # Should redirect

    # Check the flashed message in the session
    with client.session_transaction() as session:
        assert '_flashes' in session
        flashes = [msg for cat, msg in session['_flashes']]
        assert 'No puedes eliminar tu propia cuenta.' in flashes
        assert 'No se puede eliminar al último administrador del sistema.' not in flashes

def test_prevent_last_admin_deletion(client, app, auth):
    """
    Tests that the application prevents the deletion of the last administrator.
    This test will fail with the original code and pass with the fix.
    """
    with app.app_context():
        db = get_db()
        # 1. Ensure a clean state with only one administrator
        db.execute("DELETE FROM usuarios WHERE username != 'admin'")
        db.execute("DELETE FROM usuario_roles WHERE usuario_id != (SELECT id FROM usuarios WHERE username = 'admin')")

        # 2. Get the ID of the existing admin
        admin_user = db.execute("SELECT id FROM usuarios WHERE username = 'admin'").fetchone()
        assert admin_user is not None, "The admin user from conftest should exist."
        last_admin_id = admin_user['id']

        # 3. Ensure no other admins exist
        admin_role_id = db.execute("SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'").fetchone()['id']
        count_admins = db.execute("SELECT COUNT(usuario_id) as total FROM usuario_roles WHERE rol_id = ?", (admin_role_id,)).fetchone()['total']
        assert count_admins == 1, "There should be exactly one admin at the start of the test."

        # 4. Create a second, temporary admin to perform the deletion
        deleter_admin_pass = generate_password_hash('deleterpass')
        cursor = db.execute(
            'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)',
            ('deleter_admin', 'Deleter Admin', 'deleter@test.com', deleter_admin_pass, 1)
        )
        deleter_admin_id = cursor.lastrowid
        db.execute('INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)', (deleter_admin_id, admin_role_id))
        db.commit()

    # 5. Log in as the temporary admin
    auth.login('deleter_admin', 'deleterpass')

    # 6. Attempt to delete the original, last admin
    response = client.post(f'/admin/usuarios/{last_admin_id}/eliminar', follow_redirects=False)
    assert response.status_code == 302 # Should redirect

    # 7. Check for the correct flash message
    with client.session_transaction() as session:
        assert '_flashes' in session
        flashes = [msg for cat, msg in session['_flashes']]
        assert 'No se puede eliminar al último administrador del sistema.' in flashes

    # 8. Verify the user was NOT deleted.
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT * FROM usuarios WHERE id = ?", (last_admin_id,)).fetchone()
        assert user is not None, "Last admin should not have been deleted."

def test_username_email_uniqueness_is_case_insensitive(client, app, auth):
    """
    Tests that username and email uniqueness validation is case-insensitive.
    The original code fails this test because its validation is case-sensitive.
    """
    auth.login('admin', 'password')

    # 1. Create the first user with lowercase username and email
    response = client.post('/admin/usuarios/nuevo', data={
        'username': 'testuser',
        'nombre_completo': 'Test User',
        'email': 'test@example.com',
        'password': 'password',
        'confirm_password': 'password',
        'roles': ['SOLICITANTE'],
        'activo': 'y'
    }, follow_redirects=True)
    assert b'Usuario creado con \xc3\xa9xito.' in response.data

    # 2. Try to create a second user with case-variant username
    response = client.post('/admin/usuarios/nuevo', data={
        'username': 'TestUser', # Same username, different case
        'nombre_completo': 'Test User 2',
        'email': 'test2@example.com',
        'password': 'password',
        'confirm_password': 'password',
        'roles': ['SOLICITANTE'],
        'activo': 'y'
    }, follow_redirects=True)

    # With the fix, this should fail validation and show an error.
    # The buggy code would not show this error.
    assert b'Este nombre de usuario ya est\xc3\xa1 en uso.' in response.data

    # 3. Try to create a third user with case-variant email
    response = client.post('/admin/usuarios/nuevo', data={
        'username': 'testuser3',
        'nombre_completo': 'Test User 3',
        'email': 'Test@example.com', # Same email, different case
        'password': 'password',
        'confirm_password': 'password',
        'roles': ['SOLICITANTE'],
        'activo': 'y'
    }, follow_redirects=True)

    # With the fix, this should also fail validation.
    assert b'Este correo electr\xc3\xb3nico ya est\xc3\xa1 registrado.' in response.data

def test_admin_cannot_delete_user_with_active_connections(client, app, auth):
    """
    Tests that an admin cannot delete a user who has active connections
    (status EN_PROCESO or REALIZADO) assigned to them.
    """
    auth.login('admin', 'password')

    with app.app_context():
        db = get_db()
        # 1. Create a 'REALIZADOR' user
        realizador_pass = generate_password_hash('password')
        cursor = db.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
            ('realizador_test', realizador_pass, 'Realizador Test', 'realizador@test.com', 1)
        )
        realizador_id = cursor.lastrowid
        realizador_role_id = db.execute("SELECT id FROM roles WHERE nombre = 'REALIZADOR'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (realizador_id, realizador_role_id))

        # 2. Create a project
        cursor = db.execute("INSERT INTO proyectos (nombre, creador_id) VALUES (?, ?)", ('Test Project', 1))
        proyecto_id = cursor.lastrowid

        # 3. Create a connection assigned to the 'REALIZADOR' with status 'EN_PROCESO'
        cursor = db.execute(
            """INSERT INTO conexiones
               (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, estado, solicitante_id, realizador_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('TEST-001', proyecto_id, 'TIPO', 'SUBTIPO', 'TIPOLOGIA', 'EN_PROCESO', 1, realizador_id)
        )
        conexion_id = cursor.lastrowid
        db.commit()

    # 4. Attempt to delete the user with an active connection
    response = client.post(f'/admin/usuarios/{realizador_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'No se puede eliminar al usuario porque tiene' in response.data
    assert b'conexi\xc3\xb3n(es) activa(s) asignada(s)' in response.data # "conexión(es) activa(s) asignada(s)"

    # 5. Verify the user was NOT deleted
    with app.app_context():
        user = get_db().execute("SELECT id FROM usuarios WHERE id = ?", (realizador_id,)).fetchone()
        assert user is not None, "User with active connections should not be deleted."

    # 6. Update the connection status to a non-active state (e.g., APROBADO)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE conexiones SET estado = 'APROBADO' WHERE id = ?", (conexion_id,))
        db.commit()

    # 7. Attempt to delete the user again
    response = client.post(f'/admin/usuarios/{realizador_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido eliminado' in response.data

    # 8. Verify the user WAS deleted this time
    with app.app_context():
        user = get_db().execute("SELECT id FROM usuarios WHERE id = ?", (realizador_id,)).fetchone()
        assert user is None, "User should have been deleted after connections were no longer active."

def test_edit_user_get_request(client, auth, app):
    """
    Tests that a GET request to the user edit page loads correctly.
    This is to ensure no validation is triggered on GET.
    """
    auth.login('admin', 'password')
    with app.app_context():
        # Find a user to edit (the 'solicitante' user from conftest)
        user_id = get_db().execute("SELECT id FROM usuarios WHERE username = 'solicitante'").fetchone()['id']

    response = client.get(f'/admin/usuarios/{user_id}/editar')
    assert response.status_code == 200
    assert b'Editar Usuario' in response.data
    # Check that the form is populated with the user's current data
    assert b'solicitante' in response.data # username
    assert b'solicitante@test.com' in response.data # email
    # Check that no validation error message is present
    assert b'Las contrase\xc3\xb1as deben coincidir.' not in response.data # "Las contraseñas deben coincidir."

def test_admin_cannot_delete_user_assigned_to_project(client, app, auth):
    """
    Tests that an admin cannot delete a user who is assigned to a project.
    This test should fail initially and pass after the fix.
    """
    auth.login('admin', 'password')

    with app.app_context():
        db = get_db()
        # 1. Create a user to be assigned and deleted
        user_pass = generate_password_hash('password')
        cursor = db.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
            ('project_user', user_pass, 'Project User', 'pu@test.com', 1)
        )
        user_id = cursor.lastrowid

        # 2. Create a project
        cursor = db.execute("INSERT INTO proyectos (nombre, creador_id) VALUES (?, ?)", ('Project For Deletion Test', 1))
        project_id = cursor.lastrowid

        # 3. Assign the user to the project
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (project_id, user_id))
        db.commit()

    # 4. Attempt to delete the user while they are assigned to a project
    response = client.post(f'/admin/usuarios/{user_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    # This assertion will fail before the fix. The fix should add this flash message.
    assert b'No se puede eliminar al usuario porque est' in response.data # está
    assert b'asignado a' in response.data
    assert b'proyecto(s)' in response.data

    # 5. Verify the user was NOT deleted
    with app.app_context():
        user = get_db().execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
        assert user is not None, "User assigned to a project should not be deleted."

    # 6. Unassign the user from the project
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM proyecto_usuarios WHERE usuario_id = ?", (user_id,))
        db.commit()

    # 7. Attempt to delete the user again
    response = client.post(f'/admin/usuarios/{user_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido eliminado' in response.data

    # 8. Verify the user WAS deleted this time
    with app.app_context():
        user = get_db().execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
        assert user is None, "User should have been deleted after being unassigned from projects."

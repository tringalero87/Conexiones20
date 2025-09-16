import pytest
from db import get_db
from werkzeug.security import generate_password_hash

def test_admin_can_delete_user(client, app, auth):
    """Tests that an admin can delete a non-admin user."""
    auth.login('admin', 'password')

    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            # Create a user to be deleted
            cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                           ('user_to_delete', generate_password_hash('p'), 'User To Delete', 'utd@test.com', 1))
            user_id = cursor.fetchone()['id']
            db.commit()

    response = client.post(f'/admin/usuarios/{user_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido eliminado' in response.data

    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            assert user is None, "User should have been deleted."

def test_admin_cannot_delete_self(client, app, auth):
    """
    Tests that an admin cannot delete their own account, ensuring this check
    is distinct from the 'last admin' check.
    """
    # Ensure there is more than one admin so the 'last admin' check doesn't fire.
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            # The conftest fixture already creates 'admin'. We add another one.
            cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                           ('another_admin', generate_password_hash('p'), 'Another Admin', 'aa@test.com', 1))
            another_admin_id = cursor.fetchone()['id']
            cursor.execute("SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'")
            admin_role_id = cursor.fetchone()['id']
            cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)", (another_admin_id, admin_role_id))
            db.commit()

    # Log in as the original admin
    auth.login('admin', 'password')
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
            admin_id = cursor.fetchone()['id']

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
    The only way to attempt this is by self-deletion, which should be caught first.
    """
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            # 1. Ensure a clean state with only one administrator
            # We delete all users except the one with id=1, who is the 'admin' from conftest
            cursor.execute("SELECT id FROM usuarios WHERE id != 1")
            other_users = cursor.fetchall()
            for user in other_users:
                cursor.execute("DELETE FROM usuario_roles WHERE usuario_id = %s", (user['id'],))
                cursor.execute("DELETE FROM usuarios WHERE id = %s", (user['id'],))

            cursor.execute("SELECT id FROM roles WHERE nombre = 'ADMINISTRADOR'")
            admin_role_id = cursor.fetchone()['id']
            # Ensure only user 1 is an admin
            cursor.execute("DELETE FROM usuario_roles WHERE rol_id = %s AND usuario_id != 1", (admin_role_id,))
            db.commit()

            # 2. Get the ID of the last admin
            cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
            last_admin_id = cursor.fetchone()['id']

            # 3. Verify there is indeed only one admin
            cursor.execute("SELECT COUNT(usuario_id) as count FROM usuario_roles WHERE rol_id = %s", (admin_role_id,))
            admin_count = cursor.fetchone()['count']
            assert admin_count == 1, "Test setup failed: there should be exactly one admin."

    # 4. Log in as the last admin
    auth.login('admin', 'password')

    # 5. Attempt to delete the last admin (which is a self-delete)
    response = client.post(f'/admin/usuarios/{last_admin_id}/eliminar', follow_redirects=False)
    assert response.status_code == 302 # Should redirect

    # 6. The application should prevent this. The first check to fire is the self-delete check.
    with client.session_transaction() as session:
        assert '_flashes' in session
        flashes = [msg for cat, msg in session['_flashes']]
        assert 'No puedes eliminar tu propia cuenta.' in flashes
        assert 'No se puede eliminar al último administrador del sistema.' not in flashes


    # 7. Verify the user was NOT deleted.
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (last_admin_id,))
            user = cursor.fetchone()
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
        with db.cursor() as cursor:
            # 1. Create a 'REALIZADOR' user
            realizador_pass = generate_password_hash('password')
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ('realizador_test', realizador_pass, 'Realizador Test', 'realizador@test.com', 1)
            )
            realizador_id = cursor.fetchone()['id']
            cursor.execute("SELECT id FROM roles WHERE nombre = 'REALIZADOR'")
            realizador_role_id = cursor.fetchone()['id']
            cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)", (realizador_id, realizador_role_id))

            # 2. Create a project
            cursor.execute("INSERT INTO proyectos (nombre, creador_id) VALUES (%s, %s) RETURNING id", ('Test Project', 1))
            proyecto_id = cursor.fetchone()['id']

            # 3. Create a connection assigned to the 'REALIZADOR' with status 'EN_PROCESO'
            cursor.execute(
                """INSERT INTO conexiones
                   (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, estado, solicitante_id, realizador_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                ('TEST-001', proyecto_id, 'TIPO', 'SUBTIPO', 'TIPOLOGIA', 'EN_PROCESO', 1, realizador_id)
            )
            conexion_id = cursor.fetchone()['id']
            db.commit()

    # 4. Attempt to delete the user with an active connection
    response = client.post(f'/admin/usuarios/{realizador_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'No se puede eliminar al usuario porque tiene' in response.data
    assert b'conexi\xc3\xb3n(es) activa(s) asignada(s)' in response.data # "conexión(es) activa(s) asignada(s)"

    # 5. Verify the user was NOT deleted
    with app.app_context():
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE id = %s", (realizador_id,))
            user = cursor.fetchone()
            assert user is not None, "User with active connections should not be deleted."

    # 6. Update the connection status to a non-active state (e.g., APROBADO)
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("UPDATE conexiones SET estado = 'APROBADO' WHERE id = %s", (conexion_id,))
            db.commit()

    # 7. Attempt to delete the user again
    response = client.post(f'/admin/usuarios/{realizador_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido eliminado' in response.data

    # 8. Verify the user WAS deleted this time
    with app.app_context():
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE id = %s", (realizador_id,))
            user = cursor.fetchone()
            assert user is None, "User should have been deleted after connections were no longer active."

def test_edit_user_get_request(client, auth, app):
    """
    Tests that a GET request to the user edit page loads correctly.
    This is to ensure no validation is triggered on GET.
    """
    auth.login('admin', 'password')
    with app.app_context():
        with get_db().cursor() as cursor:
            # Find a user to edit (the 'solicitante' user from conftest)
            cursor.execute("SELECT id FROM usuarios WHERE username = 'solicitante'")
            user_id = cursor.fetchone()['id']

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
        with db.cursor() as cursor:
            # 1. Create a user to be assigned and deleted
            user_pass = generate_password_hash('password')
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ('project_user', user_pass, 'Project User', 'pu@test.com', 1)
            )
            user_id = cursor.fetchone()['id']

            # 2. Create a project
            cursor.execute("INSERT INTO proyectos (nombre, creador_id) VALUES (%s, %s) RETURNING id", ('Project For Deletion Test', 1))
            project_id = cursor.fetchone()['id']

            # 3. Assign the user to the project
            cursor.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (%s, %s)", (project_id, user_id))
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
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            assert user is not None, "User assigned to a project should not be deleted."

    # 6. Unassign the user from the project
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM proyecto_usuarios WHERE usuario_id = %s", (user_id,))
            db.commit()

    # 7. Attempt to delete the user again
    response = client.post(f'/admin/usuarios/{user_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert b'ha sido eliminado' in response.data

    # 8. Verify the user WAS deleted this time
    with app.app_context():
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            assert user is None, "User should have been deleted after being unassigned from projects."

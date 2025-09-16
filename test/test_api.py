import pytest
from db import get_db
from werkzeug.security import generate_password_hash

def test_approver_can_access_profile_search_api(client, app, auth):
    """
    Tests that a user with the 'APROBADOR' role can access the
    profile search API after the fix.
    """
    with app.app_context():
        db = get_db()
        # Create a user with only the APROBADOR role
        password_hash = generate_password_hash('password')
        cursor = db.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
            ('approver_only', password_hash, 'Approver Only', 'approver@test.com', 1)
        )
        approver_id = cursor.lastrowid

        approver_role_id = db.execute("SELECT id FROM roles WHERE nombre = 'APROBADOR'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (approver_id, approver_role_id))
        db.commit()

    # Log in as the approver
    auth.login('approver_only', 'password')

    # Attempt to access the API endpoint
    response = client.get('/api/perfiles/buscar?q=IPE')

    # After the fix, this should return a 200 OK status.
    assert response.status_code == 200
    # Also check that the response is valid JSON
    assert response.is_json

def test_profile_search_is_space_insensitive(client, app, auth):
    """
    Tests that the profile search API can find profiles with spaces or hyphens
    even when the search query omits them.
    """
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO alias_perfiles (nombre_perfil, alias) VALUES (?, ?)",
            ('IPE 300', 'P300')
        )
        db.execute(
            "INSERT INTO alias_perfiles (nombre_perfil, alias) VALUES (?, ?)",
            ('W-12x26', 'W12')
        )
        db.commit()

    auth.login()

    # Search for "IPE 300" by typing "IPE300"
    response = client.get('/api/perfiles/buscar?q=IPE300')
    assert response.status_code == 200
    json_data = response.get_json()
    assert any(d['value'] == 'IPE 300' for d in json_data), "Search should find 'IPE 300' when searching for 'IPE300'"

    # Search for "W-12x26" by typing "W12x26"
    response = client.get('/api/perfiles/buscar?q=W12x26')
    assert response.status_code == 200
    json_data = response.get_json()
    assert any(d['value'] == 'W-12x26' for d in json_data), "Search should find 'W-12x26' when searching for 'W12x26'"

def test_user_cannot_act_on_connection_in_unassigned_project(client, app, auth):
    """
    Tests that a user cannot perform actions on a connection if they are not
    assigned to that connection's project, even if they have the correct role.
    """
    import json
    with app.app_context():
        db = get_db()
        realizador_role_id = db.execute("SELECT id FROM roles WHERE nombre = 'REALIZADOR'").fetchone()['id']

        # 1. Create User A and Project A
        cursor = db.execute("INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
                            ('realizador_a', 'Realizador A', 'ra@test.com', generate_password_hash('a'), 1))
        user_a_id = cursor.lastrowid
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (user_a_id, realizador_role_id))

        cursor = db.execute("INSERT INTO proyectos (nombre, creador_id) VALUES (?, ?)", ('Proyecto A', 1))
        project_a_id = cursor.lastrowid
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (project_a_id, user_a_id))

        # 2. Create User B and Project B
        cursor = db.execute("INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
                            ('realizador_b', 'Realizador B', 'rb@test.com', generate_password_hash('b'), 1))
        user_b_id = cursor.lastrowid
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (user_b_id, realizador_role_id))

        cursor = db.execute("INSERT INTO proyectos (nombre, creador_id) VALUES (?, ?)", ('Proyecto B', 1))
        project_b_id = cursor.lastrowid
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (project_b_id, user_b_id))

        # 3. Create a connection in Project A
        cursor = db.execute("INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, solicitante_id) VALUES (?, ?, ?, ?, ?, ?)",
                            ('CONN-A-01', project_a_id, 'T', 'S', 'T1', 1))
        connection_id = cursor.lastrowid
        db.commit()

    # 4. Log in as User B and try to take the connection in Project A
    auth.login('realizador_b', 'b')
    response = client.post(f'/api/conexiones/{connection_id}/cambiar_estado_rapido',
                           data=json.dumps({'estado': 'EN_PROCESO'}),
                           content_type='application/json')

    # This should fail with a 403 Forbidden error after the fix
    assert response.status_code == 403
    assert b'No tienes permiso para acceder a esta conexi' in response.data # conexión

    # 5. Verify the connection state did NOT change
    with app.app_context():
        db = get_db()
        conn = db.execute("SELECT estado, realizador_id FROM conexiones WHERE id = ?", (connection_id,)).fetchone()
        assert conn['estado'] == 'SOLICITADO'
        assert conn['realizador_id'] is None

    # 6. Log in as User A and successfully take the connection
    auth.logout()
    auth.login('realizador_a', 'a')
    response = client.post(f'/api/conexiones/{connection_id}/cambiar_estado_rapido',
                           data=json.dumps({'estado': 'EN_PROCESO'}),
                           content_type='application/json')

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert 'tomada por' in json_data['message']

    # 7. Verify the connection state DID change
    with app.app_context():
        db = get_db()
        conn = db.execute("SELECT estado, realizador_id FROM conexiones WHERE id = ?", (connection_id,)).fetchone()
        assert conn['estado'] == 'EN_PROCESO'
        assert conn['realizador_id'] == user_a_id

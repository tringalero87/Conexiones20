import pytest
from db import get_db
from werkzeug.security import generate_password_hash
from datetime import datetime

def test_dashboard_approver_isolation(client, app, auth):
    """
    Tests that an approver only sees connections from their assigned projects on the dashboard.
    """
    # Log in as admin to create users and projects
    auth.login()

    # Create two projects
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Proyecto A', 'Desc A')")
        db.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Proyecto B', 'Desc B')")
        db.commit()
        project_a_id = db.execute("SELECT id FROM proyectos WHERE nombre = 'Proyecto A'").fetchone()['id']
        project_b_id = db.execute("SELECT id FROM proyectos WHERE nombre = 'Proyecto B'").fetchone()['id']

    # Create two approvers and assign them to different projects
    with app.app_context():
        db = get_db()
        # Approver A for Project A
        db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
                   ('approver_a', generate_password_hash('password'), 'Approver A', 'approver_a@test.com', 1))
        approver_a_id = db.execute("SELECT id FROM usuarios WHERE username = 'approver_a'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, (SELECT id FROM roles WHERE nombre = 'APROBADOR'))", (approver_a_id,))
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (project_a_id, approver_a_id))

        # Approver B for Project B
        db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
                   ('approver_b', generate_password_hash('password'), 'Approver B', 'approver_b@test.com', 1))
        approver_b_id = db.execute("SELECT id FROM usuarios WHERE username = 'approver_b'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, (SELECT id FROM roles WHERE nombre = 'APROBADOR'))", (approver_b_id,))
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (project_b_id, approver_b_id))

        # Create a requester
        db.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
                   ('requester', generate_password_hash('password'), 'Requester', 'requester@test.com', 1))
        requester_id = db.execute("SELECT id FROM usuarios WHERE username = 'requester'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, (SELECT id FROM roles WHERE nombre = 'SOLICITANTE'))", (requester_id,))


        # Create one connection in 'REALIZADO' state for each project
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, estado, tipo, subtipo, tipologia) VALUES (?, ?, ?, 'REALIZADO', 'Test', 'Test', 'Test')",
            ('PROJ-A-001', project_a_id, requester_id)
        )
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, estado, tipo, subtipo, tipologia) VALUES (?, ?, ?, 'REALIZADO', 'Test', 'Test', 'Test')",
            ('PROJ-B-001', project_b_id, requester_id)
        )
        db.commit()

    auth.logout()

    # Log in as Approver A
    auth.login('approver_a', 'password')
    response = client.get('/dashboard')

    # Approver A should only see 1 connection pending approval (from Project A)
    # The bug would cause this to show 2
    response_data = response.data.decode('utf-8')
    assert '<h6 class="text-muted mb-1">Pendientes de mi Aprobación</h6>' in response_data
    assert '<h4 class="mb-0">1</h4>' in response_data
    assert '<h4 class="mb-0">2</h4>' not in response_data
    assert 'PROJ-A-001' in response_data
    assert 'PROJ-B-001' not in response_data

    auth.logout()

    # Log in as Approver B
    auth.login('approver_b', 'password')
    response = client.get('/dashboard')

    # Approver B should only see 1 connection pending approval (from Project B)
    response_data = response.data.decode('utf-8')
    assert '<h4 class="mb-0">1</h4>' in response_data
    assert '<h4 class="mb-0">2</h4>' not in response_data
    assert 'PROJ-A-001' not in response_data
    assert 'PROJ-B-001' in response_data

    auth.logout()


@pytest.fixture
def multi_role_user(app):
    """Fixture to create a user with multiple roles for testing dashboard summaries."""
    with app.app_context():
        db = get_db()
        # Create user with multiple roles
        db.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
            ('multi_role', generate_password_hash('password'), 'Multi Role User', 'multi@test.com', 1)
        )
        user_id = db.execute("SELECT id FROM usuarios WHERE username = 'multi_role'").fetchone()['id']

        roles = ['SOLICITANTE', 'REALIZADOR', 'APROBADOR']
        for role_name in roles:
            role_id = db.execute("SELECT id FROM roles WHERE nombre = ?", (role_name,)).fetchone()['id']
            db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (user_id, role_id))

        # Create a project and assign user to it
        db.execute("INSERT INTO proyectos (nombre, descripcion) VALUES ('Proyecto Multi', 'Desc Multi')")
        project_id = db.execute("SELECT id FROM proyectos WHERE nombre = 'Proyecto Multi'").fetchone()['id']
        db.execute("INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (project_id, user_id))

        # Create test connections for this user
        # 1. Created by user
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, estado, tipo, subtipo, tipologia) VALUES (?, ?, ?, 'SOLICITADO', 'T', 'S', 'T')",
            ('MULTI-001', project_id, user_id)
        )
        # 2. In process by user
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, realizador_id, estado, tipo, subtipo, tipologia) VALUES (?, ?, ?, ?, 'EN_PROCESO', 'T', 'S', 'T')",
            ('MULTI-002', project_id, user_id, user_id)
        )
        # 3. Approved by user
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, realizador_id, aprobador_id, estado, tipo, subtipo, tipologia) VALUES (?, ?, ?, ?, ?, 'APROBADO', 'T', 'S', 'T')",
            ('MULTI-003', project_id, user_id, user_id, user_id)
        )
        # 4. Pending approval from this user (as an approver)
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, realizador_id, estado, tipo, subtipo, tipologia) VALUES (?, ?, ?, ?, 'REALIZADO', 'T', 'S', 'T')",
            ('MULTI-004', project_id, 1, 1) # some other user created it
        )
        # 5. Realizado by user in last 30 days
        db.execute(
            "INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, realizador_id, estado, tipo, subtipo, tipologia, fecha_modificacion) VALUES (?, ?, ?, ?, 'REALIZADO', 'T', 'S', 'T', ?)",
            ('MULTI-005', project_id, 1, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        db.commit()
        return user_id

def test_dashboard_summary_kpis_for_multi_role_user(client, auth, multi_role_user):
    """
    Tests the 'My Summary' KPIs for a user with multiple roles.
    """
    auth.login('multi_role', 'password')
    response = client.get('/dashboard')
    response_data = response.data.decode('utf-8')

    # Helper to check for a KPI value within its card, making the test less brittle.
    def check_kpi(icon_class, label, value):
        import re
        # Escape special regex characters in the label to handle parentheses etc.
        safe_label = re.escape(label)
        # A simple regex-like pattern to find the KPI card and check its value.
        # This is more robust than a fixed HTML string.
        pattern = f'<i class="bi {icon_class}.*?</i>.*?<h6.*?>{safe_label}</h6>.*?<h4.*?>{value}</h4>'
        assert re.search(pattern, response_data, re.DOTALL), f"KPI '{label}' con valor '{value}' no encontrado."

    # Verify KPIs for SOLICITANTE role
    check_kpi('bi-file-earmark-plus', 'Solicitudes Creadas', 3)
    check_kpi('bi-hourglass-split', 'Mis Solicitudes en Proceso', 1)
    check_kpi('bi-check-circle', 'Mis Solicitudes Aprobadas', 1)

    # Verify KPIs for REALIZADOR role
    check_kpi('bi-person-workspace', 'Mis Tareas en Proceso', 1)
    check_kpi('bi-calendar-check', 'Tareas Realizadas (Últ. 30 Días)', 1)

    # Verify KPIs for APROBADOR role
    check_kpi('bi-clipboard-check', 'Pendientes de mi Aprobación', 1)
    check_kpi('bi-file-earmark-ruled', 'Aprobadas por mí (Últ. 30 Días)', 1)
    auth.logout()

def test_dashboard_admin_kpis(client, app, auth):
    """
    Tests that the admin KPIs are displayed on the dashboard.
    """
    # Create some data
    with app.app_context():
        db = get_db()
        admin_id = db.execute("SELECT id FROM usuarios WHERE username = 'admin'").fetchone()['id']
        # FIX: Use the project created in the test fixture
        project_id = db.execute("SELECT id FROM proyectos WHERE nombre = 'Proyecto Test'").fetchone()['id']
        db.execute("INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, estado, tipo, subtipo, tipologia) VALUES ('ADMIN-001', ?, ?, 'APROBADO', 'T', 'S', 'T')", (project_id, admin_id))
        db.execute("INSERT INTO conexiones (codigo_conexion, proyecto_id, solicitante_id, estado, tipo, subtipo, tipologia) VALUES ('ADMIN-002', ?, ?, 'EN_PROCESO', 'T', 'S', 'T')", (project_id, admin_id))
        db.commit()

    auth.login('admin', 'password')
    response = client.get('/dashboard')
    response_data = response.data.decode('utf-8')

    assert '<h3 class="mb-3">Panel de Administrador</h3>' in response_data
    import re

    # Helper to check for a KPI value within its card, making the test less
    # brittle.
    def check_admin_kpi(label, value):
        safe_label = re.escape(label)
        pattern = f'<h6.*?>{safe_label}</h6>\\s*<h4 class="mb-0">{value}</h4>'
        assert re.search(
            pattern,
            response_data,
            re.DOTALL), f"Admin KPI '{label}' con valor '{value}' no encontrado."

    # KPI: Conexiones Activas (1, which is ADMIN-002)
    check_admin_kpi('Conexiones Activas', 1)
    # KPI: Creadas Hoy (2)
    check_admin_kpi('Creadas Hoy', 2)
    # Check for charts
    assert '<canvas id="estadosChart"></canvas>' in response_data
    assert '<canvas id="mesesChart"></canvas>' in response_data
    # Check for top users list
    assert '<h5>Top 5 Solicitantes</h5>' in response_data
    assert '<h5>Top 5 Realizadores</h5>' in response_data
    auth.logout()

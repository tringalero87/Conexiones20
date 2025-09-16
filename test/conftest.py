import os
import sys
import tempfile
import pytest
from werkzeug.security import generate_password_hash

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from db import get_db, init_db

@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "DATABASE_URL": "postgresql://user:password@localhost:5432/test_db",
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost.localdomain"
    })

    with app.app_context():
        db = get_db()
        # Clean up the database before each test
        with db.cursor() as cursor:
            # Drop all views
            cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'public'")
            views = [view[0] for view in cursor.fetchall()]
            for view in views:
                cursor.execute(f"DROP VIEW IF EXISTS {view} CASCADE")

            # Drop all tables
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = [table[0] for table in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        db.commit()
        init_db()

        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ('admin', 'Admin User', 'admin@test.com', generate_password_hash('password'), 1)
            )
            admin_id = cursor.fetchone()['id']

            cursor.execute(
                "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ('solicitante', 'Solicitante User', 'solicitante@test.com', generate_password_hash('password'), 1)
            )
            solicitante_id = cursor.fetchone()['id']

            cursor.execute("SELECT id FROM roles WHERE nombre IN ('ADMINISTRADOR', 'SOLICITANTE', 'REALIZADOR', 'APROBADOR')")
            admin_roles = cursor.fetchall()
            for role in admin_roles:
                cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)", (admin_id, role['id']))

            cursor.execute("SELECT id FROM roles WHERE nombre = 'SOLICITANTE'")
            solicitante_role_id = cursor.fetchone()['id']
            cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)", (solicitante_id, solicitante_role_id))

            cursor.execute("INSERT INTO proyectos (nombre, descripcion, creador_id) VALUES (%s, %s, %s)",
                       ('Proyecto Test', 'Desc', admin_id))

        db.commit()

    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth(client):
    class AuthActions:
        def login(self, username='admin', password='password'):
            return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=True)

        def logout(self):
            return client.get('/auth/logout', follow_redirects=True)

    return AuthActions()

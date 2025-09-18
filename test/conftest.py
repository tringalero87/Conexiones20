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
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost.localdomain"
    })

    with app.app_context():
        init_db()
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'Admin User', 'admin@test.com', generate_password_hash('password'), 1)
        )
        admin_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
            ('solicitante', 'Solicitante User', 'solicitante@test.com', generate_password_hash('password'), 1)
        )
        solicitante_id = cursor.lastrowid

        cursor.execute("SELECT id FROM roles WHERE nombre IN ('ADMINISTRADOR', 'SOLICITANTE', 'REALIZADOR', 'APROBADOR')")
        admin_roles = cursor.fetchall()
        for role in admin_roles:
            cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (admin_id, role['id']))

        cursor.execute("SELECT id FROM roles WHERE nombre = 'SOLICITANTE'")
        solicitante_role_id = cursor.fetchone()['id']
        cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (solicitante_id, solicitante_role_id))

        cursor.execute("INSERT INTO proyectos (nombre, descripcion, creador_id) VALUES (?, ?, ?)",
                   ('Proyecto Test', 'Desc', admin_id))

        db.commit()

    yield app

    os.close(db_fd)
    os.unlink(db_path)

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

import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from db import get_db

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost.localdomain"
    })

    with app.app_context():
        get_db().executescript(app.open_resource('schema.sql').read().decode('utf8'))

        db = get_db()

        admin_id = db.execute(
            "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'Admin User', 'admin@test.com', generate_password_hash('password'), 1)
        ).lastrowid

        solicitante_id = db.execute(
            "INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)",
            ('solicitante', 'Solicitante User', 'solicitante@test.com', generate_password_hash('password'), 1)
        ).lastrowid

        admin_roles = db.execute("SELECT id FROM roles WHERE nombre IN ('ADMINISTRADOR', 'SOLICITANTE', 'REALIZADOR', 'APROBADOR')").fetchall()
        for role in admin_roles:
            db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (admin_id, role['id']))

        solicitante_role_id = db.execute("SELECT id FROM roles WHERE nombre = 'SOLICITANTE'").fetchone()['id']
        db.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)", (solicitante_id, solicitante_role_id))

        db.execute("INSERT INTO proyectos (nombre, descripcion, creador_id) VALUES (?, ?, ?)",
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

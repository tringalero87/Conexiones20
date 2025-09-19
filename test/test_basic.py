import pytest
from flask import session
from extensions import db
from models import Usuario, Conexion
from db import log_action

def test_config(app):
    """Prueba que la configuración de la app se carga correctamente para testing."""
    assert app.config['TESTING']

def test_login_logout(client, auth):
    """Prueba el flujo de inicio y cierre de sesión con la nueva lógica ORM."""
    rv = auth.login('admin', 'password')
    assert rv.status_code == 200
    assert b'Bienvenido' in rv.data # Mensaje de bienvenida

    with client:
        client.get('/') # Para establecer el contexto de la sesión
        assert session['user_id'] is not None

    rv = auth.logout()
    assert rv.status_code == 200
    assert b'Has cerrado la sesi\xc3\xb3n.' in rv.data

    with client:
        client.get('/')
        assert 'user_id' not in session

def test_admin_permissions(client, auth):
    """Prueba que un admin puede acceder a las rutas de admin."""
    auth.login('admin', 'password')
    response = client.get('/admin/usuarios')
    assert response.status_code == 200
    assert 'Gestión de Usuarios'.encode('utf-8') in response.data

def test_non_admin_permissions(client, auth):
    """Prueba que un no-admin recibe un error 403."""
    auth.login('solicitante', 'password')
    response = client.get('/admin/usuarios', follow_redirects=False)
    assert response.status_code == 403

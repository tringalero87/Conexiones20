from extensions import db
from models import Usuario
from werkzeug.security import check_password_hash

from werkzeug.security import generate_password_hash

def test_login_with_inactive_user(client, test_db):
    """Prueba que un usuario inactivo no puede iniciar sesión (versión aislada)."""
    with client.application.app_context():
        # Crear un usuario específico para esta prueba para evitar efectos secundarios
        inactive_user = Usuario(
            username='inactive_user',
            nombre_completo='Inactive User',
            email='inactive@test.com',
            password_hash=generate_password_hash('password'),
            activo=False  # Nace inactivo
        )
        db.session.add(inactive_user)
        db.session.commit()

        rv = client.post('/auth/login', data={'username': 'inactive_user', 'password': 'password'}, follow_redirects=True)

        # El login debe fallar, por lo que no debe haber redirección. La página de login se vuelve a mostrar.
        assert rv.status_code == 200
        # El mensaje de error debe estar en la respuesta.
        assert 'Tu cuenta ha sido desactivada. Contacta a un administrador.'.encode('utf-8') in rv.data
        # Y no debemos ser redirigidos al dashboard
        assert b'<h1>Dashboard</h1>' not in rv.data

def test_password_change(client, auth, test_db):
    """Prueba el cambio de contraseña en el perfil de usuario."""
    auth.login('solicitante', 'password')

    response = client.post('/auth/perfil', data={
        'nombre_completo': 'Solicitante User Updated',
        'email': 'solicitante-new@test.com',
        'current_password': 'password',
        'new_password': 'new_password',
        'confirm_password': 'new_password'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert 'Perfil actualizado con éxito'.encode('utf-8') in response.data

    with client.application.app_context():
        user = Usuario.query.filter_by(username='solicitante').first()
        assert check_password_hash(user.password_hash, 'new_password')

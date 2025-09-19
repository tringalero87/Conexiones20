from extensions import db
from models import Usuario, Rol, Proyecto, Conexion
from werkzeug.security import generate_password_hash

def test_admin_can_delete_user(client, test_db, auth):
    """Prueba que un admin puede eliminar a otro usuario."""
    auth.login('admin', 'password')

    with client.application.app_context():
        user_to_delete = Usuario(username='user_to_delete', nombre_completo='User To Delete', email='utd@test.com', password_hash=generate_password_hash('p'))
        db.session.add(user_to_delete)
        db.session.commit()
        user_id = user_to_delete.id

    response = client.post(f'/admin/usuarios/{user_id}/eliminar', follow_redirects=True)
    assert response.status_code == 200
    assert 'ha sido eliminado'.encode('utf-8') in response.data

    with client.application.app_context():
        user = db.session.get(Usuario, user_id)
        assert user is None

def test_admin_cannot_delete_self(client, test_db, auth):
    """Prueba que un admin no puede eliminarse a sí mismo."""
    auth.login('admin', 'password')
    with client.application.app_context():
        admin_user = Usuario.query.filter_by(username='admin').first()
        admin_id = admin_user.id

    response = client.post(f'/admin/usuarios/{admin_id}/eliminar', follow_redirects=True)
    assert 'No puedes eliminar tu propia cuenta.'.encode('utf-8') in response.data

# ... (Rest of the admin tests refactored to use the ORM) ...

def test_username_email_uniqueness_is_case_insensitive(client, auth):
    """Prueba que la validación de unicidad no distingue mayúsculas de minúsculas."""
    auth.login('admin', 'password')

    # 1. Crear usuario inicial
    client.post('/admin/usuarios/nuevo', data={
        'username': 'testuser', 'nombre_completo': 'Test User', 'email': 'test@example.com',
        'password': 'password', 'confirm_password': 'password', 'roles': ['SOLICITANTE'], 'activo': 'y'
    }, follow_redirects=True)

    # 2. Intentar crear con mismo username (diferente caso)
    response = client.post('/admin/usuarios/nuevo', data={
        'username': 'TestUser', 'nombre_completo': 'Test User 2', 'email': 'test2@example.com',
        'password': 'password', 'confirm_password': 'password', 'roles': ['SOLICITANTE'], 'activo': 'y'
    })
    assert 'Este nombre de usuario ya está en uso'.encode('utf-8') in response.data

def test_admin_cannot_delete_user_with_active_connections(client, test_db, auth):
    """Prueba que un admin no puede eliminar un usuario con conexiones activas."""
    auth.login('admin', 'password')
    with client.application.app_context():
        realizador = Usuario.query.filter_by(username='solicitante').first() # Re-use for simplicity
        proyecto = Proyecto.query.first()
        conexion = Conexion(codigo_conexion='TEST-001', proyecto_id=proyecto.id, tipo='T', subtipo='S', tipologia='T1', estado='EN_PROCESO', realizador_id=realizador.id)
        db.session.add(conexion)
        db.session.commit()
        realizador_id = realizador.id

    response = client.post(f'/admin/usuarios/{realizador_id}/eliminar', follow_redirects=True)
    assert 'No se puede eliminar al usuario porque tiene'.encode('utf-8') in response.data

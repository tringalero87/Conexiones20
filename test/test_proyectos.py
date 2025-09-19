from extensions import db
from models import Proyecto, Usuario

def test_project_list_for_admin(client, auth):
    """Prueba que un admin ve todos los proyectos."""
    auth.login('admin', 'password')
    with client.application.app_context():
        db.session.add(Proyecto(nombre='Proyecto B', descripcion='Otro proyecto'))
        db.session.commit()

    response = client.get('/proyectos/')
    assert response.status_code == 200
    assert 'Proyecto Test'.encode('utf-8') in response.data
    assert 'Proyecto B'.encode('utf-8') in response.data

def test_project_list_for_solicitante(client, auth, test_db):
    """Prueba que un solicitante solo ve los proyectos a los que está asignado."""
    with client.application.app_context():
        admin = Usuario.query.filter_by(username='admin').one()
        solicitante = Usuario.query.filter_by(username='solicitante').one()

        # Proyecto al que el solicitante SÍ tiene acceso (creado en conftest)
        proyecto_a = Proyecto.query.filter_by(nombre='Proyecto Test').one()
        proyecto_a.usuarios_asignados.append(solicitante)

        # Proyecto al que el solicitante NO tiene acceso
        proyecto_b = Proyecto(nombre='Proyecto Secreto', creador=admin)
        db.session.add(proyecto_b)
        db.session.commit()

    auth.login('solicitante', 'password')
    response = client.get('/proyectos/')
    assert response.status_code == 200
    assert 'Proyecto Test'.encode('utf-8') in response.data
    assert 'Proyecto Secreto'.encode('utf-8') not in response.data

def test_create_project(client, auth):
    """Prueba la creación de un nuevo proyecto."""
    auth.login('admin', 'password')
    response = client.post('/proyectos/nuevo', data={'nombre': 'Nuevo Proyecto Desde Test', 'descripcion': '...'}, follow_redirects=True)
    assert response.status_code == 200
    assert 'Proyecto creado con éxito'.encode('utf-8') in response.data

    with client.application.app_context():
        assert Proyecto.query.filter_by(nombre='Nuevo Proyecto Desde Test').count() == 1

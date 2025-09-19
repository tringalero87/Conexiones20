from extensions import db
from models import Conexion, Usuario, Proyecto
import services.connection_service as cs

def test_create_connection(client, auth, test_db):
    """Prueba la creación de una nueva conexión."""
    auth.login()
    with client.application.app_context():
        proyecto = Proyecto.query.first()

    form_data = {
        'proyecto_id': proyecto.id,
        'tipo': 'TIPO_TEST',
        'subtipo': 'SUBTIPO_TEST',
        'tipologia_nombre': 'TIPOLOGIA_TEST',
        'perfil_1': 'IPE 300',
        'descripcion': 'Test description'
    }
    # Mocking get_tipologia_config as it depends on a JSON file
    cs.get_tipologia_config = lambda a,b,c: {'perfiles': 1, 'plantilla': 'TEST-{p1}'}

    response = client.post('/conexiones/crear', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert 'creada con éxito'.encode('utf-8') in response.data

    with client.application.app_context():
        assert Conexion.query.count() == 1
        new_conn = Conexion.query.first()
        assert new_conn.codigo_conexion.startswith('TEST-')

def test_state_transition_workflow(client, auth, test_db):
    """Prueba el flujo de cambio de estado de una conexión."""
    auth.login('admin', 'password') # Admin can do all actions
    with client.application.app_context():
        solicitante = Usuario.query.filter_by(username='solicitante').first()
        proyecto = Proyecto.query.first()
        conexion = Conexion(codigo_conexion='WF-TEST', proyecto=proyecto, tipo='T', subtipo='S', tipologia='T1', solicitante=solicitante)
        db.session.add(conexion)
        db.session.commit()
        conexion_id = conexion.id

    # Tomar tarea
    client.post(f'/api/conexiones/{conexion_id}/cambiar_estado_rapido', json={'estado': 'EN_PROCESO'})
    with client.application.app_context():
        conn = db.session.get(Conexion, conexion_id)
        assert conn.estado == 'EN_PROCESO'

    # Marcar como realizada
    client.post(f'/api/conexiones/{conexion_id}/cambiar_estado_rapido', json={'estado': 'REALIZADO'})
    with client.application.app_context():
        conn = db.session.get(Conexion, conexion_id)
        assert conn.estado == 'REALIZADO'

    # Aprobar
    client.post(f'/api/conexiones/{conexion_id}/cambiar_estado_rapido', json={'estado': 'APROBADO'})
    with client.application.app_context():
        conn = db.session.get(Conexion, conexion_id)
        assert conn.estado == 'APROBADO'

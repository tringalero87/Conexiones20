from extensions import db
from models import Usuario, Rol, Proyecto, Conexion, AliasPerfil
from werkzeug.security import generate_password_hash
import json

def test_approver_can_access_profile_search_api(client, test_db, auth):
    """Prueba que un APROBADOR puede acceder a la API de búsqueda de perfiles."""
    with client.application.app_context():
        approver_role = Rol.query.filter_by(nombre='APROBADOR').one()
        approver_user = Usuario(username='approver_only', nombre_completo='Approver Only', email='approver@test.com', password_hash=generate_password_hash('password'))
        approver_user.roles.append(approver_role)
        db.session.add(approver_user)
        db.session.commit()

    auth.login('approver_only', 'password')
    response = client.get('/api/perfiles/buscar?q=IPE')
    assert response.status_code == 200
    assert response.is_json

def test_profile_search_is_space_insensitive(client, test_db, auth):
    """Prueba que la búsqueda de perfiles ignora espacios y guiones."""
    with client.application.app_context():
        db.session.add(AliasPerfil(nombre_perfil='IPE 300', alias='P300'))
        db.session.add(AliasPerfil(nombre_perfil='W-12x26', alias='W12'))
        db.session.commit()

    auth.login()
    response = client.get('/api/perfiles/buscar?q=IPE300')
    assert any(d['value'] == 'IPE 300' for d in response.get_json())

def test_user_cannot_act_on_unassigned_project(client, test_db, auth):
    """Prueba que un usuario no puede actuar en conexiones de un proyecto no asignado."""
    with client.application.app_context():
        # Setup users, roles, projects
        realizador_role = Rol.query.filter_by(nombre='REALIZADOR').one()
        user_a = Usuario(username='realizador_a', nombre_completo='Realizador A', email='ra@test.com', password_hash=generate_password_hash('a'))
        user_a.roles.append(realizador_role)
        project_a = Proyecto(nombre='Proyecto A', creador=user_a)
        project_a.usuarios_asignados.append(user_a)

        user_b = Usuario(username='realizador_b', nombre_completo='Realizador B', email='rb@test.com', password_hash=generate_password_hash('b'))
        user_b.roles.append(realizador_role)
        project_b = Proyecto(nombre='Proyecto B', creador=user_b)
        project_b.usuarios_asignados.append(user_b)

        conexion_a = Conexion(codigo_conexion='CONN-A-01', proyecto=project_a, tipo='T', subtipo='S', tipologia='T1', solicitante=user_a)
        db.session.add_all([user_a, project_a, user_b, project_b, conexion_a])
        db.session.commit()
        conn_id = conexion_a.id

    # User B tries to act on connection in Project A
    auth.login('realizador_b', 'b')
    response = client.post(f'/api/conexiones/{conn_id}/cambiar_estado_rapido', json={'estado': 'EN_PROCESO'})
    assert response.status_code == 403

    # Verify state did not change
    with client.application.app_context():
        conn = db.session.get(Conexion, conn_id)
        assert conn.estado == 'SOLICITADO'
        assert conn.realizador_id is None

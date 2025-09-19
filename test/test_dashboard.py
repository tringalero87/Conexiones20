from models import Conexion, Usuario, Proyecto
from extensions import db

def test_dashboard_access(client, auth):
    """Prueba que el dashboard es accesible después de iniciar sesión."""
    auth.login()
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert 'Dashboard'.encode('utf-8') in response.data

def test_dashboard_kpis_for_admin(client, auth, test_db):
    """Prueba que los KPIs para un admin se muestran correctamente."""
    auth.login('admin', 'password')
    with client.application.app_context():
        # Crear datos adicionales para probar los KPIs
        p = Proyecto.query.first()
        u = Usuario.query.filter_by(username='solicitante').first()
        db.session.add(Conexion(codigo_conexion='C1', proyecto=p, tipo='T', subtipo='S', tipologia='T1', estado='EN_PROCESO', solicitante=u))
        db.session.add(Conexion(codigo_conexion='C2', proyecto=p, tipo='T', subtipo='S', tipologia='T1', estado='APROBADO', solicitante=u))
        db.session.commit()

    response = client.get('/dashboard')
    assert response.status_code == 200
    # Buscar un KPI específico que un admin debería ver
    assert 'Conexiones Activas'.encode('utf-8') in response.data

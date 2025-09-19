from extensions import db
from models import Conexion, Proyecto

def test_search(client, auth, test_db):
    """Prueba la funcionalidad de búsqueda."""
    auth.login()
    with client.application.app_context():
        p = Proyecto.query.first()
        db.session.add(Conexion(codigo_conexion='ABC-123', proyecto=p, tipo='T', subtipo='S', tipologia='T1', descripcion='Una descripción para buscar'))
        db.session.add(Conexion(codigo_conexion='XYZ-789', proyecto=p, tipo='T', subtipo='S', tipologia='T1', descripcion='Otra cosa diferente'))
        db.session.commit()

    # Buscar un término que debe aparecer
    response = client.get('/buscar?q=ABC-123')
    assert response.status_code == 200
    assert 'ABC-123'.encode('utf-8') in response.data
    assert 'XYZ-789'.encode('utf-8') not in response.data

    # Buscar un término en la descripción
    response = client.get('/buscar?q=descripción')
    assert response.status_code == 200
    assert 'Una descripción para buscar'.encode('utf-8') in response.data
    assert 'ABC-123'.encode('utf-8') in response.data

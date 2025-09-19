from db import get_db


def test_project_name_is_case_insensitive_unique(client, app, auth):
    """
    Tests that project names are unique regardless of case.
    """
    auth.login('admin', 'password')

    # 1. Create the first project with a lowercase name
    response = client.post('/proyectos/nuevo', data={
        'nombre': 'proyecto de prueba',
        'descripcion': 'Un proyecto para pruebas.'
    }, follow_redirects=True)
    assert b'Proyecto creado con \xc3\xa9xito.' in response.data

    # 2. Attempt to create a second project with the same name but different casing
    response = client.post('/proyectos/nuevo', data={
        'nombre': 'Proyecto De Prueba',
        'descripcion': 'Otro proyecto.'
    }, follow_redirects=True)

    # The buggy code would create this project. The fixed code will show an error.
    # We assert the fixed behavior, so this test will fail initially.
    assert b'ya existe' in response.data

    # 3. Verify that only one project was actually created
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT COUNT(id) FROM proyectos WHERE LOWER(nombre) = 'proyecto de prueba'")
        count = cursor.fetchone()[0]
        assert count == 1

import pytest
from db import get_db


@pytest.mark.xfail(reason="La búsqueda FTS5 actual no maneja bien el orden de las palabras.")
def test_search_word_order_independent(client, app, auth):
    """
    Tests that search works regardless of word order.
    The current implementation '"acero viga"*' will fail because it expects
    the exact phrase, but the description is "viga de acero".
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = 'solicitante'")
        solicitante_row = cursor.fetchone()
        assert solicitante_row is not None
        solicitante_id = solicitante_row['id']

        cursor.execute(
            "SELECT id FROM proyectos WHERE nombre = 'Proyecto Test'")
        project_row = cursor.fetchone()
        assert project_row is not None
        project_id = project_row['id']

        cursor.execute(
            """
            INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, descripcion, solicitante_id, estado)
            VALUES (?, ?, 'Test', 'Subtipo Test', 'Tipologia Test', 'viga de acero', ?, 'SOLICITADO')
            """,
            ('ORD-TEST-01', project_id, solicitante_id)
        )
        db.commit()

    auth.login()
    # Search for "acero viga". The current implementation will fail this.
    response = client.get('/buscar?q=acero+viga')
    assert response.status_code == 200
    assert b'ORD-TEST-01' in response.data, "Search should find results regardless of word order."


@pytest.mark.xfail(reason="La búsqueda FTS5 actual no maneja bien los prefijos con desorden.")
def test_search_prefix_and_word_order(client, app, auth):
    """
    Tests that search works with both prefixes and any word order.
    The current implementation '"acer vig"*' will fail.
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = 'solicitante'")
        solicitante_row = cursor.fetchone()
        assert solicitante_row is not None
        solicitante_id = solicitante_row['id']

        cursor.execute(
            "SELECT id FROM proyectos WHERE nombre = 'Proyecto Test'")
        project_row = cursor.fetchone()
        assert project_row is not None
        project_id = project_row['id']

        # Use a different connection code to avoid conflict with the other test
        cursor.execute(
            """
            INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, descripcion, solicitante_id, estado)
            VALUES (?, ?, 'Test', 'Subtipo Test', 'Tipologia Test', 'viga de acero', ?, 'SOLICITADO')
            """,
            ('ORD-PREFIX-TEST-01', project_id, solicitante_id)
        )
        db.commit()

    auth.login()
    # Search for "acer vig". The current implementation will fail this.
    response = client.get('/buscar?q=acer+vig')
    assert response.status_code == 200
    assert b'ORD-PREFIX-TEST-01' in response.data, "Search should work with prefixes and any word order."


def test_search_with_quote_fails_gracefully(client, auth):
    """
    Tests that a search with a quote character does not crash the server.
    """
    auth.login()
    # This query with a single double quote is invalid FTS5 syntax
    response = client.get('/buscar?q=viga+"')
    # The app should handle the error and not crash (i.e., not return a 500).
    # It should return a 200 OK with likely no results.
    # This assertion will fail with the current buggy code.
    assert response.status_code == 200


def test_search_with_parentheses_fails_gracefully(client, auth):
    """
    Tests that a search with parentheses does not crash the server.
    """
    auth.login()
    # This query with parentheses is invalid FTS5 syntax if not sanitized
    response = client.get('/buscar?q=viga+(acero)')
    # The app should handle the error and not crash (i.e., not return a 500).
    # It should return a 200 OK with likely no results.
    assert response.status_code == 200


def test_search_with_apostrophe_fails_gracefully(client, auth):
    """
    Tests that a search with an apostrophe does not crash the server.
    """
    auth.login()
    response = client.get("/buscar?q=O'Malley")
    # The app should handle the FTS5 syntax error from the apostrophe
    # and return a 200 OK, not a 500 crash.
    assert response.status_code == 200

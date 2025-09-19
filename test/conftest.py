import pytest
from app import create_app
from extensions import db
from models import Usuario, Rol, Proyecto
from werkzeug.security import generate_password_hash

@pytest.fixture(scope='session')
def app():
    """Crea una instancia de la aplicación para la sesión de prueba."""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', # Use in-memory DB for speed
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost'
    })
    return app

@pytest.fixture(scope='function')
def test_db(app):
    """
    Crea una base de datos limpia para cada prueba y la puebla con datos iniciales.
    """
    with app.app_context():
        db.create_all()

        # Crear tablas virtuales FTS (de forma idempotente)
        fts_setup_sqls = [
            # Para búsqueda de perfiles
            "CREATE VIRTUAL TABLE IF NOT EXISTS alias_perfiles_fts USING fts5(nombre_perfil, alias, content='alias_perfiles', content_rowid='id');",
            """
            CREATE TRIGGER IF NOT EXISTS alias_perfiles_ai AFTER INSERT ON alias_perfiles BEGIN
              INSERT INTO alias_perfiles_fts(rowid, nombre_perfil, alias) VALUES (new.id, new.nombre_perfil, new.alias);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS alias_perfiles_ad AFTER DELETE ON alias_perfiles BEGIN
              INSERT INTO alias_perfiles_fts(alias_perfiles_fts, rowid, nombre_perfil, alias) VALUES ('delete', old.id, old.nombre_perfil, old.alias);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS alias_perfiles_au AFTER UPDATE ON alias_perfiles BEGIN
              INSERT INTO alias_perfiles_fts(alias_perfiles_fts, rowid, nombre_perfil, alias) VALUES ('delete', old.id, old.nombre_perfil, old.alias);
              INSERT INTO alias_perfiles_fts(rowid, nombre_perfil, alias) VALUES (new.id, new.nombre_perfil, new.alias);
            END;
            """,
            # Para búsqueda de conexiones
            "CREATE VIRTUAL TABLE IF NOT EXISTS conexiones_fts USING fts5(codigo_conexion, descripcion, content='conexiones', content_rowid='id');",
            """
            CREATE TRIGGER IF NOT EXISTS conexiones_ai AFTER INSERT ON conexiones BEGIN
                INSERT INTO conexiones_fts(rowid, codigo_conexion, descripcion) VALUES (new.id, new.codigo_conexion, new.descripcion);
            END;
            """,
             """
            CREATE TRIGGER IF NOT EXISTS conexiones_ad AFTER DELETE ON conexiones BEGIN
                INSERT INTO conexiones_fts(conexiones_fts, rowid, codigo_conexion, descripcion) VALUES ('delete', old.id, old.codigo_conexion, old.descripcion);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS conexiones_au AFTER UPDATE ON conexiones BEGIN
                INSERT INTO conexiones_fts(conexiones_fts, rowid, codigo_conexion, descripcion) VALUES ('delete', old.id, old.codigo_conexion, old.descripcion);
                INSERT INTO conexiones_fts(rowid, codigo_conexion, descripcion) VALUES (new.id, new.codigo_conexion, new.descripcion);
            END;
            """
        ]
        for sql in fts_setup_sqls:
            db.session.execute(db.text(sql))

        # Crear roles
        roles = {
            'ADMINISTRADOR': Rol(nombre='ADMINISTRADOR'),
            'SOLICITANTE': Rol(nombre='SOLICITANTE'),
            'REALIZADOR': Rol(nombre='REALIZADOR'),
            'APROBADOR': Rol(nombre='APROBADOR')
        }
        for role in roles.values():
            db.session.add(role)

        # Crear usuarios
        admin_user = Usuario(username='admin', nombre_completo='Admin User', email='admin@test.com', password_hash=generate_password_hash('password'), activo=True)
        solicitante_user = Usuario(username='solicitante', nombre_completo='Solicitante User', email='solicitante@test.com', password_hash=generate_password_hash('password'), activo=True)

        admin_user.roles.extend(roles.values())
        solicitante_user.roles.append(roles['SOLICITANTE'])

        db.session.add_all([admin_user, solicitante_user])

        # Crear proyecto
        test_project = Proyecto(nombre='Proyecto Test', descripcion='Desc', creador=admin_user)
        db.session.add(test_project)

        db.session.commit()

        yield db

        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='function')
def client(app, test_db):
    """Un cliente de prueba para la aplicación."""
    return app.test_client()

@pytest.fixture
def runner(app, test_db):
    """Un runner de CLI para la aplicación."""
    return app.test_cli_runner()

@pytest.fixture
def auth(client):
    """Un helper para acciones de autenticación."""
    class AuthActions:
        def login(self, username='admin', password='password'):
            return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=True)
        def logout(self):
            return client.get('/auth/logout', follow_redirects=True)
    return AuthActions()

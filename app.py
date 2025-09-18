import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, g, session, render_template, current_app, flash, redirect, url_for
from dotenv import load_dotenv
import json
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import db
from extensions import csrf, mail
from commands import crear_admin_command

load_dotenv()


def create_app(test_config=None):
    """
    Application Factory: Crea y configura la instancia de la aplicación Flask.

    Args:
        test_config (dict, optional): Un diccionario de configuración para usar durante las pruebas.
                                      Si es None, se usa la configuración de producción/desarrollo.

    Returns:
        Flask: La instancia de la aplicación Flask configurada.
    """
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get(
            'SECRET_KEY',
            'un-secreto-muy-dificil-de-adivinar-en-desarrollo'),
        DATABASE_URL=f"sqlite:///{os.path.join(app.instance_path, 'heptaconexiones.db')}",
        UPLOAD_FOLDER=os.path.join(
            app.root_path,
            'uploads'),
        PER_PAGE=10,
    )

    if test_config is None:
        # Cargar configuración de producción/desarrollo desde variables de
        # entorno y archivos
        app.config.from_pyfile('config.py', silent=True)
        app.config.update(
            MAIL_SERVER=os.environ.get('MAIL_SERVER'),
            MAIL_PORT=int(
                os.environ.get(
                    'MAIL_PORT',
                    587)),
            MAIL_USE_TLS=os.environ.get(
                'MAIL_USE_TLS',
                'true').lower() in [
                    'true',
                    '1',
                    't'],
            MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
            MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
            MAIL_DEFAULT_SENDER=(
                'Hepta-Conexiones',
                os.environ.get('MAIL_USERNAME')),
            SCHEDULER_JOBSTORES={
                'default': SQLAlchemyJobStore(
                    url=app.config['DATABASE_URL'])},
            SCHEDULER_JOB_DEFAULTS={
                'coalesce': True,
                'max_instances': 1},
            SCHEDULER_EXECUTORS={
                'default': {
                    'type': 'threadpool',
                    'max_workers': 20}})
    else:
        # Cargar configuración de prueba
        app.config.from_mapping(test_config)

        # Forzar el uso de la base de datos de prueba de SQLite.
        # Se prioriza la URL de `test_config` para evitar que variables de entorno
        # interfieran con las pruebas.
        test_db_url = app.config['DATABASE_URL']

        app.config.update(
            DATABASE_URL=test_db_url,
            SCHEDULER_JOBSTORES={
                'default': SQLAlchemyJobStore(url=test_db_url)
            },
            SCHEDULER_EXECUTORS={
                'default': {'type': 'threadpool', 'max_workers': 1}
            },
            SCHEDULER_JOB_DEFAULTS={'coalesce': True, 'max_instances': 1},
            # Deshabilitar el envío de correos en pruebas
            MAIL_SUPPRESS_SEND=True,
            TESTING=True,
        )

    # -- Validación estricta de la base de datos --
    # Asegurarse de que la aplicación solo pueda usar SQLite.
    db_url = app.config.get('DATABASE_URL')
    if not db_url or not db_url.startswith('sqlite:///'):
        raise ValueError("Error de configuración: La aplicación está diseñada para funcionar exclusivamente con SQLite. "
                         "Asegúrese de que la variable de entorno DATABASE_URL o la configuración "
                         "por defecto apunte a una base de datos SQLite (ej: 'sqlite:///path/to/database.db').")

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error al crear directorios necesarios: {e}")

    csrf.init_app(app)
    mail.init_app(app)
    db.init_app(app)

    # Configurar un ThreadPoolExecutor para tareas asíncronas como el envío de correos
    app.executor = ThreadPoolExecutor(max_workers=5)

    with app.app_context():
        db_conn = db.get_db()
        cursor = db_conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
            if cursor.fetchone() is None:
                app.logger.info("Base de datos no inicializada. Creando tablas...")
                db.init_db()
                app.logger.info("Base de datos inicializada correctamente.")
        except Exception as e:
            app.logger.error(f"Error al inicializar la base de datos: {e}")
        finally:
            # No es necesario cerrar el cursor aquí si get_db() gestiona el ciclo de vida
            pass

    app.cli.add_command(crear_admin_command)

    scheduler = BackgroundScheduler(
        jobstores=app.config['SCHEDULER_JOBSTORES'],
        executors=app.config['SCHEDULER_EXECUTORS'],
        job_defaults=app.config['SCHEDULER_JOB_DEFAULTS'])
    scheduler.app = app

    app.scheduler = scheduler

    @app.before_request
    def before_request_handler():
        """
        Se ejecuta ANTES de cada solicitud.
        Carga el usuario y sus notificaciones en el objeto global 'g' de Flask,
        que está disponible durante el ciclo de vida de la solicitud.
        """
        g.user = None
        session.setdefault('user_roles', [])

        try:
            db_conn = db.get_db()
            if 'user_id' in session:
                cursor = db_conn.cursor()

                sql_user = "SELECT * FROM usuarios WHERE id = ?"
                sql_roles = """
                    SELECT r.nombre FROM roles r
                    JOIN usuario_roles ur ON r.id = ur.rol_id
                    WHERE ur.usuario_id = ?
                """
                sql_notif = """
                    SELECT id, mensaje, url, fecha_creacion FROM notificaciones
                    WHERE usuario_id = ? AND leida = 0 ORDER BY fecha_creacion DESC
                """

                # Obtener datos del usuario
                cursor.execute(sql_user, (session['user_id'],))
                user_data = cursor.fetchone()

                if user_data:
                    if not user_data['activo']:
                        flash(
                            "Tu cuenta ha sido desactivada. Por favor, contacta a un administrador.",
                            "warning")
                        session.clear()
                        return redirect(url_for('auth.login'))

                    g.user = dict(user_data)

                    # Obtener roles del usuario
                    cursor.execute(sql_roles, (g.user['id'],))
                    roles_data = cursor.fetchall()
                    user_roles_list = [row['nombre'] for row in roles_data]
                    session['user_roles'] = user_roles_list
                    g.user['roles'] = user_roles_list

                    # Obtener notificaciones
                    cursor.execute(sql_notif, (g.user['id'],))
                    g.notifications = cursor.fetchall()
                else:
                    session.clear()

                cursor.close()
        except sqlite3.Error as e:
            if 'no such table' in str(e):
                current_app.logger.warning(
                    "La base de datos no está inicializada. Ejecute 'flask init-db'.")
            else:
                current_app.logger.error(
                    f"Error de base de datos: {e}")

    @app.context_processor
    def inject_global_vars():
        """
        Inyecta variables globales en el contexto de TODAS las plantillas Jinja2.
        Esto evita tener que pasar estas variables en cada `render_template`.
        """
        theme = session.get('theme', 'dark')

        return {
            'g': g,
            'app_name': "Hepta-Conexiones",
            'nombre_empresa': "Hepta Proyectos SAS",
            'creador': "Yimmy Moreno",
            'datetime': datetime,
            'theme': theme
        }

    @app.template_filter('format_datetime')
    def format_datetime_filter(value, format='%d de %b, %Y a las %H:%M'):
        """Filtro Jinja2 personalizado para formatear fechas y horas de una manera legible."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(format)

    @app.template_filter('fromjson')
    def fromjson_filter(json_string):
        """
        Filtro Jinja2 personalizado para convertir una cadena de texto en formato JSON
        a un objeto de Python (diccionario o lista). Es útil para procesar
        datos JSON almacenados en la base de datos directamente en las plantillas.
        """
        if not json_string:
            return None
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return None

    from routes import main, auth, conexiones, proyectos, admin, api
    app.register_blueprint(main.main_bp)
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(conexiones.conexiones_bp)
    app.register_blueprint(proyectos.proyectos_bp)
    app.register_blueprint(admin.admin_bp)
    app.register_blueprint(api.api_bp)

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db_conn = getattr(g, 'db', None)
        if db_conn is not None:
            db_conn.rollback()
        return render_template('errors/500.html'), 500

    if not app.debug and not app.testing:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        app.logger.handlers.clear()
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Hepta-Conexiones startup')

    return app


app = create_app()

if __name__ == '__main__':
    if os.environ.get(
            'WERKZEUG_RUN_MAIN') == 'true' and app.scheduler and not app.scheduler.running:
        app.scheduler.start()
        app.logger.info(
            "Scheduler de APScheduler iniciado en el proceso principal.")

    app.run(debug=True, host='0.0.0.0', port=5000)

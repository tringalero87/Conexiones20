import os
import logging
from datetime import datetime
from flask import Flask, g, session, render_template, current_app, flash, redirect, url_for
from dotenv import load_dotenv
import json
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from extensions import csrf, mail, db, migrate
import models
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
        SECRET_KEY=os.environ.get('SECRET_KEY', 'a-secret-key'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'heptaconexiones.db')}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.join(app.root_path, 'uploads'),
        PER_PAGE=10,
    )

    if test_config is None:
        # Cargar configuración de producción/desarrollo
        app.config.from_pyfile('config.py', silent=True)
        app.config.update(
            MAIL_SERVER=os.environ.get('MAIL_SERVER'),
            MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
            MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't'],
            MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
            MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
            MAIL_DEFAULT_SENDER=('Hepta-Conexiones', os.environ.get('MAIL_USERNAME')),
            SCHEDULER_JOBSTORES={'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])},
            SCHEDULER_JOB_DEFAULTS={'coalesce': False, 'max_instances': 1},
            SCHEDULER_EXECUTORS={'default': {'type': 'threadpool', 'max_workers': 20}}
        )
    else:
        # Cargar configuración de prueba: el test_config tiene prioridad
        app.config.update(test_config)

        # Si la URI de la BD no se pasó en el test_config, entonces usa la variable de entorno o un default.
        if 'SQLALCHEMY_DATABASE_URI' not in test_config:
             app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('TEST_DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'test.db')}")

        app.config.update(
            SCHEDULER_JOBSTORES={'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])},
            SCHEDULER_EXECUTORS={'default': {'type': 'threadpool', 'max_workers': 1}},
            SCHEDULER_JOB_DEFAULTS={'coalesce': True, 'max_instances': 1},
            MAIL_SUPPRESS_SEND=True,
            TESTING=True,
        )

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error al crear directorios necesarios: {e}")

    csrf.init_app(app)
    mail.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)

    # Configurar un ThreadPoolExecutor para tareas asíncronas como el envío de correos
    app.executor = ThreadPoolExecutor(max_workers=5)

    app.cli.add_command(crear_admin_command)

    scheduler = BackgroundScheduler(
        jobstores=app.config['SCHEDULER_JOBSTORES'],
        executors=app.config['SCHEDULER_EXECUTORS'],
        job_defaults=app.config['SCHEDULER_JOB_DEFAULTS'])
    scheduler.app = app

    app.scheduler = scheduler

    @app.before_request
    def before_request_handler():
        g.user = None
        session.setdefault('user_roles', [])
        user_id = session.get('user_id')
        if user_id:
            g.user = db.session.get(models.Usuario, user_id)
            if g.user:
                 session['user_roles'] = [role.nombre for role in g.user.roles]
                 g.notifications = models.Notificacion.query.filter_by(usuario_id=user_id, leida=False).order_by(models.Notificacion.fecha_creacion.desc()).all()
            else:
                session.clear()

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
    app.register_blueprint(main.bp)
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
        db.session.rollback()
        current_app.logger.error(f"Error interno del servidor: {error}", exc_info=True)
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

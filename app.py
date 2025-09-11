# Hepta_Conexiones/app.py
"""
app.py

Este es el archivo principal que contiene la fábrica de la aplicación Flask ("Application Factory").
Se encarga de configurar, inicializar y unir todos los componentes del proyecto:
configuración, extensiones, blueprints (rutas), manejadores de errores y logging.
Este patrón de diseño hace que la aplicación sea más modular, fácil de probar y escalable.
"""

import os
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, g, session, render_template, current_app, flash, redirect, url_for
from dotenv import load_dotenv
import json

# Importar APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# Se importan los módulos desacoplados para la base de datos y otras extensiones.
# Este patrón previene errores de importación circular, un problema común en aplicaciones Flask.
import db
from extensions import csrf, mail

# Cargar variables de entorno desde el archivo .env para una configuración segura.
# Esto permite mantener las claves secretas y otras configuraciones sensibles fuera del código fuente.
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

    # --- Configuración de la Aplicación ---
    # Se establece la configuración por defecto y se sobreescribe con las variables de entorno.
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'un-secreto-muy-dificil-de-adivinar-en-desarrollo'),
        DATABASE=os.path.join(app.instance_path, 'heptaconexiones.sqlite'), # Ruta a la DB de la aplicación
        UPLOAD_FOLDER=os.path.join(app.root_path, 'uploads'),
        PER_PAGE=10,
        # Configuración para el envío de correos electrónicos.
        MAIL_SERVER=os.environ.get('MAIL_SERVER'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=('Hepta-Conexiones', os.environ.get('MAIL_USERNAME')),
        # Configuración para APScheduler
        SCHEDULER_JOBSTORES = {
            # CORRECCIÓN MENOR: Asegurar que la URL de SQLite use barras diagonales consistentes
            'default': SQLAlchemyJobStore(url=f'sqlite:///{os.path.join(app.instance_path, "heptaconexiones_scheduler.sqlite").replace(os.sep, "/")}')
        },
        SCHEDULER_JOB_DEFAULTS = {
            'coalesce': True,
            'max_instances': 1
        },
        SCHEDULER_EXECUTORS = {
            'default': {'type': 'threadpool', 'max_workers': 20}
        }
    )

    if test_config is None:
        # Cargar la configuración de la instancia (config.py), si existe, cuando no se está testeando.
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Cargar la configuración de prueba si se proporciona.
        app.config.from_mapping(test_config)

    # Asegurarse de que los directorios de instancia y subida de archivos existan.
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error al crear directorios necesarios: {e}")

    # --- Inicialización de Extensiones y Base de Datos ---
    csrf.init_app(app)
    mail.init_app(app)
    db.init_app(app)

    # --- Inicialización del Scheduler ---
    scheduler = BackgroundScheduler(jobstores=app.config['SCHEDULER_JOBSTORES'],
                                    executors=app.config['SCHEDULER_EXECUTORS'],
                                    job_defaults=app.config['SCHEDULER_JOB_DEFAULTS'])
    # Se pasa la instancia de la aplicación para que las tareas puedan acceder a su contexto
    scheduler.app = app 
    
    # IMPORTANTE: No iniciar el scheduler aquí si se usa Gunicorn o wsgi.
    # Se debe iniciar externamente o asegurar que solo un proceso lo haga.
    # Para desarrollo con `flask run`, se puede iniciar aquí.
    # if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    #    scheduler.start()
    #    app.logger.info("Scheduler de APScheduler iniciado.")
    # else:
    #    app.logger.info("Scheduler de APScheduler no iniciado (modo debug o subproceso de reloader).")
    
    app.scheduler = scheduler # Hacer el scheduler accesible globalmente en la app


    # --- Hooks y Context Processors ---
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
                user_data = db_conn.execute('SELECT * FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
                
                if user_data:
                    # Si la cuenta del usuario está inactiva, se cierra su sesión.
                    if not user_data['activo']:
                        flash("Tu cuenta ha sido desactivada. Por favor, contacta a un administrador.", "warning")
                        session.clear()
                        return redirect(url_for('auth.login'))

                    g.user = user_data
                    
                    # Se cargan los roles del usuario en la sesión para un acceso rápido.
                    roles_data = db_conn.execute("""
                        SELECT r.nombre FROM roles r
                        JOIN usuario_roles ur ON r.id = ur.rol_id
                        WHERE ur.usuario_id = ?
                    """, (g.user['id'],)).fetchall()
                    session['user_roles'] = [row['nombre'] for row in roles_data]

                    # Se cargan las notificaciones no leídas del usuario.
                    g.notifications = db_conn.execute("""
                        SELECT id, mensaje, url, fecha_creacion FROM notificaciones 
                        WHERE usuario_id = ? AND leida = 0 ORDER BY fecha_creacion DESC
                    """, (g.user['id'],)).fetchall()
                else:
                    # Si el user_id en la sesión ya no es válido, se limpia la sesión.
                    session.clear()
        except sqlite3.OperationalError as e:
            if 'no such table' in str(e):
                current_app.logger.warning("La base de datos no está inicializada. Ejecute 'flask init-db'.")
            else:
                current_app.logger.error(f"Error operacional de base de datos: {e}")


    @app.context_processor
    def inject_global_vars():
        """
        Inyecta variables globales en el contexto de TODAS las plantillas Jinja2.
        Esto evita tener que pasar estas variables en cada `render_template`.
        """
        # NUEVO: Obtener la preferencia de tema del usuario de la sesión
        theme = session.get('theme', 'dark') # 'dark' es el tema por defecto si no hay preferencia
        
        return {
            'g': g,
            'app_name': "Hepta-Conexiones",
            'nombre_empresa': "Hepta Proyectos SAS",
            'creador': "Yimmy Moreno",
            'datetime': datetime,
            'theme': theme # Inyectar la preferencia de tema
        }

    @app.template_filter('format_datetime')
    def format_datetime_filter(value, format='%d de %b, %Y a las %H:%M'):
        """Filtro Jinja2 personalizado para formatear fechas y horas de una manera legible."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                # CORRECCIÓN: Probar el formato de SQLite antes que ISO
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    # Fallback a ISO si no es el formato estándar de SQLite
                    value = datetime.fromisoformat(value)
                except ValueError:
                    return value # Devuelve el valor original si no se puede convertir.
        return value.strftime(format)

    # Filtro para convertir una cadena JSON en un objeto Python
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

    # --- Registro de Blueprints ---
    # Los Blueprints organizan la aplicación en componentes modulares, cada uno con sus propias rutas.
    from routes import main, auth, conexiones, proyectos, admin, api
    app.register_blueprint(main.main_bp)
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(conexiones.conexiones_bp)
    app.register_blueprint(proyectos.proyectos_bp)
    app.register_blueprint(admin.admin_bp)
    app.register_blueprint(api.api_bp)
    
    # --- Manejadores de Errores Personalizados ---
    # Se definen plantillas personalizadas para los errores HTTP comunes.
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        # En caso de un error 500, se hace rollback a la sesión de la base de datos
        # para evitar dejar la base en un estado inconsistente.
        db_conn = getattr(g, 'db', None)
        if db_conn is not None:
            db_conn.rollback()
        return render_template('errors/500.html'), 500

    # --- Configuración de Logging ---
    # Se configura el logging solo cuando la aplicación no está en modo de depuración.
    if not app.debug and not app.testing:
        # En un entorno de producción (especialmente en contenedores), es mejor
        # loguear a la salida estándar (stdout/stderr) para que sea capturado
        # por Gunicorn y el orquestador de contenedores (ej. Docker, Kubernetes).
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        # Eliminar cualquier manejador por defecto que Flask pueda haber añadido
        app.logger.handlers.clear()
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Hepta-Conexiones startup')

    return app

# Se crea la instancia de la aplicación para que los servidores de producción (como Gunicorn) la puedan encontrar.
app = create_app()

if __name__ == '__main__':
    # Este bloque solo se ejecuta cuando se corre el script directamente (ej. 'python app.py').
    # No se usa en un entorno de producción.
    # Se asegura de que el scheduler solo se inicie una vez en el proceso principal (no en el proceso de reloader).
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' and app.scheduler and not app.scheduler.running:
        app.scheduler.start()
        app.logger.info("Scheduler de APScheduler iniciado en el proceso principal.")
        
    app.run(debug=True, host='0.0.0.0', port=5000)
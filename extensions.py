"""
extensions.py

Este archivo inicializa las extensiones de Flask (como CSRFProtect y Mail)
en un módulo separado para prevenir errores de importación circular.
"""

from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

csrf = CSRFProtect()
mail = Mail()
db = SQLAlchemy()
migrate = Migrate()

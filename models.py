"""
models.py

Este archivo contiene las definiciones de los modelos de la base de datos
utilizando SQLAlchemy ORM.
"""

from extensions import db
from sqlalchemy.sql import func
from datetime import datetime, timezone

# Tabla de asociación para la relación muchos a muchos entre Usuarios y Roles
usuario_roles = db.Table('usuario_roles',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('rol_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

# Tabla de asociación para la relación muchos a muchos entre Proyectos y Usuarios
proyecto_usuarios = db.Table('proyecto_usuarios',
    db.Column('proyecto_id', db.Integer, db.ForeignKey('proyectos.id'), primary_key=True),
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True)
)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    nombre_completo = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    roles = db.relationship('Rol', secondary=usuario_roles, back_populates='usuarios')
    proyectos_asignados = db.relationship('Proyecto', secondary=proyecto_usuarios, back_populates='usuarios_asignados')

class Rol(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String, unique=True, nullable=False)
    usuarios = db.relationship('Usuario', secondary=usuario_roles, back_populates='roles')

class Proyecto(db.Model):
    __tablename__ = 'proyectos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String, unique=True, nullable=False)
    descripcion = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))

    creador = db.relationship('Usuario', backref=db.backref('proyectos_creados', lazy=True))
    conexiones = db.relationship('Conexion', back_populates='proyecto', cascade="all, delete-orphan")
    usuarios_asignados = db.relationship('Usuario', secondary=proyecto_usuarios, back_populates='proyectos_asignados')

class Conexion(db.Model):
    __tablename__ = 'conexiones'
    id = db.Column(db.Integer, primary_key=True)
    codigo_conexion = db.Column(db.String, unique=True, nullable=False)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyectos.id'), nullable=False)
    tipo = db.Column(db.String, nullable=False)
    subtipo = db.Column(db.String, nullable=False)
    tipologia = db.Column(db.String, nullable=False)
    descripcion = db.Column(db.Text)
    detalles_json = db.Column(db.Text) # Almacenará JSON como texto
    estado = db.Column(db.String, nullable=False, default='SOLICITADO')
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    realizador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    aprobador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    fecha_modificacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    detalles_rechazo = db.Column(db.Text)

    proyecto = db.relationship('Proyecto', back_populates='conexiones')
    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    realizador = db.relationship('Usuario', foreign_keys=[realizador_id])
    aprobador = db.relationship('Usuario', foreign_keys=[aprobador_id])

    archivos = db.relationship('Archivo', back_populates='conexion', cascade="all, delete-orphan")
    comentarios = db.relationship('Comentario', back_populates='conexion', cascade="all, delete-orphan")
    historial = db.relationship('HistorialEstado', back_populates='conexion', cascade="all, delete-orphan")

class Archivo(db.Model):
    __tablename__ = 'archivos'
    id = db.Column(db.Integer, primary_key=True)
    conexion_id = db.Column(db.Integer, db.ForeignKey('conexiones.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    tipo_archivo = db.Column(db.String, nullable=False)
    nombre_archivo = db.Column(db.String, nullable=False)
    fecha_subida = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    conexion = db.relationship('Conexion', back_populates='archivos')
    usuario = db.relationship('Usuario', backref='archivos_subidos')

class Comentario(db.Model):
    __tablename__ = 'comentarios'
    id = db.Column(db.Integer, primary_key=True)
    conexion_id = db.Column(db.Integer, db.ForeignKey('conexiones.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    contenido = db.Column(db.Text, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    conexion = db.relationship('Conexion', back_populates='comentarios')
    usuario = db.relationship('Usuario', backref='comentarios_realizados')

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    url = db.Column(db.String, nullable=False)
    conexion_id = db.Column(db.Integer, db.ForeignKey('conexiones.id'))
    leida = db.Column(db.Boolean, nullable=False, default=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    usuario = db.relationship('Usuario', backref=db.backref('notificaciones', lazy='dynamic'))
    conexion = db.relationship('Conexion', backref='notificaciones')

class HistorialEstado(db.Model):
    __tablename__ = 'historial_estados'
    id = db.Column(db.Integer, primary_key=True)
    conexion_id = db.Column(db.Integer, db.ForeignKey('conexiones.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    estado = db.Column(db.String, nullable=False)
    detalles = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    conexion = db.relationship('Conexion', back_populates='historial')
    usuario = db.relationship('Usuario', backref='historial_acciones')

class Configuracion(db.Model):
    __tablename__ = 'configuracion'
    clave = db.Column(db.String, primary_key=True)
    valor = db.Column(db.String, nullable=False)

class Reporte(db.Model):
    __tablename__ = 'reportes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String, nullable=False)
    descripcion = db.Column(db.Text)
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    filtros = db.Column(db.Text, nullable=False) # JSON como texto
    programado = db.Column(db.Boolean, nullable=False, default=False)
    frecuencia = db.Column(db.String)
    destinatarios = db.Column(db.Text) # Lista de emails como texto
    ultima_ejecucion = db.Column(db.DateTime)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    creador = db.relationship('Usuario', backref='reportes_creados')

class AliasPerfil(db.Model):
    __tablename__ = 'alias_perfiles'
    id = db.Column(db.Integer, primary_key=True)
    nombre_perfil = db.Column(db.String, unique=True, nullable=False)
    alias = db.Column(db.String, unique=True, nullable=False)
    norma = db.Column(db.String)

class AuditoriaAccion(db.Model):
    __tablename__ = 'auditoria_acciones'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    accion = db.Column(db.String, nullable=False)
    tipo_objeto = db.Column(db.String)
    objeto_id = db.Column(db.Integer)
    detalles = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    usuario = db.relationship('Usuario', backref='acciones_auditadas')

class PreferenciaNotificacion(db.Model):
    __tablename__ = 'preferencias_notificaciones'
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True)
    email_notif_estado = db.Column(db.Boolean, nullable=False, default=True)

    usuario = db.relationship('Usuario', backref=db.backref('preferencias_notificacion', uselist=False))

class UserDashboardPreference(db.Model):
    __tablename__ = 'user_dashboard_preferences'
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True)
    widgets_config = db.Column(db.Text)

    usuario = db.relationship('Usuario', backref=db.backref('dashboard_preferences', uselist=False))

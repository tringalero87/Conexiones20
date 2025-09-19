-- ===================================================================================
-- Hepta-Conexiones - Esquema de Base de Datos para SQLite
-- Versión: 9.0
-- Adaptado para SQLite
-- ===================================================================================

-- -----------------------------------------------------
-- Tabla: usuarios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  nombre_completo TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: roles
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE
);

-- -----------------------------------------------------
-- Tabla: usuario_roles
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS usuario_roles (
  usuario_id INTEGER NOT NULL,
  rol_id INTEGER NOT NULL,
  PRIMARY KEY (usuario_id, rol_id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
  FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: proyectos
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS proyectos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  descripcion TEXT,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  creador_id INTEGER,
  FOREIGN KEY (creador_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: conexiones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS conexiones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo_conexion TEXT NOT NULL UNIQUE,
  proyecto_id INTEGER NOT NULL,
  tipo TEXT NOT NULL,
  subtipo TEXT NOT NULL,
  tipologia TEXT NOT NULL,
  descripcion TEXT,
  detalles_json TEXT,
  estado TEXT NOT NULL DEFAULT 'SOLICITADO'
    CHECK(estado IN ('SOLICITADO', 'EN_PROCESO', 'REALIZADO', 'APROBADO', 'RECHAZADO')),
  solicitante_id INTEGER,
  realizador_id INTEGER,
  aprobador_id INTEGER,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_modificacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  detalles_rechazo TEXT,
  FOREIGN KEY (proyecto_id) REFERENCES proyectos(id) ON DELETE CASCADE,
  FOREIGN KEY (solicitante_id) REFERENCES usuarios(id) ON DELETE SET NULL,
  FOREIGN KEY (realizador_id) REFERENCES usuarios(id) ON DELETE SET NULL,
  FOREIGN KEY (aprobador_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: archivos
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS archivos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conexion_id INTEGER NOT NULL,
  usuario_id INTEGER,
  tipo_archivo TEXT NOT NULL,
  nombre_archivo TEXT NOT NULL,
  fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conexion_id) REFERENCES conexiones(id) ON DELETE CASCADE,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: comentarios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conexion_id INTEGER NOT NULL,
  usuario_id INTEGER,
  contenido TEXT NOT NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conexion_id) REFERENCES conexiones(id) ON DELETE CASCADE,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: notificaciones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS notificaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER NOT NULL,
  mensaje TEXT NOT NULL,
  url TEXT NOT NULL,
  conexion_id INTEGER,
  leida INTEGER NOT NULL DEFAULT 0,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
  FOREIGN KEY (conexion_id) REFERENCES conexiones(id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: historial_estados
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_estados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conexion_id INTEGER NOT NULL,
  usuario_id INTEGER,
  estado TEXT NOT NULL,
  detalles TEXT,
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conexion_id) REFERENCES conexiones(id) ON DELETE CASCADE,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: proyecto_usuarios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS proyecto_usuarios (
    proyecto_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    PRIMARY KEY (proyecto_id, usuario_id),
    FOREIGN KEY (proyecto_id) REFERENCES proyectos(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: configuracion
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

-- -----------------------------------------------------
-- Tabla: reportes
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS reportes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    creador_id INTEGER NOT NULL,
    filtros TEXT NOT NULL,
    programado INTEGER NOT NULL DEFAULT 0,
    frecuencia TEXT,
    destinatarios TEXT,
    ultima_ejecucion TIMESTAMP,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creador_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: alias_perfiles
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS alias_perfiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_perfil TEXT NOT NULL UNIQUE,
  alias TEXT NOT NULL UNIQUE,
  norma TEXT
);

-- -----------------------------------------------------
-- Tabla: auditoria_acciones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS auditoria_acciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    accion TEXT NOT NULL,
    tipo_objeto TEXT,
    objeto_id INTEGER,
    detalles TEXT,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: preferencias_notificaciones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS preferencias_notificaciones (
    usuario_id INTEGER PRIMARY KEY,
    email_notif_estado INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: user_dashboard_preferences
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS user_dashboard_preferences (
  usuario_id INTEGER PRIMARY KEY,
  widgets_config TEXT,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Vistas (VIEWS)
-- -----------------------------------------------------

DROP VIEW IF EXISTS conexiones_view;
CREATE VIEW conexiones_view AS
SELECT 
    c.id, c.codigo_conexion, c.proyecto_id, p.nombre as proyecto_nombre,
    c.tipo, c.subtipo, c.tipologia, c.descripcion, c.detalles_json, c.estado,
    c.solicitante_id, sol.nombre_completo as solicitante_nombre,
    c.realizador_id, real.nombre_completo as realizador_nombre,
    c.aprobador_id, aprob.nombre_completo as aprobador_nombre,
    c.fecha_creacion, c.fecha_modificacion, c.detalles_rechazo
FROM conexiones c
LEFT JOIN proyectos p ON c.proyecto_id = p.id
LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
LEFT JOIN usuarios real ON c.realizador_id = real.id
LEFT JOIN usuarios aprob ON c.aprobador_id = aprob.id;

DROP VIEW IF EXISTS historial_detallado_view;
CREATE VIEW historial_detallado_view AS
SELECT
    h.id, h.conexion_id, h.estado, h.fecha, h.detalles,
    u.nombre_completo as usuario_nombre,
    c.codigo_conexion
FROM historial_estados h
JOIN usuarios u ON h.usuario_id = u.id
JOIN conexiones c ON h.conexion_id = c.id;

-- -----------------------------------------------------
-- INSERCIÓN DE DATOS INICIALES
-- -----------------------------------------------------
INSERT OR IGNORE INTO roles (nombre) VALUES ('ADMINISTRADOR'), ('APROBADOR'), ('REALIZADOR'), ('SOLICITANTE');
INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('PER_PAGE', '10');
INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('MAINTENANCE_MODE', '0');

-- -----------------------------------------------------
-- Índices
-- -----------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_conexiones_estado ON conexiones (estado);
CREATE INDEX IF NOT EXISTS idx_conexiones_proyecto_id ON conexiones (proyecto_id);
CREATE INDEX IF NOT EXISTS idx_notificaciones_usuario_id ON notificaciones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario_id ON auditoria_acciones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_accion ON auditoria_acciones (accion);
CREATE INDEX IF NOT EXISTS idx_auditoria_tipo_objeto_id ON auditoria_acciones (tipo_objeto, objeto_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_solicitante_id ON conexiones (solicitante_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_realizador_id ON conexiones (realizador_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_aprobador_id ON conexiones (aprobador_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_fecha_creacion ON conexiones (fecha_creacion);
CREATE INDEX IF NOT EXISTS idx_conexiones_fecha_modificacion ON conexiones (fecha_modificacion);
CREATE INDEX IF NOT EXISTS idx_conexiones_estado_realizador ON conexiones (estado, realizador_id);

-- -----------------------------------------------------
-- -----------------------------------------------------
-- Fin del esquema
-- -----------------------------------------------------

-- ===================================================================================
-- Tablas Virtuales FTS5 para Búsqueda de Texto Completo
-- ===================================================================================

-- -----------------------------------------------------
-- Tabla FTS para: conexiones
-- Indexa 'codigo_conexion' y 'descripcion' para búsquedas rápidas.
-- -----------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS conexiones_fts USING fts5(
    codigo_conexion,
    descripcion,
    content='conexiones',
    content_rowid='id'
);

-- Triggers para mantener la tabla FTS sincronizada con la tabla 'conexiones'
CREATE TRIGGER IF NOT EXISTS t_conexiones_after_insert AFTER INSERT ON conexiones BEGIN
  INSERT INTO conexiones_fts(rowid, codigo_conexion, descripcion)
  VALUES (new.id, new.codigo_conexion, new.descripcion);
END;

CREATE TRIGGER IF NOT EXISTS t_conexiones_after_delete AFTER DELETE ON conexiones BEGIN
  INSERT INTO conexiones_fts(conexiones_fts, rowid, codigo_conexion, descripcion)
  VALUES ('delete', old.id, old.codigo_conexion, old.descripcion);
END;

CREATE TRIGGER IF NOT EXISTS t_conexiones_after_update AFTER UPDATE ON conexiones BEGIN
  INSERT INTO conexiones_fts(conexiones_fts, rowid, codigo_conexion, descripcion)
  VALUES ('delete', old.id, old.codigo_conexion, old.descripcion);
  INSERT INTO conexiones_fts(rowid, codigo_conexion, descripcion)
  VALUES (new.id, new.codigo_conexion, new.descripcion);
END;


-- -----------------------------------------------------
-- Tabla FTS para: alias_perfiles
-- Indexa 'nombre_perfil' y 'alias' para búsquedas rápidas.
-- Se utiliza un tokenizador personalizado para manejar prefijos y normalización.
-- -----------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS alias_perfiles_fts USING fts5(
    nombre_perfil,
    alias,
    content='alias_perfiles',
    content_rowid='id',
    tokenize = "unicode61"
);

-- Triggers para mantener la tabla FTS sincronizada con la tabla 'alias_perfiles'
CREATE TRIGGER IF NOT EXISTS t_alias_after_insert AFTER INSERT ON alias_perfiles BEGIN
  INSERT INTO alias_perfiles_fts(rowid, nombre_perfil, alias)
  VALUES (new.id, new.nombre_perfil, new.alias);
END;

CREATE TRIGGER IF NOT EXISTS t_alias_after_delete AFTER DELETE ON alias_perfiles BEGIN
  INSERT INTO alias_perfiles_fts(alias_perfiles_fts, rowid, nombre_perfil, alias)
  VALUES ('delete', old.id, old.nombre_perfil, old.alias);
END;

CREATE TRIGGER IF NOT EXISTS t_alias_after_update AFTER UPDATE ON alias_perfiles BEGIN
  INSERT INTO alias_perfiles_fts(alias_perfiles_fts, rowid, nombre_perfil, alias)
  VALUES ('delete', old.id, old.nombre_perfil, old.alias);
  INSERT INTO alias_perfiles_fts(rowid, nombre_perfil, alias)
  VALUES (new.id, new.nombre_perfil, new.alias);
END;
-- ===================================================================================
-- Hepta-Conexiones - Esquema de Base de Datos PostgreSQL
-- Versión: 9.0
-- Creador: Yimmy Moreno (Adaptado por Jules)
--
-- Este script define la estructura de la base de datos para PostgreSQL.
-- ===================================================================================

-- -----------------------------------------------------
-- Tabla: usuarios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
  id SERIAL PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  nombre_completo TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: roles
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE
);

-- -----------------------------------------------------
-- Tabla: usuario_roles
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS usuario_roles (
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  rol_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (usuario_id, rol_id)
);

-- -----------------------------------------------------
-- Tabla: proyectos
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS proyectos (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  descripcion TEXT,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  creador_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: conexiones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS conexiones (
  id SERIAL PRIMARY KEY,
  codigo_conexion TEXT NOT NULL UNIQUE,
  proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
  tipo TEXT NOT NULL,
  subtipo TEXT NOT NULL,
  tipologia TEXT NOT NULL,
  descripcion TEXT,
  detalles_json JSONB,
  estado TEXT NOT NULL DEFAULT 'SOLICITADO'
    CHECK(estado IN ('SOLICITADO', 'EN_PROCESO', 'REALIZADO', 'APROBADO', 'RECHAZADO')),
  solicitante_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  realizador_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  aprobador_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_modificacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  detalles_rechazo TEXT
);

-- -----------------------------------------------------
-- Tabla: archivos
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS archivos (
  id SERIAL PRIMARY KEY,
  conexion_id INTEGER NOT NULL REFERENCES conexiones(id) ON DELETE CASCADE,
  usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  tipo_archivo TEXT NOT NULL,
  nombre_archivo TEXT NOT NULL,
  fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: comentarios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios (
  id SERIAL PRIMARY KEY,
  conexion_id INTEGER NOT NULL REFERENCES conexiones(id) ON DELETE CASCADE,
  usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  contenido TEXT NOT NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: notificaciones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS notificaciones (
  id SERIAL PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  mensaje TEXT NOT NULL,
  url TEXT NOT NULL,
  conexion_id INTEGER REFERENCES conexiones(id) ON DELETE CASCADE,
  leida BOOLEAN NOT NULL DEFAULT FALSE,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: historial_estados
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_estados (
  id SERIAL PRIMARY KEY,
  conexion_id INTEGER NOT NULL REFERENCES conexiones(id) ON DELETE CASCADE,
  usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  estado TEXT NOT NULL,
  detalles TEXT,
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: proyecto_usuarios
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS proyecto_usuarios (
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    PRIMARY KEY (proyecto_id, usuario_id)
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
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    creador_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    filtros JSONB NOT NULL,
    programado BOOLEAN NOT NULL DEFAULT FALSE,
    frecuencia TEXT,
    destinatarios TEXT,
    ultima_ejecucion TIMESTAMP,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: alias_perfiles
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS alias_perfiles (
  id SERIAL PRIMARY KEY,
  nombre_perfil TEXT NOT NULL UNIQUE,
  alias TEXT NOT NULL UNIQUE,
  norma TEXT
);

-- -----------------------------------------------------
-- Tabla: auditoria_acciones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS auditoria_acciones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    accion TEXT NOT NULL,
    tipo_objeto TEXT,
    objeto_id INTEGER,
    detalles JSONB,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Tabla: preferencias_notificaciones
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS preferencias_notificaciones (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    email_notif_estado BOOLEAN NOT NULL DEFAULT TRUE
);

-- -----------------------------------------------------
-- Tabla: user_dashboard_preferences
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS user_dashboard_preferences (
  usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
  widgets_config JSONB
);

-- -----------------------------------------------------
-- Vistas (VIEWS)
-- -----------------------------------------------------

CREATE OR REPLACE VIEW conexiones_view AS
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

CREATE OR REPLACE VIEW historial_detallado_view AS
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
INSERT INTO roles (nombre) VALUES ('ADMINISTRADOR'), ('APROBADOR'), ('REALIZADOR'), ('SOLICITANTE') ON CONFLICT (nombre) DO NOTHING;
INSERT INTO configuracion (clave, valor) VALUES ('PER_PAGE', '10') ON CONFLICT (clave) DO NOTHING;
INSERT INTO configuracion (clave, valor) VALUES ('MAINTENANCE_MODE', '0') ON CONFLICT (clave) DO NOTHING;

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
-- Búsqueda de Texto Completo (Full-Text Search)
-- -----------------------------------------------------
-- 1. Añadir una columna tsvector a la tabla de conexiones
ALTER TABLE conexiones ADD COLUMN IF NOT EXISTS fts_document tsvector;

-- 2. Crear una función para actualizar la columna tsvector
CREATE OR REPLACE FUNCTION update_conexiones_fts_document()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fts_document :=
        to_tsvector('simple', COALESCE(NEW.codigo_conexion, '')) ||
        to_tsvector('simple', COALESCE(NEW.tipologia, '')) ||
        to_tsvector('simple', COALESCE(NEW.descripcion, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Crear un trigger para llamar a la función en cada inserción o actualización
DROP TRIGGER IF EXISTS tsvector_update ON conexiones;
CREATE TRIGGER tsvector_update
BEFORE INSERT OR UPDATE ON conexiones
FOR EACH ROW
EXECUTE FUNCTION update_conexiones_fts_document();

-- 4. Crear un índice GIN en la nueva columna para acelerar las búsquedas
CREATE INDEX IF NOT EXISTS idx_conexiones_fts ON conexiones USING gin(fts_document);
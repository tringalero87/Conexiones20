-- ===================================================================================
-- Hepta-Conexiones - Esquema de Base de Datos SQLite
-- Versión: 8.2 (Esquema Final, Documentado y con todas las Tablas/Vistas)
-- Creador: Yimmy Moreno
--
-- Este script define la estructura completa y mejorada de la base de datos.
-- Se han añadido comentarios detallados para explicar el propósito de cada
-- tabla y columna, y se ha asegurado que el script sea idempotente
-- (se puede ejecutar múltiples veces sin errores) usando 'IF NOT EXISTS'.
-- ===================================================================================

-- Habilita el soporte para claves foráneas en SQLite. Es crucial para mantener la integridad
-- referencial de los datos (ej. una conexión no puede existir sin un proyecto).
PRAGMA foreign_keys = ON;

-- -----------------------------------------------------
-- Tabla: usuarios
-- Almacena la información de las cuentas de todos los usuarios del sistema.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Identificador único para cada usuario.
  username TEXT NOT NULL UNIQUE,             -- Nombre de usuario para el login, debe ser único.
  nombre_completo TEXT NOT NULL,             -- Nombre completo del usuario para mostrar en la interfaz.
  email TEXT NOT NULL UNIQUE,                -- Correo electrónico, debe ser único.
  password_hash TEXT NOT NULL,               -- Contraseña hasheada para almacenamiento seguro.
  activo BOOLEAN NOT NULL DEFAULT 1,         -- Indica si la cuenta está activa (1) o desactivada (0).
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP -- Fecha y hora de creación de la cuenta.
);

-- -----------------------------------------------------
-- Tabla: roles
-- Define los roles disponibles en el sistema (ej: ADMINISTRADOR, REALIZADOR).
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Identificador único para cada rol.
  nombre TEXT NOT NULL UNIQUE                -- Nombre del rol (ej: 'ADMINISTRADOR').
);

-- -----------------------------------------------------
-- Tabla: usuario_roles (Tabla de Unión)
-- Asocia usuarios con sus respectivos roles, implementando una relación Muchos a Muchos.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS usuario_roles (
  usuario_id INTEGER NOT NULL,               -- Clave foránea que apunta al ID del usuario.
  rol_id INTEGER NOT NULL,                   -- Clave foránea que apunta al ID del rol.
  PRIMARY KEY (usuario_id, rol_id),          -- La clave primaria compuesta previene entradas duplicadas.
  FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE,
  FOREIGN KEY (rol_id) REFERENCES roles (id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: proyectos
-- Almacena la información de los proyectos de construcción.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS proyectos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Identificador único para cada proyecto.
  nombre TEXT NOT NULL UNIQUE,               -- Nombre del proyecto, debe ser único.
  descripcion TEXT,                          -- Descripción opcional del proyecto.
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación del proyecto.
  creador_id INTEGER,                        -- ID del usuario que creó el proyecto.
  FOREIGN KEY (creador_id) REFERENCES usuarios (id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: conexiones
-- La tabla principal del sistema. Almacena cada solicitud de conexión codificada.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS conexiones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Identificador único para cada conexión.
  codigo_conexion TEXT NOT NULL UNIQUE,      -- Código único generado por el sistema (ej: MV-IPE300-T1).
  proyecto_id INTEGER NOT NULL,              -- ID del proyecto al que pertenece la conexión.
  tipo TEXT NOT NULL,                        -- Tipo principal de conexión (ej: 'MOMENTO').
  subtipo TEXT NOT NULL,                     -- Subtipo dentro del tipo principal (ej: 'VIGA-COLUMNA (ALA)').
  tipologia TEXT NOT NULL,                   -- Tipología específica (ej: 'T0', 'T1').
  descripcion TEXT,                          -- Descripción opcional proporcionada por el solicitante.
  detalles_json TEXT,                        -- Almacena datos dinámicos (perfiles, etc.) en formato JSON.
  estado TEXT NOT NULL DEFAULT 'SOLICITADO'
    -- Se añade una restricción CHECK para garantizar la integridad de los datos de estado.
    CHECK(estado IN ('SOLICITADO', 'EN_PROCESO', 'REALIZADO', 'APROBADO', 'RECHAZADO')),
  solicitante_id INTEGER,                    -- ID del usuario que solicitó la conexión.
  realizador_id INTEGER,                     -- ID del usuario que está realizando la conexión.
  aprobador_id INTEGER,                      -- ID del usuario que aprobó la conexión.
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Fecha de creación de la solicitud.
  fecha_modificacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Fecha de la última modificación de estado.
  detalles_rechazo TEXT,                     -- Almacena el motivo del rechazo.
  FOREIGN KEY (proyecto_id) REFERENCES proyectos (id) ON DELETE CASCADE,
  FOREIGN KEY (solicitante_id) REFERENCES usuarios (id) ON DELETE SET NULL,
  FOREIGN KEY (realizador_id) REFERENCES usuarios (id) ON DELETE SET NULL,
  FOREIGN KEY (aprobador_id) REFERENCES usuarios (id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: archivos
-- Almacena metadatos de los archivos subidos para cada conexión.
-- ON DELETE CASCADE asegura que si se borra una conexión, todos sus archivos se borran también.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS archivos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Identificador único del archivo.
  conexion_id INTEGER NOT NULL,              -- ID de la conexión a la que pertenece el archivo.
  usuario_id INTEGER,                        -- ID del usuario que subió el archivo.
  tipo_archivo TEXT NOT NULL,                -- Tipo de archivo según la plantilla (ej: 'Memoria De Calculo (.PDF)').
  nombre_archivo TEXT NOT NULL,              -- Nombre del archivo guardado en el sistema de archivos.
  fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Fecha y hora de subida.
  FOREIGN KEY (conexion_id) REFERENCES conexiones (id) ON DELETE CASCADE,
  FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: comentarios
-- Almacena la discusión y comunicación dentro de una conexión específica.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,      -- Identificador único del comentario.
  conexion_id INTEGER NOT NULL,              -- ID de la conexión a la que pertenece el comentario.
  usuario_id INTEGER,                        -- ID del usuario que escribió el comentario.
  contenido TEXT NOT NULL,                   -- El texto del comentario (HTML sanitizado).
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conexion_id) REFERENCES conexiones (id) ON DELETE CASCADE,
  FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: notificaciones
-- Almacena notificaciones para los usuarios sobre eventos importantes en el sistema.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS notificaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER NOT NULL,               -- ID del usuario que recibirá la notificación.
  mensaje TEXT NOT NULL,                     -- El texto de la notificación (ej: "Nueva conexión asignada").
  url TEXT NOT NULL,                         -- La URL a la que se redirigirá al usuario al hacer clic.
  conexion_id INTEGER,                       -- ID de la conexión relacionada (si aplica).
  leida BOOLEAN NOT NULL DEFAULT 0,          -- Indica si la notificación ha sido leída (1) o no (0).
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE,
  FOREIGN KEY (conexion_id) REFERENCES conexiones (id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: historial_estados
-- Registra cada cambio de estado de una conexión para una trazabilidad completa.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_estados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conexion_id INTEGER NOT NULL,
  usuario_id INTEGER,
  estado TEXT NOT NULL,                      -- El estado al que se cambió (ej: 'APROBADO').
  detalles TEXT,                             -- Detalles adicionales (ej: motivo del rechazo).
  fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conexion_id) REFERENCES conexiones (id) ON DELETE CASCADE,
  FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: proyecto_usuarios (Tabla de Unión)
-- Asocia usuarios a los proyectos a los que tienen acceso. Relación Muchos a Muchos.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS proyecto_usuarios (
    proyecto_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    PRIMARY KEY (proyecto_id, usuario_id),
    FOREIGN KEY (proyecto_id) REFERENCES proyectos (id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: configuracion
-- Un almacén simple de clave-valor para ajustes globales de la aplicación.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

-- -----------------------------------------------------
-- Tabla: reportes
-- Almacena las configuraciones de reportes guardados y programados por los administradores.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS reportes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    descripcion TEXT, -- Añadido este campo para la descripción del reporte
    creador_id INTEGER NOT NULL,
    filtros TEXT NOT NULL, -- Almacena los filtros del reporte en formato JSON.
    programado BOOLEAN NOT NULL DEFAULT 0,
    frecuencia TEXT, -- 'diaria', 'semanal', 'mensual'
    destinatarios TEXT, -- Almacena emails separados por comas.
    ultima_ejecucion TIMESTAMP,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creador_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: alias_perfiles
-- Almacena los alias para los nombres de perfiles de acero.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS alias_perfiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_perfil TEXT NOT NULL UNIQUE,
  alias TEXT NOT NULL UNIQUE,
  norma TEXT -- Nueva columna 'norma'
);


-- -----------------------------------------------------
-- Tabla: auditoria_acciones (NUEVA)
-- Registra todas las acciones significativas realizadas por los usuarios y el sistema.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS auditoria_acciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,                    -- ID del usuario que realizó la acción (NULL si es acción del sistema/no autenticado)
    accion TEXT NOT NULL,                  -- Tipo de acción (ej. 'INICIAR_SESION', 'CREAR_CONEXION', 'ELIMINAR_USUARIO')
    tipo_objeto TEXT,                      -- Tipo de entidad afectada (ej. 'usuarios', 'conexiones', 'proyectos', 'sistema')
    objeto_id INTEGER,                     -- ID del objeto afectado (ej. ID de usuario, ID de conexión)
    detalles TEXT,                         -- Detalles adicionales de la acción (ej. cambios en formato JSON, motivo)
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
);

-- -----------------------------------------------------
-- Tabla: preferencias_notificaciones (NUEVA)
-- Permite a los usuarios personalizar qué tipos de notificaciones desean recibir.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS preferencias_notificaciones (
    usuario_id INTEGER PRIMARY KEY,        -- ID del usuario
    email_notif_estado BOOLEAN NOT NULL DEFAULT 1, -- Recibir email por cambios de estado (1=sí, 0=no)
    -- Añadir más campos booleanos para otros tipos de notificaciones personalizables
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Tabla: user_dashboard_preferences (NUEVA)
-- Almacena las preferencias de personalización del dashboard por usuario.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS user_dashboard_preferences (
  usuario_id INTEGER PRIMARY KEY,
  widgets_config TEXT, -- Almacena la configuración de widgets en JSON (ej. {'order': ['my_summary', 'my_tasks'], 'visible': {'my_summary': true}})
  FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);


-- -----------------------------------------------------
-- Vistas (VIEWS) para simplificar consultas complejas
-- -----------------------------------------------------

CREATE VIEW IF NOT EXISTS conexiones_view AS
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

CREATE VIEW IF NOT EXISTS historial_detallado_view AS
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
-- Índices para mejorar el rendimiento de las consultas más frecuentes.
-- -----------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_conexiones_estado ON conexiones (estado);
CREATE INDEX IF NOT EXISTS idx_conexiones_proyecto_id ON conexiones (proyecto_id);
CREATE INDEX IF NOT EXISTS idx_notificaciones_usuario_id ON notificaciones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario_id ON auditoria_acciones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_accion ON auditoria_acciones (accion);
CREATE INDEX IF NOT EXISTS idx_auditoria_tipo_objeto_id ON auditoria_acciones (tipo_objeto, objeto_id);

-- Índices para optimizar las consultas del dashboard y de listas de tareas.
CREATE INDEX IF NOT EXISTS idx_conexiones_solicitante_id ON conexiones (solicitante_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_realizador_id ON conexiones (realizador_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_aprobador_id ON conexiones (aprobador_id);
CREATE INDEX IF NOT EXISTS idx_conexiones_fecha_creacion ON conexiones (fecha_creacion);
CREATE INDEX IF NOT EXISTS idx_conexiones_fecha_modificacion ON conexiones (fecha_modificacion);
-- Índice compuesto para optimizar la búsqueda de tareas por estado y usuario.
CREATE INDEX IF NOT EXISTS idx_conexiones_estado_realizador ON conexiones (estado, realizador_id);


-- -----------------------------------------------------
-- Búsqueda de Texto Completo (Full-Text Search - FTS5)
-- Tabla virtual para realizar búsquedas eficientes en las conexiones.
-- -----------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS conexiones_fts USING fts5(
    codigo_conexion,
    tipologia,
    descripcion,
    content='conexiones',
    content_rowid='id'
);

-- -----------------------------------------------------
-- Triggers (Disparadores) para mantener la tabla FTS sincronizada automáticamente.
-- -----------------------------------------------------

CREATE TRIGGER IF NOT EXISTS conexiones_after_insert AFTER INSERT ON conexiones BEGIN
  INSERT INTO conexiones_fts(rowid, codigo_conexion, tipologia, descripcion)
  VALUES (new.id, new.codigo_conexion, new.tipologia, new.descripcion);
END;

CREATE TRIGGER IF NOT EXISTS conexiones_after_delete AFTER DELETE ON conexiones BEGIN
  INSERT INTO conexiones_fts(conexiones_fts, rowid, codigo_conexion, tipologia, descripcion)
  VALUES ('delete', old.id, old.codigo_conexion, old.tipologia, old.descripcion);
END;

CREATE TRIGGER IF NOT EXISTS conexiones_after_update AFTER UPDATE ON conexiones BEGIN
  INSERT INTO conexiones_fts(conexiones_fts, rowid, codigo_conexion, tipologia, descripcion)
  VALUES ('delete', old.id, old.codigo_conexion, old.tipologia, old.descripcion);
  INSERT INTO conexiones_fts(rowid, codigo_conexion, tipologia, descripcion)
  VALUES (new.id, new.codigo_conexion, new.tipologia, new.descripcion);
END;
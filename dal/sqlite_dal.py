from db import get_db
from .base_dal import BaseDAL
import json

class SQLiteDAL(BaseDAL):

    def get_conexion(self, conexion_id):
        db = get_db()
        sql = """
            SELECT c.*, p.nombre as proyecto_nombre,
                   sol.nombre_completo as solicitante_nombre,
                   real.nombre_completo as realizador_nombre,
                   aprob.nombre_completo as aprobador_nombre
            FROM conexiones c
            JOIN proyectos p ON c.proyecto_id = p.id
            LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
            LEFT JOIN usuarios real ON c.realizador_id = real.id
            LEFT JOIN usuarios aprob ON c.aprobador_id = aprob.id
            WHERE c.id = ?
        """
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id,))
        return cursor.fetchone()

    def get_conexiones_by_proyecto(self, proyecto_id):
        db = get_db()
        sql = "SELECT * FROM conexiones WHERE proyecto_id = ? ORDER BY fecha_creacion DESC"
        cursor = db.cursor()
        cursor.execute(sql, (proyecto_id,))
        return cursor.fetchall()

    def create_conexion(self, conexion_data):
        db = get_db()
        sql = """
            INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, descripcion, detalles_json, solicitante_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = db.cursor()
        cursor.execute(sql, (
            conexion_data['codigo_conexion'],
            conexion_data['proyecto_id'],
            conexion_data['tipo'],
            conexion_data['subtipo'],
            conexion_data['tipologia'],
            conexion_data['descripcion'],
            json.dumps(conexion_data['detalles_json']),
            conexion_data['solicitante_id']
        ))
        new_id = cursor.lastrowid
        db.commit()
        return new_id

    def update_conexion(self, conexion_id, conexion_data):
        db = get_db()
        sql = """
            UPDATE conexiones
            SET codigo_conexion = ?, descripcion = ?, detalles_json = ?, fecha_modificacion = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        cursor = db.cursor()
        cursor.execute(sql, (
            conexion_data['codigo_conexion'],
            conexion_data['descripcion'],
            json.dumps(conexion_data['detalles_json']),
            conexion_id
        ))
        db.commit()

    def delete_conexion(self, conexion_id):
        db = get_db()
        sql = 'DELETE FROM conexiones WHERE id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id,))
        db.commit()

    def search_conexiones(self, query):
        db = get_db()
        # Simple search for SQLite, using LIKE
        term = f"%{query}%"
        sql = """
            SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre
            FROM conexiones c
            JOIN proyectos p ON c.proyecto_id = p.id
            LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
            WHERE c.codigo_conexion LIKE ? OR c.tipo LIKE ? OR c.subtipo LIKE ? OR c.tipologia LIKE ? OR c.descripcion LIKE ?
            ORDER BY c.fecha_creacion DESC
        """
        params = (term, term, term, term, term)
        cursor = db.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    def get_proyectos_for_user(self, user_id, is_admin):
        db = get_db()
        cursor = db.cursor()
        if is_admin:
            cursor.execute("SELECT id, nombre FROM proyectos ORDER BY nombre")
        else:
            sql = """
                SELECT p.id, p.nombre FROM proyectos p
                JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
                WHERE pu.usuario_id = ? ORDER BY p.nombre
            """
            cursor.execute(sql, (user_id,))
        return cursor.fetchall()

    def get_proyecto(self, proyecto_id):
        db = get_db()
        sql = 'SELECT * FROM proyectos WHERE id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (proyecto_id,))
        return cursor.fetchone()

    def get_alias(self, nombre_perfil):
        db = get_db()
        sql = 'SELECT alias FROM alias_perfiles WHERE nombre_perfil = ?'
        cursor = db.cursor()
        cursor.execute(sql, (nombre_perfil,))
        return cursor.fetchone()

    def get_all_aliases(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT alias, nombre_perfil FROM alias_perfiles ORDER BY nombre_perfil")
        return cursor.fetchall()

    def get_all_conexiones_codes(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT codigo_conexion FROM conexiones")
        return set(row['codigo_conexion'] for row in cursor.fetchall())

    def get_archivos_by_conexion(self, conexion_id):
        db = get_db()
        sql = 'SELECT a.*, u.nombre_completo as subido_por FROM archivos a JOIN usuarios u ON a.usuario_id = u.id WHERE a.conexion_id = ? ORDER BY a.fecha_subida DESC'
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id,))
        return cursor.fetchall()

    def get_comentarios_by_conexion(self, conexion_id):
        db = get_db()
        sql = "SELECT c.*, u.nombre_completo FROM comentarios c JOIN usuarios u ON c.usuario_id = u.id WHERE c.conexion_id = ? ORDER BY c.fecha_creacion DESC"
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id,))
        return cursor.fetchall()

    def get_historial_by_conexion(self, conexion_id):
        db = get_db()
        sql = "SELECT h.*, u.nombre_completo FROM historial_estados h JOIN usuarios u ON h.usuario_id = u.id WHERE h.conexion_id = ? ORDER BY h.fecha DESC"
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id,))
        return cursor.fetchall()

    def get_usuario_a_asignar(self, username):
        db = get_db()
        sql = 'SELECT id, nombre_completo FROM usuarios WHERE username = ? AND activo = 1'
        cursor = db.cursor()
        cursor.execute(sql, (username,))
        return cursor.fetchone()

    def update_conexion_realizador(self, conexion_id, realizador_id, nuevo_estado=None):
        db = get_db()
        cursor = db.cursor()
        if nuevo_estado:
            sql = 'UPDATE conexiones SET realizador_id = ?, estado = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?'
            cursor.execute(sql, (realizador_id, nuevo_estado, conexion_id))
        else:
            sql = 'UPDATE conexiones SET realizador_id = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?'
            cursor.execute(sql, (realizador_id, conexion_id))
        db.commit()

    def add_historial_estado(self, conexion_id, usuario_id, estado, detalles=None):
        db = get_db()
        sql = 'INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES (?, ?, ?, ?)'
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id, usuario_id, estado, detalles))
        db.commit()

    def create_archivo(self, conexion_id, usuario_id, tipo_archivo, filename):
        db = get_db()
        sql = 'INSERT INTO archivos (conexion_id, usuario_id, tipo_archivo, nombre_archivo) VALUES (?, ?, ?, ?)'
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id, usuario_id, tipo_archivo, filename))
        db.commit()

    def get_archivo(self, archivo_id, conexion_id):
        db = get_db()
        sql = 'SELECT * FROM archivos WHERE id = ? AND conexion_id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (archivo_id, conexion_id))
        return cursor.fetchone()

    def delete_archivo(self, archivo_id):
        db = get_db()
        sql = 'DELETE FROM archivos WHERE id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (archivo_id,))
        db.commit()

    def create_comentario(self, conexion_id, usuario_id, contenido):
        db = get_db()
        sql = 'INSERT INTO comentarios (conexion_id, usuario_id, contenido) VALUES (?, ?, ?)'
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id, usuario_id, contenido))
        db.commit()

    def get_comentario(self, comentario_id, conexion_id):
        db = get_db()
        sql = 'SELECT * FROM comentarios WHERE id = ? AND conexion_id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (comentario_id, conexion_id))
        return cursor.fetchone()

    def delete_comentario(self, comentario_id):
        db = get_db()
        sql = 'DELETE FROM comentarios WHERE id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (comentario_id,))
        db.commit()

    def get_users_for_notification(self, proyecto_id, roles_to_notify):
        db = get_db()
        placeholders = ', '.join(['?'] * len(roles_to_notify))
        sql = f"""
            SELECT DISTINCT u.id, u.email, u.nombre_completo, COALESCE(pn.email_notif_estado, 1) as email_notif_estado
            FROM usuarios u
            JOIN proyecto_usuarios pu ON u.id = pu.usuario_id
            JOIN usuario_roles ur ON u.id = ur.usuario_id
            JOIN roles r ON ur.rol_id = r.id
            LEFT JOIN preferencias_notificaciones pn ON u.id = pn.usuario_id
            WHERE pu.proyecto_id = ? AND r.nombre IN ({placeholders}) AND u.activo = 1
        """

        params = [proyecto_id] + roles_to_notify
        cursor = db.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    def create_notification(self, usuario_id, mensaje, url, conexion_id):
        db = get_db()
        sql = 'INSERT INTO notificaciones (usuario_id, mensaje, url, conexion_id) VALUES (?, ?, ?, ?)'
        cursor = db.cursor()
        cursor.execute(sql, (usuario_id, mensaje, url, conexion_id))
        db.commit()

    def get_all_users_with_roles(self):
        db = get_db()
        sql = """
            SELECT
                u.id, u.username, u.nombre_completo, u.email, u.activo,
                GROUP_CONCAT(r.nombre, ', ') as roles
            FROM usuarios u
            LEFT JOIN usuario_roles ur ON u.id = ur.usuario_id
            LEFT JOIN roles r ON ur.rol_id = r.id
            GROUP BY u.id
            ORDER BY u.nombre_completo
        """
        cursor = db.cursor()
        cursor.execute(sql)
        return cursor.fetchall()

    def get_roles(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT nombre FROM roles ORDER BY nombre')
        return cursor.fetchall()

    def create_user(self, username, nombre_completo, email, password_hash, activo):
        db = get_db()
        sql = 'INSERT INTO usuarios (username, nombre_completo, email, password_hash, activo) VALUES (?, ?, ?, ?, ?)'
        cursor = db.cursor()
        cursor.execute(sql, (username, nombre_completo, email, password_hash, activo))
        return cursor.lastrowid

    def get_role_id_by_name(self, name):
        db = get_db()
        sql = 'SELECT id FROM roles WHERE nombre = ?'
        cursor = db.cursor()
        cursor.execute(sql, (name,))
        return cursor.fetchone()

    def assign_role_to_user(self, user_id, role_id):
        db = get_db()
        sql = 'INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (?, ?)'
        cursor = db.cursor()
        cursor.execute(sql, (user_id, role_id))

    def get_user_by_id(self, user_id):
        db = get_db()
        sql = "SELECT * FROM usuarios WHERE id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return cursor.fetchone()

    def update_user(self, user_id, username, nombre_completo, email, activo):
        db = get_db()
        sql = "UPDATE usuarios SET username = ?, nombre_completo = ?, email = ?, activo = ? WHERE id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (username, nombre_completo, email, activo, user_id))

    def get_user_roles(self, user_id):
        db = get_db()
        sql = "SELECT r.nombre FROM roles r JOIN usuario_roles ur ON r.id = ur.rol_id WHERE ur.usuario_id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return [row['nombre'] for row in cursor.fetchall()]

    def remove_all_roles_from_user(self, user_id):
        db = get_db()
        sql = "DELETE FROM usuario_roles WHERE usuario_id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))

    def toggle_user_active_status(self, user_id, status):
        db = get_db()
        sql = 'UPDATE usuarios SET activo = ? WHERE id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (status, user_id))
        db.commit()

    def is_user_admin(self, user_id):
        db = get_db()
        sql = "SELECT 1 FROM usuario_roles ur JOIN roles r ON ur.rol_id = r.id WHERE ur.usuario_id = ? AND r.nombre = 'ADMINISTRADOR'"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return cursor.fetchone() is not None

    def get_admin_count(self):
        db = get_db()
        sql = "SELECT COUNT(ur.usuario_id) as admin_count FROM usuario_roles ur JOIN roles r ON ur.rol_id = r.id WHERE r.nombre = 'ADMINISTRADOR'"
        cursor = db.cursor()
        cursor.execute(sql)
        return cursor.fetchone()['admin_count']

    def get_user_project_count(self, user_id):
        db = get_db()
        sql = "SELECT COUNT(proyecto_id) as count FROM proyecto_usuarios WHERE usuario_id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return cursor.fetchone()['count']

    def get_user_active_connection_count(self, user_id):
        db = get_db()
        sql = "SELECT COUNT(id) as count FROM conexiones WHERE realizador_id = ? AND estado IN ('EN_PROCESO', 'REALIZADO')"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return cursor.fetchone()['count']

    def get_user_solicited_connection_count(self, user_id):
        db = get_db()
        sql = "SELECT COUNT(id) as count FROM conexiones WHERE solicitante_id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return cursor.fetchone()['count']

    def delete_user(self, user_id):
        db = get_db()
        sql = 'DELETE FROM usuarios WHERE id = ?'
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        db.commit()

    # Métodos para la autenticación y perfiles de usuario
    def get_user_by_username(self, username):
        db = get_db()
        sql = 'SELECT * FROM usuarios WHERE username = ?'
        cursor = db.cursor()
        cursor.execute(sql, (username,))
        return cursor.fetchone()

    def update_user_profile(self, user_id, nombre_completo, email):
        db = get_db()
        sql = "UPDATE usuarios SET nombre_completo = ?, email = ? WHERE id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (nombre_completo, email, user_id))
        # El commit se manejará en la ruta para agrupar operaciones

    def update_user_password(self, user_id, password_hash):
        db = get_db()
        sql = "UPDATE usuarios SET password_hash = ? WHERE id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (password_hash, user_id))
        # El commit se manejará en la ruta

    def get_notification_preferences(self, user_id):
        db = get_db()
        sql = "SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = ?"
        cursor = db.cursor()
        cursor.execute(sql, (user_id,))
        return cursor.fetchone()

    def upsert_notification_preferences(self, user_id, email_notif_estado):
        db = get_db()
        sql = "INSERT INTO preferencias_notificaciones (usuario_id, email_notif_estado) VALUES (?, ?) ON CONFLICT (usuario_id) DO UPDATE SET email_notif_estado = excluded.email_notif_estado"
        cursor = db.cursor()
        cursor.execute(sql, (user_id, email_notif_estado))
        # El commit se manejará en la ruta

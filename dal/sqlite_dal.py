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

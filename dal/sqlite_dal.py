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

    def search_conexiones_fts(self, query):
        db = get_db()
        cursor = db.cursor()
        try:
            # Sanitize for FTS by escaping double quotes, then wrap in quotes for phrase search
            # and add asterisk for prefix matching.
            term = f'"{query.replace("\"", "\"\"")}"*'
            sql = """
                SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre
                FROM conexiones_fts fts
                JOIN conexiones c ON fts.rowid = c.id
                JOIN proyectos p ON c.proyecto_id = p.id
                LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
                WHERE fts.conexiones_fts MATCH ?
                ORDER BY c.fecha_creacion DESC
            """
            cursor.execute(sql, (term,))
            return cursor.fetchall()
        finally:
            cursor.close()

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
        cursor.execute(
            "SELECT alias, nombre_perfil FROM alias_perfiles ORDER BY nombre_perfil")
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

    def get_archivo_by_name(self, conexion_id, filename):
        db = get_db()
        sql = 'SELECT id FROM archivos WHERE conexion_id = ? AND nombre_archivo = ?'
        cursor = db.cursor()
        cursor.execute(sql, (conexion_id, filename))
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
        cursor.execute(sql, (username, nombre_completo,
                       email, password_hash, activo))
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
        cursor.execute(
            sql, (username, nombre_completo, email, activo, user_id))

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

    def get_all_reports(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT r.*, u.nombre_completo as creador_nombre FROM reportes r JOIN usuarios u ON r.creador_id = u.id ORDER BY r.nombre")
        return cursor.fetchall()

    def get_report(self, reporte_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM reportes WHERE id = ?', (reporte_id,))
        return cursor.fetchone()

    def create_report(self, nombre, descripcion, creador_id, filtros, programado, frecuencia, destinatarios):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO reportes (nombre, descripcion, creador_id, filtros, programado, frecuencia, destinatarios) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nombre, descripcion, creador_id, filtros,
             programado, frecuencia, destinatarios)
        )
        new_id = cursor.lastrowid
        db.commit()
        return new_id

    def update_report(self, reporte_id, nombre, descripcion, filtros, programado, frecuencia, destinatarios):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE reportes SET nombre = ?, descripcion = ?, filtros = ?, programado = ?, frecuencia = ?, destinatarios = ? WHERE id = ?",
            (nombre, descripcion, filtros, programado,
             frecuencia, destinatarios, reporte_id)
        )
        db.commit()

    def delete_report(self, reporte_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM reportes WHERE id = ?', (reporte_id,))
        db.commit()

    def get_report_data(self, filtros, columnas):
        db = get_db()
        cursor = db.cursor()

        query_base = f"SELECT {', '.join(columnas)} FROM conexiones_view WHERE 1=1"
        params = []

        if filtros.get('proyecto_id') and filtros['proyecto_id'] != 0:
            query_base += " AND proyecto_id = ?"
            params.append(filtros['proyecto_id'])
        if filtros.get('estado'):
            query_base += " AND estado = ?"
            params.append(filtros['estado'])
        if filtros.get('realizador_id') and filtros['realizador_id'] != 0:
            query_base += " AND realizador_id = ?"
            params.append(filtros['realizador_id'])
        if filtros.get('fecha_inicio'):
            query_base += " AND date(fecha_creacion) >= ?"
            params.append(filtros['fecha_inicio'])
        if filtros.get('fecha_fin'):
            query_base += " AND date(fecha_creacion) <= ?"
            params.append(filtros['fecha_fin'])

        cursor.execute(query_base, tuple(params))
        return cursor.fetchall()

    def update_report_last_execution(self, reporte_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'UPDATE reportes SET ultima_ejecucion = CURRENT_TIMESTAMP WHERE id = ?', (reporte_id,))
        db.commit()

    def get_alias_by_name_or_alias(self, nombre_perfil, alias):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT id FROM alias_perfiles WHERE nombre_perfil = ? OR alias = ?', (nombre_perfil, alias))
        return cursor.fetchone()

    def create_alias(self, nombre_perfil, alias, norma):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO alias_perfiles (nombre_perfil, alias, norma) VALUES (?, ?, ?)',
                       (nombre_perfil, alias, norma))
        new_id = cursor.lastrowid
        db.commit()
        return new_id

    def update_alias(self, alias_id, nombre_perfil, alias, norma):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE alias_perfiles SET nombre_perfil = ?, alias = ?, norma = ? WHERE id = ?',
                       (nombre_perfil, alias, norma, alias_id))
        db.commit()

    def delete_alias(self, alias_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM alias_perfiles WHERE id = ?', (alias_id,))
        db.commit()

    def get_alias_by_id(self, alias_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT * FROM alias_perfiles WHERE id = ?', (alias_id,))
        return cursor.fetchone()

    def get_alias_by_name(self, nombre_perfil):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT * FROM alias_perfiles WHERE nombre_perfil = ?', (nombre_perfil,))
        return cursor.fetchone()

    def get_efficiency_kpis(self):
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_days
            FROM historial_estados h1
            JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id
            WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'
        """)
        avg_time_query = cursor.fetchone()
        avg_approval_time = avg_time_query['avg_days'] if avg_time_query and avg_time_query['avg_days'] is not None else 0

        cursor.execute(
            "SELECT COUNT(id) as total FROM conexiones WHERE fecha_modificacion >= date('now', '-30 days') AND estado = 'APROBADO'")
        processed_last_30d_row = cursor.fetchone()
        processed_last_30d = processed_last_30d_row['total'] if processed_last_30d_row else 0

        cursor.execute(
            "SELECT COUNT(id) as total FROM conexiones WHERE estado = 'APROBADO'")
        total_approved_row = cursor.fetchone()
        total_approved = total_approved_row['total'] if total_approved_row else 0

        cursor.execute(
            "SELECT COUNT(DISTINCT conexion_id) as total FROM historial_estados WHERE estado = 'RECHAZADO'")
        total_rejected_history_row = cursor.fetchone()
        total_rejected_history = total_rejected_history_row[
            'total'] if total_rejected_history_row else 0

        rejection_rate = (total_rejected_history / (total_approved + total_rejected_history)
                          * 100) if (total_approved + total_rejected_history) > 0 else 0

        return {
            'avg_approval_time': f"{avg_approval_time:.1f} días" if isinstance(avg_approval_time, (int, float)) else 'N/A',
            'processed_in_range': processed_last_30d,
            'rejection_rate': f"{rejection_rate:.1f}%"
        }

    def get_time_by_state(self):
        # This is a placeholder. A real implementation would query the database.
        return {'Solicitado': 8.5, 'En Proceso': 48.2, 'Realizado': 24.0}

    def get_completed_by_user(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT u.nombre_completo, COUNT(c.id) as total
            FROM conexiones c JOIN usuarios u ON c.realizador_id = u.id
            WHERE c.estado = 'APROBADO' AND c.fecha_modificacion >= date('now', '-30 days')
            GROUP BY u.id
            ORDER BY total DESC
        """)
        return cursor.fetchall()

    def get_slow_connections(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre,
                   u.nombre_completo as realizador_nombre,
                   (julianday('now') - julianday(c.fecha_modificacion)) as dias_en_proceso
            FROM conexiones c
            JOIN proyectos p ON c.proyecto_id = p.id
            LEFT JOIN usuarios u ON c.realizador_id = u.id
            WHERE c.estado = 'EN_PROCESO'
            ORDER BY dias_en_proceso DESC
            LIMIT 5
        """)
        return cursor.fetchall()

    def get_audit_logs(self, offset, per_page, filtro_usuario_id=None, filtro_accion=None):
        db = get_db()
        cursor = db.cursor()

        query = "SELECT a.*, u.nombre_completo as usuario_nombre FROM auditoria_acciones a JOIN usuarios u ON a.usuario_id = u.id WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM auditoria_acciones a JOIN usuarios u ON a.usuario_id = u.id WHERE 1=1"
        params = []

        if filtro_usuario_id:
            query += " AND a.usuario_id = ?"
            count_query += " AND a.usuario_id = ?"
            params.append(filtro_usuario_id)
        if filtro_accion:
            query += " AND a.accion = ?"
            count_query += " AND a.accion = ?"
            params.append(filtro_accion)

        query += " ORDER BY a.fecha DESC LIMIT ? OFFSET ?"

        params_count = params[:]
        params.extend([per_page, offset])

        cursor.execute(query, tuple(params))
        acciones = cursor.fetchall()

        cursor.execute(count_query, tuple(params_count))
        total_acciones = cursor.fetchone()[0]

        return acciones, total_acciones

    def get_distinct_audit_actions(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT DISTINCT accion FROM auditoria_acciones ORDER BY accion')
        return cursor.fetchall()

    def get_all_config(self):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT clave, valor FROM configuracion")
        return {row['clave']: row['valor'] for row in cursor.fetchall()}

    def update_config(self, key, value):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (?, ?) ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor", (key, value))
        db.commit()

    def user_has_access_to_project(self, user_id, proyecto_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT 1 FROM proyecto_usuarios WHERE proyecto_id = ? AND usuario_id = ?", (proyecto_id, user_id))
        return cursor.fetchone() is not None

    def get_users_for_project(self, proyecto_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT usuario_id FROM proyecto_usuarios WHERE proyecto_id = ?", (proyecto_id,))
        return {row['usuario_id'] for row in cursor.fetchall()}

    def assign_users_to_project(self, proyecto_id, user_ids):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM proyecto_usuarios WHERE proyecto_id = ?", (proyecto_id,))
        for user_id in user_ids:
            cursor.execute(
                "INSERT INTO proyecto_usuarios (proyecto_id, usuario_id) VALUES (?, ?)", (proyecto_id, int(user_id)))
        db.commit()

import time
import json
from datetime import datetime, timedelta
from flask import g, current_app
from db import get_db

_cache = {}
CACHE_TIMEOUT = 60  # Cache results for 60 seconds

def clear_dashboard_cache():
    """Clears the in-memory dashboard cache."""
    _cache.clear()

def get_dashboard_data(user_id, user_roles):
    """
    Fetches and consolidates all data required for the dashboard.
    Results are cached to improve performance.
    This version uses multiple correct queries and ensures consistent data structure.
    """
    cache_key = f"dashboard_{user_id}"
    now = time.time()

    if cache_key in _cache:
        cached_data, timestamp = _cache[cache_key]
        if now - timestamp < CACHE_TIMEOUT:
            return cached_data.copy()

    db = get_db()
    cursor = db.cursor()

    # Initialize with all keys expected by the template
    dashboard_data = {
        'kpis': {},
        'charts': {},
        'tareas': {},
        'feed_actividad': [],
        'my_summary': {},
        'my_performance': {},
        'my_performance_chart': {},
        'my_projects_summary': [],
        'user_prefs': {},
        'all_projects_for_filter': []
    }

    # --- Personal Summary (My Summary) ---
    summary = {}
    cursor.execute("SELECT COUNT(id) FROM conexiones WHERE solicitante_id = ?", (user_id,))
    summary['total_conexiones_creadas'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM conexiones WHERE solicitante_id = ? AND estado = 'EN_PROCESO'", (user_id,))
    summary['conexiones_en_proceso_solicitadas'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM conexiones WHERE solicitante_id = ? AND estado = 'APROBADO'", (user_id,))
    summary['conexiones_aprobadas_solicitadas'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM conexiones WHERE realizador_id = ? AND estado = 'EN_PROCESO'", (user_id,))
    summary['mis_tareas_en_proceso'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM conexiones WHERE realizador_id = ? AND estado = 'REALIZADO' AND fecha_modificacion >= date('now', '-30 days')", (user_id,))
    summary['mis_tareas_realizadas_ult_30d'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM conexiones WHERE aprobador_id = ? AND estado = 'APROBADO' AND fecha_modificacion >= date('now', '-30 days')", (user_id,))
    summary['aprobadas_por_mi_ult_30d'] = cursor.fetchone()[0]
    pendientes_query = "SELECT COUNT(c.id) as total FROM conexiones c JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id WHERE c.estado = 'REALIZADO' AND pu.usuario_id = ?"
    cursor.execute(pendientes_query, (user_id,))
    summary['pendientes_mi_aprobacion'] = cursor.fetchone()['total']
    summary['notificaciones_no_leidas'] = len(g.get('notifications', []))
    dashboard_data['my_summary'] = summary

    # --- Performance Metrics for Realizador/Aprobador ---
    if 'REALIZADOR' in user_roles or 'APROBADOR' in user_roles:
        avg_time_sql = "SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_days FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id WHERE h1.usuario_id = ? AND h1.estado = 'EN_PROCESO' AND h2.estado IN ('REALIZADO', 'APROBADO')"
        completed_sql = "SELECT COUNT(id) as total FROM conexiones WHERE ((realizador_id = ? AND estado = 'REALIZADO') OR (aprobador_id = ? AND estado = 'APROBADO')) AND strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now')"
        cursor.execute(avg_time_sql, (user_id,))
        avg_time_result = cursor.fetchone()
        avg_days_val = avg_time_result['avg_days'] if avg_time_result and avg_time_result['avg_days'] is not None else 0
        cursor.execute(completed_sql, (user_id, user_id))
        completed_query = cursor.fetchone()
        tasks_completed = completed_query['total'] if completed_query else 0
        dashboard_data['my_performance'] = {
            'avg_completion_time': f"{avg_days_val:.1f} días" if avg_days_val > 0 else 'N/A',
            'tasks_completed_this_month': tasks_completed
        }
        sql_chart = "SELECT date(fecha_modificacion) as completion_date, COUNT(id) as total FROM conexiones WHERE ((realizador_id = ? AND estado = 'REALIZADO') OR (aprobador_id = ? AND estado = 'APROBADO')) AND fecha_modificacion >= ? GROUP BY completion_date ORDER BY completion_date"
        params_chart = (user_id, user_id, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))
        cursor.execute(sql_chart, params_chart)
        tasks_map = {row['completion_date']: row['total'] for row in cursor.fetchall()}
        chart_data = {'labels': [], 'data': []}
        for i in range(29, -1, -1):
            date = (datetime.now() - timedelta(days=i))
            date_str = date.strftime('%Y-%m-%d')
            chart_data['labels'].append(date.strftime('%d %b'))
            chart_data['data'].append(tasks_map.get(date_str, 0))
        dashboard_data['my_performance_chart'] = chart_data

    # --- User's projects summary ---
    query_projects = "SELECT p.id, p.nombre, COUNT(c.id) AS total_conexiones, SUM(CASE WHEN c.estado = 'SOLICITADO' THEN 1 ELSE 0 END) AS solicitadas, SUM(CASE WHEN c.estado = 'EN_PROCESO' THEN 1 ELSE 0 END) AS en_proceso, SUM(CASE WHEN c.estado = 'APROBADO' THEN 1 ELSE 0 END) AS aprobadas, SUM(CASE WHEN c.estado = 'RECHAZADO' THEN 1 ELSE 0 END) AS rechazadas FROM proyectos p JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id LEFT JOIN conexiones c ON p.id = c.proyecto_id WHERE pu.usuario_id = ? GROUP BY p.id, p.nombre ORDER BY p.nombre"
    cursor.execute(query_projects, (user_id,))
    dashboard_data['my_projects_summary'] = [dict(row) for row in cursor.fetchall()]

    # --- Admin KPIs (Global Stats) ---
    if 'ADMINISTRADOR' in user_roles:
        kpi_counts_query = "SELECT SUM(CASE WHEN estado NOT IN ('APROBADO', 'RECHAZADO') THEN 1 ELSE 0 END) as total_activas, SUM(CASE WHEN date(fecha_creacion) = date('now') THEN 1 ELSE 0 END) as creadas_hoy FROM conexiones"
        avg_time_sql_admin = "SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_time FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'"
        cursor.execute(kpi_counts_query)
        kpi_counts = cursor.fetchone()
        cursor.execute(avg_time_sql_admin)
        avg_time_result_admin = cursor.fetchone()
        avg_days_admin = avg_time_result_admin['avg_time'] if avg_time_result_admin and avg_time_result_admin['avg_time'] is not None else 0
        dashboard_data['kpis'] = {
            'total_activas': kpi_counts['total_activas'] or 0,
            'creadas_hoy': kpi_counts['creadas_hoy'] or 0,
            'tiempo_aprobacion': f"{avg_days_admin:.1f} días" if avg_days_admin > 0 else "N/A"
        }
        # Placeholder for charts data to avoid template errors
        dashboard_data['charts'] = {}


    # --- Task lists ---
    tasks = {'pendientes_aprobacion': [], 'mis_asignadas': [], 'disponibles': [], 'mis_solicitudes': []}
    if 'APROBADOR' in user_roles:
        query_aprobador = "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id WHERE c.estado = 'REALIZADO' AND pu.usuario_id = ? ORDER BY c.fecha_modificacion DESC LIMIT 5"
        cursor.execute(query_aprobador, (user_id,))
        tasks['pendientes_aprobacion'] = [dict(row) for row in cursor.fetchall()]
    if 'REALIZADOR' in user_roles:
        query_realizador = "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.estado = 'EN_PROCESO' AND c.realizador_id = ? ORDER BY c.fecha_modificacion DESC LIMIT 5"
        cursor.execute(query_realizador, (user_id,))
        tasks['mis_asignadas'] = [dict(row) for row in cursor.fetchall()]
        query_disponibles = "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.estado = 'SOLICITADO' ORDER BY c.fecha_creacion DESC LIMIT 5"
        cursor.execute(query_disponibles)
        tasks['disponibles'] = [dict(row) for row in cursor.fetchall()]
    if 'SOLICITANTE' in user_roles:
        query_solicitante = "SELECT id, codigo_conexion, estado, fecha_creacion, tipo FROM conexiones WHERE solicitante_id = ? AND estado NOT IN ('APROBADO') ORDER BY fecha_creacion DESC LIMIT 5"
        cursor.execute(query_solicitante, (user_id,))
        tasks['mis_solicitudes'] = [dict(row) for row in cursor.fetchall()]
    dashboard_data['tareas'] = tasks

    # --- Activity Feed ---
    cursor.execute("""
        SELECT h.objeto_id as conexion_id, h.fecha, u.nombre_completo as usuario_nombre, c.codigo_conexion, h.accion, h.detalles
        FROM auditoria_acciones h JOIN usuarios u ON h.usuario_id = u.id
        LEFT JOIN conexiones c ON h.objeto_id = c.id AND h.tipo_objeto = 'conexiones'
        WHERE h.accion IN ('CREAR_CONEXION', 'TOMAR_CONEXION', 'MARCAR_REALIZADO_CONEXION', 'APROBAR_CONEXION', 'RECHAZAR_CONEXION', 'SUBIR_ARCHIVO', 'AGREGAR_COMENTARIO')
        ORDER BY h.fecha DESC LIMIT 10
    """)
    dashboard_data['feed_actividad'] = [dict(row) for row in cursor.fetchall()]

    # --- Other data needed by template ---
    cursor.execute('SELECT widgets_config FROM user_dashboard_preferences WHERE usuario_id = ?', (user_id,))
    user_prefs_row = cursor.fetchone()
    dashboard_data['user_prefs'] = json.loads(user_prefs_row['widgets_config']) if user_prefs_row and user_prefs_row['widgets_config'] else {}
    cursor.execute("SELECT id, nombre FROM proyectos ORDER BY nombre")
    dashboard_data['all_projects_for_filter'] = [dict(row) for row in cursor.fetchall()]

    _cache[cache_key] = (dashboard_data, now)

    cursor.close()

    return dashboard_data

"""
routes/main.py

Este archivo contiene las rutas principales y de navegación general de la aplicación,
como el dashboard, el catálogo de conexiones y la función de búsqueda.
No contiene lógica de un módulo específico (como Proyectos o Conexiones),
sino las páginas generales que unen la aplicación.
"""
import json
import os
import re
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, g, current_app, redirect,
                   url_for, request, jsonify, session, flash)
from db import get_db
from . import roles_required

main_bp = Blueprint('main', __name__)

def _get_my_summary_data(db, user_id):
    """Obtiene los datos para el widget 'Mi Resumen de Actividad'."""
    is_postgres = hasattr(db, 'cursor')

    if is_postgres:
        summary_query = """
            SELECT
                SUM(CASE WHEN solicitante_id = %s THEN 1 ELSE 0 END) as total_conexiones_creadas,
                SUM(CASE WHEN solicitante_id = %s AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as conexiones_en_proceso_solicitadas,
                SUM(CASE WHEN solicitante_id = %s AND estado = 'APROBADO' THEN 1 ELSE 0 END) as conexiones_aprobadas_solicitadas,
                SUM(CASE WHEN realizador_id = %s AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as mis_tareas_en_proceso,
                SUM(CASE WHEN realizador_id = %s AND estado = 'REALIZADO' AND fecha_modificacion >= NOW() - interval '30 days' THEN 1 ELSE 0 END) as mis_tareas_realizadas_ult_30d,
                SUM(CASE WHEN aprobador_id = %s AND estado = 'APROBADO' AND fecha_modificacion >= NOW() - interval '30 days' THEN 1 ELSE 0 END) as aprobadas_por_mi_ult_30d
            FROM conexiones
            WHERE solicitante_id = %s OR realizador_id = %s OR aprobador_id = %s
        """
        params = [user_id] * 9
        with db.cursor() as cursor:
            cursor.execute(summary_query, params)
            summary_row = cursor.fetchone()
    else:
        summary_query = """
            SELECT
                SUM(CASE WHEN solicitante_id = ? THEN 1 ELSE 0 END) as total_conexiones_creadas,
                SUM(CASE WHEN solicitante_id = ? AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as conexiones_en_proceso_solicitadas,
                SUM(CASE WHEN solicitante_id = ? AND estado = 'APROBADO' THEN 1 ELSE 0 END) as conexiones_aprobadas_solicitadas,
                SUM(CASE WHEN realizador_id = ? AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as mis_tareas_en_proceso,
                SUM(CASE WHEN realizador_id = ? AND estado = 'REALIZADO' AND fecha_modificacion >= date('now', '-30 days') THEN 1 ELSE 0 END) as mis_tareas_realizadas_ult_30d,
                SUM(CASE WHEN aprobador_id = ? AND estado = 'APROBADO' AND fecha_modificacion >= date('now', '-30 days') THEN 1 ELSE 0 END) as aprobadas_por_mi_ult_30d
            FROM conexiones
            WHERE solicitante_id = ? OR realizador_id = ? OR aprobador_id = ?
        """
        params = [user_id] * 9
        summary_row = db.execute(summary_query, params).fetchone()

    summary = dict(summary_row) if summary_row else {
        'total_conexiones_creadas': 0,
        'conexiones_en_proceso_solicitadas': 0,
        'conexiones_aprobadas_solicitadas': 0,
        'mis_tareas_en_proceso': 0,
        'mis_tareas_realizadas_ult_30d': 0,
        'aprobadas_por_mi_ult_30d': 0
    }

    pendientes_row = db.execute("""
        SELECT COUNT(c.id) as total
        FROM conexiones c
        JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id
        WHERE c.estado = 'REALIZADO' AND pu.usuario_id = ?
    """, (user_id,)).fetchone()
    summary['pendientes_mi_aprobacion'] = pendientes_row['total'] if pendientes_row else 0

    summary['notificaciones_no_leidas'] = len(g.notifications) if hasattr(g, 'notifications') else 0

    for key in summary:
        if summary[key] is None:
            summary[key] = 0

    return summary

def _get_my_performance_data(db, user_id):
    """Obtiene los datos para el widget 'Mi Rendimiento'."""
    performance = {'avg_completion_time': 'N/A', 'tasks_completed_this_month': 0}
    is_postgres = hasattr(db, 'cursor')

    if is_postgres:
        avg_time_query_sql = """
            SELECT AVG(h2.fecha - h1.fecha) as avg_time
            FROM historial_estados h1
            JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id
            WHERE h1.usuario_id = %s AND h1.estado = 'EN_PROCESO' AND h2.estado IN ('REALIZADO', 'APROBADO')
        """
        with db.cursor() as cursor:
            cursor.execute(avg_time_query_sql, (user_id,))
            avg_time_result = cursor.fetchone()
        avg_time = avg_time_result['avg_time'] if avg_time_result and avg_time_result['avg_time'] is not None else timedelta(0)
        performance['avg_completion_time'] = f"{avg_time.days + avg_time.seconds / 86400.0:.1f} días" if avg_time.total_seconds() > 0 else "N/A"

        completed_query_sql = """
            SELECT COUNT(id) as total FROM conexiones
            WHERE (realizador_id = %s AND estado = 'REALIZADO' AND TO_CHAR(fecha_modificacion, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM'))
            OR (aprobador_id = %s AND estado = 'APROBADO' AND TO_CHAR(fecha_modificacion, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM'))
        """
        with db.cursor() as cursor:
            cursor.execute(completed_query_sql, (user_id, user_id))
            completed_query = cursor.fetchone()
    else:
        avg_time_query = db.execute("""
            SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_days
            FROM historial_estados h1
            JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id
            WHERE h1.usuario_id = ? AND h1.estado = 'EN_PROCESO' AND h2.estado IN ('REALIZADO', 'APROBADO')
        """, (user_id,)).fetchone()
        avg_days = avg_time_query['avg_days'] if avg_time_query and avg_time_query['avg_days'] is not None else 0
        performance['avg_completion_time'] = f"{avg_days:.1f} días" if avg_days > 0 else "N/A"

        completed_query = db.execute("""
            SELECT COUNT(id) as total FROM conexiones
            WHERE (realizador_id = ? AND estado = 'REALIZADO' AND strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now'))
            OR (aprobador_id = ? AND estado = 'APROBADO' AND strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now'))
        """, (user_id, user_id)).fetchone()

    performance['tasks_completed_this_month'] = completed_query['total']
    return performance

def _get_my_performance_chart_data(db, user_id):
    """Obtiene los datos de rendimiento para un gráfico de los últimos 30 días."""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    is_postgres = hasattr(db, 'cursor')

    if is_postgres:
        completed_tasks_by_day_sql = """
            SELECT
                TO_CHAR(fecha_modificacion, 'YYYY-MM-DD') as completion_date,
                COUNT(id) as total
            FROM conexiones
            WHERE
                ((realizador_id = %s AND estado = 'REALIZADO') OR (aprobador_id = %s AND estado = 'APROBADO'))
                AND fecha_modificacion >= %s
            GROUP BY completion_date
            ORDER BY completion_date
        """
        params = (user_id, user_id, thirty_days_ago)
        with db.cursor() as cursor:
            cursor.execute(completed_tasks_by_day_sql, params)
            completed_tasks_by_day = cursor.fetchall()
    else:
        completed_tasks_by_day = db.execute("""
            SELECT
                strftime('%Y-%m-%d', fecha_modificacion) as completion_date,
                COUNT(id) as total
            FROM conexiones
            WHERE
                ((realizador_id = ? AND estado = 'REALIZADO') OR (aprobador_id = ? AND estado = 'APROBADO'))
                AND fecha_modificacion >= ?
            GROUP BY completion_date
            ORDER BY completion_date
        """, (user_id, user_id, thirty_days_ago.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()

    tasks_map = {row['completion_date']: row['total'] for row in completed_tasks_by_day}

    chart_data = {'labels': [], 'data': []}
    for i in range(30):
        date = (datetime.now() - timedelta(days=i))
        date_str = date.strftime('%Y-%m-%d')
        chart_data['labels'].insert(0, date.strftime('%d %b'))
        chart_data['data'].insert(0, tasks_map.get(date_str, 0))

    return chart_data

def _get_my_projects_summary(db, user_id):
    """Obtiene el resumen de proyectos para el usuario."""
    my_projects_summary = db.execute("""
        SELECT p.id, p.nombre,
               COUNT(c.id) AS total_conexiones,
               SUM(CASE WHEN c.estado = 'SOLICITADO' THEN 1 ELSE 0 END) AS solicitadas,
               SUM(CASE WHEN c.estado = 'EN_PROCESO' THEN 1 ELSE 0 END) AS en_proceso,
               SUM(CASE WHEN c.estado = 'APROBADO' THEN 1 ELSE 0 END) AS aprobadas,
               SUM(CASE WHEN c.estado = 'RECHAZADO' THEN 1 ELSE 0 END) AS rechazadas
        FROM proyectos p
        JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
        LEFT JOIN conexiones c ON p.id = c.proyecto_id
        WHERE pu.usuario_id = ?
        GROUP BY p.id, p.nombre
        ORDER BY p.nombre
    """, (user_id,)).fetchall()
    return [dict(row) for row in my_projects_summary]

def _get_admin_dashboard_data(db, start_date, end_date):
    """Obtiene los KPIs y datos de gráficos para el panel de administrador."""
    admin_data = {'kpis': {}, 'charts': {}}
    is_postgres = hasattr(db, 'cursor')

    if is_postgres:
        kpi_counts_query = """
            SELECT
                SUM(CASE WHEN estado NOT IN ('APROBADO', 'RECHAZADO') THEN 1 ELSE 0 END) as total_activas,
                SUM(CASE WHEN DATE(fecha_creacion) = CURRENT_DATE THEN 1 ELSE 0 END) as creadas_hoy
            FROM conexiones
        """
        with db.cursor() as cursor:
            cursor.execute(kpi_counts_query)
            kpi_counts = cursor.fetchone()

        avg_time_query_sql = """
            SELECT AVG(h2.fecha - h1.fecha) as avg_time
            FROM historial_estados h1
            JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id
            WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'
        """
        with db.cursor() as cursor:
            cursor.execute(avg_time_query_sql)
            avg_time_result = cursor.fetchone()
        avg_time = avg_time_result['avg_time'] if avg_time_result and avg_time_result['avg_time'] is not None else timedelta(0)
        admin_data['kpis']['tiempo_aprobacion'] = f"{avg_time.days + avg_time.seconds / 86400.0:.1f} días"

        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(id) as total FROM conexiones WHERE estado = 'APROBADO' AND fecha_creacion BETWEEN %s AND %s", (start_date, end_date))
            total_aprobadas_en_rango_row = cursor.fetchone()
            cursor.execute("SELECT COUNT(DISTINCT conexion_id) as total FROM historial_estados WHERE estado = 'RECHAZADO' AND fecha BETWEEN %s AND %s", (start_date, end_date))
            total_rechazadas_en_rango_row = cursor.fetchone()
            cursor.execute("SELECT estado, COUNT(id) as total FROM conexiones WHERE fecha_creacion BETWEEN %s AND %s GROUP BY estado", (start_date, end_date))
            estados_data = cursor.fetchall()
            cursor.execute("SELECT TO_CHAR(fecha_creacion, 'YYYY-MM') as mes, COUNT(id) as total FROM conexiones WHERE fecha_creacion BETWEEN %s AND %s GROUP BY mes ORDER BY mes", (start_date, end_date))
            conexiones_por_mes_data = cursor.fetchall()
            cursor.execute("SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.solicitante_id = u.id WHERE c.fecha_creacion BETWEEN %s AND %s GROUP BY u.id, u.nombre_completo ORDER BY total DESC LIMIT 5", (start_date, end_date))
            admin_data['charts']['top_solicitantes'] = cursor.fetchall()
            cursor.execute("SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.realizador_id = u.id WHERE c.realizador_id IS NOT NULL AND c.fecha_modificacion BETWEEN %s AND %s AND c.estado = 'APROBADO' GROUP BY u.id, u.nombre_completo ORDER BY total DESC LIMIT 5", (start_date, end_date))
            admin_data['charts']['top_realizadores'] = cursor.fetchall()
    else:
        kpi_counts_query = """
            SELECT
                SUM(CASE WHEN estado NOT IN ('APROBADO', 'RECHAZADO') THEN 1 ELSE 0 END) as total_activas,
                SUM(CASE WHEN DATE(fecha_creacion) = DATE('now') THEN 1 ELSE 0 END) as creadas_hoy
            FROM conexiones
        """
        kpi_counts = db.execute(kpi_counts_query).fetchone()

        avg_time_query = db.execute("""
            SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_days
            FROM historial_estados h1
            JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id
            WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'
        """).fetchone()
        avg_days = avg_time_query['avg_days'] if avg_time_query and avg_time_query['avg_days'] is not None else 0
        admin_data['kpis']['tiempo_aprobacion'] = f"{avg_days:.1f} días"

        total_aprobadas_en_rango_row = db.execute("SELECT COUNT(id) as total FROM conexiones WHERE estado = 'APROBADO' AND fecha_creacion BETWEEN ? AND ?", (start_date, end_date)).fetchone()
        total_rechazadas_en_rango_row = db.execute("SELECT COUNT(DISTINCT conexion_id) as total FROM historial_estados WHERE estado = 'RECHAZADO' AND fecha BETWEEN ? AND ?", (start_date, end_date)).fetchone()
        estados_data = db.execute("SELECT estado, COUNT(id) as total FROM conexiones WHERE fecha_creacion BETWEEN ? AND ? GROUP BY estado", (start_date, end_date)).fetchall()
        conexiones_por_mes_data = db.execute("SELECT strftime('%Y-%m', fecha_creacion) as mes, COUNT(id) as total FROM conexiones WHERE fecha_creacion BETWEEN ? AND ? GROUP BY mes ORDER BY mes", (start_date, end_date)).fetchall()
        admin_data['charts']['top_solicitantes'] = db.execute("SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.solicitante_id = u.id WHERE c.fecha_creacion BETWEEN ? AND ? GROUP BY u.id ORDER BY total DESC LIMIT 5", (start_date, end_date)).fetchall()
        admin_data['charts']['top_realizadores'] = db.execute("SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.realizador_id = u.id WHERE c.realizador_id IS NOT NULL AND c.fecha_modificacion BETWEEN ? AND ? AND c.estado = 'APROBADO' GROUP BY u.id ORDER BY total DESC LIMIT 5", (start_date, end_date)).fetchall()

    admin_data['kpis']['total_activas'] = kpi_counts['total_activas'] or 0
    admin_data['kpis']['creadas_hoy'] = kpi_counts['creadas_hoy'] or 0
    total_aprobadas_en_rango = total_aprobadas_en_rango_row['total'] if total_aprobadas_en_rango_row else 0
    total_rechazadas_en_rango = total_rechazadas_en_rango_row['total'] if total_rechazadas_en_rango_row else 0
    total_procesadas_en_rango = total_aprobadas_en_rango + total_rechazadas_en_rango
    tasa_rechazo = (total_rechazadas_en_rango / total_procesadas_en_rango * 100) if total_procesadas_en_rango > 0 else 0
    admin_data['kpis']['tasa_rechazo'] = f"{tasa_rechazo:.1f}%"
    admin_data['charts']['estados'] = {row['estado']: row['total'] for row in estados_data}
    admin_data['charts']['conexiones_mes'] = [{'mes': row['mes'], 'total': row['total']} for row in conexiones_por_mes_data]

    return admin_data

def _get_user_tasks(db, user_id, user_roles):
    """Obtiene las listas de tareas para el usuario según sus roles."""
    tasks = {
        'pendientes_aprobacion': [],
        'mis_asignadas': [],
        'disponibles': [],
        'mis_solicitudes': []
    }
    if 'APROBADOR' in user_roles:
        tasks['pendientes_aprobacion'] = db.execute("""
            SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id
            FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id
            WHERE c.estado = 'REALIZADO' AND pu.usuario_id = ? ORDER BY c.fecha_modificacion DESC LIMIT 5
        """, (user_id,)).fetchall()
    if 'REALIZADOR' in user_roles:
        tasks['mis_asignadas'] = db.execute("SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.estado = 'EN_PROCESO' AND c.realizador_id = ? ORDER BY c.fecha_modificacion DESC LIMIT 5", (user_id,)).fetchall()
        tasks['disponibles'] = db.execute("SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.estado = 'SOLICITADO' ORDER BY c.fecha_creacion DESC LIMIT 5").fetchall()
    if 'SOLICITANTE' in user_roles:
        tasks['mis_solicitudes'] = db.execute("SELECT id, codigo_conexion, estado, fecha_creacion, tipo FROM conexiones WHERE solicitante_id = ? AND estado NOT IN ('APROBADO') ORDER BY fecha_creacion DESC LIMIT 5", (user_id,)).fetchall()
    return tasks

def _get_activity_feed(db):
    """Obtiene la actividad reciente del sistema."""
    return db.execute("""
        SELECT h.objeto_id as conexion_id, h.fecha, u.nombre_completo as usuario_nombre, c.codigo_conexion, h.accion, h.detalles
        FROM auditoria_acciones h
        JOIN usuarios u ON h.usuario_id = u.id
        LEFT JOIN conexiones c ON h.objeto_id = c.id AND h.tipo_objeto = 'conexiones'
        WHERE h.accion IN ('CREAR_CONEXION', 'TOMAR_CONEXION', 'MARCAR_REALIZADO_CONEXION', 'APROBAR_CONEXION', 'RECHAZAR_CONEXION', 'SUBIR_ARCHIVO', 'AGREGAR_COMENTARIO')
        ORDER BY h.fecha DESC LIMIT 10
    """).fetchall()

@main_bp.route('/')
def index():
    """
    Ruta raíz de la aplicación ('/').
    Redirige automáticamente al dashboard principal para usuarios ya autenticados.
    Esto proporciona una experiencia de usuario fluida al entrar al sitio.
    """
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def dashboard():
    """
    Muestra el dashboard principal. El contenido se personaliza según los roles
    del usuario actual, mostrando estadísticas para administradores y listas de
    tareas para otros roles operativos.
    """
    db = get_db()
    user_id = g.user['id']
    user_roles = session.get('user_roles', [])

    dashboard_data = {
        'kpis': {
            'total_activas': 0, 'tiempo_aprobacion': 'N/A', 'creadas_hoy': 0, 'tasa_rechazo': '0.0%'
        },
        'charts': {
            'estados': {}, 'conexiones_mes': [], 'top_solicitantes': [], 'top_realizadores': []
        },
        'tareas': {
            'pendientes_aprobacion': [], 'mis_asignadas': [], 'disponibles': [], 'mis_solicitudes': []
        },
        'feed_actividad': [],
        'my_summary': {},
        'my_performance': {},
        'my_performance_chart': {},
        'my_projects_summary': [],
        'user_prefs': {}
    }

    date_start_str = request.args.get('date_start', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_end_str = request.args.get('date_end', datetime.now().strftime('%Y-%m-%d'))
    filters = {'start': date_start_str, 'end': date_end_str}
    start_date_obj = datetime.strptime(date_start_str, '%Y-%m-%d')
    end_date_obj = datetime.strptime(date_end_str, '%Y-%m-%d') + timedelta(days=1)

    dashboard_data['my_summary'] = _get_my_summary_data(db, user_id)

    if 'REALIZADOR' in user_roles or 'APROBADOR' in user_roles:
        dashboard_data['my_performance'] = _get_my_performance_data(db, user_id)
        dashboard_data['my_performance_chart'] = _get_my_performance_chart_data(db, user_id)

    if 'SOLICITANTE' in user_roles or 'REALIZADOR' in user_roles or 'APROBADOR' in user_roles:
        dashboard_data['my_projects_summary'] = _get_my_projects_summary(db, user_id)

    user_prefs_row = db.execute('SELECT widgets_config FROM user_dashboard_preferences WHERE usuario_id = ?', (user_id,)).fetchone()
    dashboard_data['user_prefs'] = json.loads(user_prefs_row['widgets_config']) if user_prefs_row and user_prefs_row['widgets_config'] else {}

    if 'ADMINISTRADOR' in user_roles:
        try:
            admin_data = _get_admin_dashboard_data(db, start_date_obj.strftime('%Y-%m-%d %H:%M:%S'), end_date_obj.strftime('%Y-%m-%d %H:%M:%S'))
            dashboard_data['kpis'] = admin_data['kpis']
            dashboard_data['charts'] = admin_data['charts']
        except Exception as e:
            current_app.logger.error(f"Error al cargar estadísticas del dashboard de admin: {e}", exc_info=True)
            flash("Ocurrió un error al cargar las estadísticas del dashboard. El administrador ha sido notificado.", "danger")

    dashboard_data['tareas'] = _get_user_tasks(db, user_id, user_roles)
    dashboard_data['feed_actividad'] = _get_activity_feed(db)

    all_projects_for_filter = db.execute("SELECT id, nombre FROM proyectos ORDER BY nombre").fetchall()

    return render_template('dashboard.html', 
                           dashboard_data=dashboard_data, 
                           titulo="Dashboard", 
                           filters=filters,
                           all_projects_for_filter=all_projects_for_filter
                           )

@main_bp.route('/catalogo')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def catalogo():
    """
    Muestra el catálogo de tipologías de conexión para que el usuario pueda
    iniciar una nueva solicitud.
    """
    db = get_db()
    json_path = os.path.join(current_app.root_path, 'conexiones.json')

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
    except FileNotFoundError:
        current_app.logger.error(f"No se encontró el archivo de configuración 'conexiones.json'.")
        flash("Error crítico: No se pudo cargar la configuración de conexiones.", "danger")
        return redirect(url_for('main.dashboard'))
    except json.JSONDecodeError:
        current_app.logger.error(f"Error crítico: El archivo de configuración de conexiones está corrupto.", exc_info=True)
        flash("Error crítico: El archivo de configuración de conexiones está corrupto.", "danger")
        return redirect(url_for('main.dashboard'))

    user_roles = session.get('user_roles', [])
    if 'ADMINISTRADOR' in user_roles:
        proyectos = db.execute("SELECT id, nombre FROM proyectos ORDER BY nombre").fetchall()
    else:
        proyectos = db.execute("""
            SELECT p.id, p.nombre FROM proyectos p
            JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
            WHERE pu.usuario_id = ? ORDER BY p.nombre
        """, (g.user['id'],)).fetchall()

    preselect_project_id = request.args.get('preselect_project_id', type=int)

    return render_template('catalogo.html', estructura=estructura, proyectos=proyectos, preselect_project_id=preselect_project_id, titulo="Catálogo")

import sqlite3

@main_bp.route('/buscar')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def buscar():
    """
    Realiza una búsqueda de texto completo en las conexiones, compatible con SQLite y PostgreSQL.
    """
    query = request.args.get('q', '')
    resultados = []
    if query:
        db = get_db()
        is_postgres = hasattr(db, 'cursor')

        sanitized_query = re.sub(r'[\'\"()\[\]{}*?^:.]', ' ', query)
        words = sanitized_query.split()

        if not words:
            resultados = []
        else:
            fts_query = " & ".join(f'{word}:*' for word in words)
            sql = """
                SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre,
                        ts_rank(c.fts_document, to_tsquery('simple', %s)) as rank
                FROM conexiones c
                JOIN proyectos p ON c.proyecto_id = p.id
                LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
                WHERE c.fts_document @@ to_tsquery('simple', %s)
                ORDER BY rank DESC
            """
            params = (fts_query, fts_query)
            with db.cursor() as cursor:
                cursor.execute(sql, params)
                resultados = cursor.fetchall()

    return render_template('buscar.html', resultados=resultados, query=query, titulo=f"Resultados para '{query}'")
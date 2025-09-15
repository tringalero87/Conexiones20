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
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"

    if is_testing:
        date_func_30_days = "datetime('now', '-30 days')"
    else:
        date_func_30_days = "NOW() - interval '30 days'"

    summary_query = f"""
        SELECT
            SUM(CASE WHEN solicitante_id = {p} THEN 1 ELSE 0 END) as total_conexiones_creadas,
            SUM(CASE WHEN solicitante_id = {p} AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as conexiones_en_proceso_solicitadas,
            SUM(CASE WHEN solicitante_id = {p} AND estado = 'APROBADO' THEN 1 ELSE 0 END) as conexiones_aprobadas_solicitadas,
            SUM(CASE WHEN realizador_id = {p} AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END) as mis_tareas_en_proceso,
            SUM(CASE WHEN realizador_id = {p} AND estado = 'REALIZADO' AND fecha_modificacion >= {date_func_30_days} THEN 1 ELSE 0 END) as mis_tareas_realizadas_ult_30d,
            SUM(CASE WHEN aprobador_id = {p} AND estado = 'APROBADO' AND fecha_modificacion >= {date_func_30_days} THEN 1 ELSE 0 END) as aprobadas_por_mi_ult_30d
        FROM conexiones
        WHERE solicitante_id = {p} OR realizador_id = {p} OR aprobador_id = {p}
    """
    params = [user_id] * 9
    cursor = db.cursor()
    cursor.execute(summary_query, params)
    summary_row = cursor.fetchone()

    summary = dict(summary_row) if summary_row else {
        'total_conexiones_creadas': 0,
        'conexiones_en_proceso_solicitadas': 0,
        'conexiones_aprobadas_solicitadas': 0,
        'mis_tareas_en_proceso': 0,
        'mis_tareas_realizadas_ult_30d': 0,
        'aprobadas_por_mi_ult_30d': 0
    }

    pendientes_query = f"""
        SELECT COUNT(c.id) as total
        FROM conexiones c
        JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id
        WHERE c.estado = 'REALIZADO' AND pu.usuario_id = {p}
    """
    cursor.execute(pendientes_query, (user_id,))
    pendientes_row = cursor.fetchone()
    summary['pendientes_mi_aprobacion'] = pendientes_row['total'] if pendientes_row else 0
    cursor.close()

    summary['notificaciones_no_leidas'] = len(g.notifications) if hasattr(g, 'notifications') else 0

    for key in summary:
        if summary[key] is None:
            summary[key] = 0

    return summary

def _get_my_performance_data(db, user_id):
    """Obtiene los datos para el widget 'Mi Rendimiento'."""
    performance = {'avg_completion_time': 'N/A', 'tasks_completed_this_month': 0}
    is_testing = current_app.config.get('TESTING', False)

    if is_testing:
        avg_time_query_sql = "SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_time FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id WHERE h1.usuario_id = ? AND h1.estado = 'EN_PROCESO' AND h2.estado IN ('REALIZADO', 'APROBADO')"
        completed_query_sql = "SELECT COUNT(id) as total FROM conexiones WHERE (realizador_id = ? AND estado = 'REALIZADO' AND strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now')) OR (aprobador_id = ? AND estado = 'APROBADO' AND strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now'))"
    else:
        avg_time_query_sql = "SELECT AVG(h2.fecha - h1.fecha) as avg_time FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id WHERE h1.usuario_id = %s AND h1.estado = 'EN_PROCESO' AND h2.estado IN ('REALIZADO', 'APROBADO')"
        completed_query_sql = "SELECT COUNT(id) as total FROM conexiones WHERE (realizador_id = %s AND estado = 'REALIZADO' AND TO_CHAR(fecha_modificacion, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')) OR (aprobador_id = %s AND estado = 'APROBADO' AND TO_CHAR(fecha_modificacion, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM'))"

    cursor = db.cursor()
    cursor.execute(avg_time_query_sql, (user_id,))
    avg_time_result = cursor.fetchone()

    if avg_time_result and avg_time_result['avg_time'] is not None:
        if is_testing:
            avg_days = avg_time_result['avg_time']
        else:
            avg_time = avg_time_result['avg_time']
            avg_days = avg_time.days + avg_time.seconds / 86400.0
        performance['avg_completion_time'] = f"{avg_days:.1f} días" if avg_days > 0 else "N/A"
    else:
        performance['avg_completion_time'] = "N/A"

    cursor.execute(completed_query_sql, (user_id, user_id))
    completed_query = cursor.fetchone()
    cursor.close()

    performance['tasks_completed_this_month'] = completed_query['total'] if completed_query else 0
    return performance

def _get_my_performance_chart_data(db, user_id):
    """Obtiene los datos de rendimiento para un gráfico de los últimos 30 días."""
    is_testing = current_app.config.get('TESTING', False)
    thirty_days_ago = datetime.now() - timedelta(days=30)

    if is_testing:
        date_format_sql = "date(fecha_modificacion)"
        completed_tasks_by_day_sql = f"SELECT {date_format_sql} as completion_date, COUNT(id) as total FROM conexiones WHERE ((realizador_id = ? AND estado = 'REALIZADO') OR (aprobador_id = ? AND estado = 'APROBADO')) AND fecha_modificacion >= ? GROUP BY completion_date ORDER BY completion_date"
        params = (user_id, user_id, thirty_days_ago.strftime('%Y-%m-%d %H:%M:%S'))
    else:
        date_format_sql = "TO_CHAR(fecha_modificacion, 'YYYY-MM-DD')"
        completed_tasks_by_day_sql = f"SELECT {date_format_sql} as completion_date, COUNT(id) as total FROM conexiones WHERE ((realizador_id = %s AND estado = 'REALIZADO') OR (aprobador_id = %s AND estado = 'APROBADO')) AND fecha_modificacion >= %s GROUP BY completion_date ORDER BY completion_date"
        params = (user_id, user_id, thirty_days_ago)

    cursor = db.cursor()
    cursor.execute(completed_tasks_by_day_sql, params)
    completed_tasks_by_day = cursor.fetchall()
    cursor.close()

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
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"
    query = f"""
        SELECT p.id, p.nombre,
               COUNT(c.id) AS total_conexiones,
               SUM(CASE WHEN c.estado = 'SOLICITADO' THEN 1 ELSE 0 END) AS solicitadas,
               SUM(CASE WHEN c.estado = 'EN_PROCESO' THEN 1 ELSE 0 END) AS en_proceso,
               SUM(CASE WHEN c.estado = 'APROBADO' THEN 1 ELSE 0 END) AS aprobadas,
               SUM(CASE WHEN c.estado = 'RECHAZADO' THEN 1 ELSE 0 END) AS rechazadas
        FROM proyectos p
        JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
        LEFT JOIN conexiones c ON p.id = c.proyecto_id
        WHERE pu.usuario_id = {p}
        GROUP BY p.id, p.nombre
        ORDER BY p.nombre
    """
    cursor = db.cursor()
    cursor.execute(query, (user_id,))
    my_projects_summary = cursor.fetchall()
    cursor.close()
    return [dict(row) for row in my_projects_summary]

def _get_admin_dashboard_data(db, start_date, end_date):
    """Obtiene los KPIs y datos de gráficos para el panel de administrador."""
    admin_data = {'kpis': {}, 'charts': {}}
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"

    cursor = db.cursor()

    kpi_counts_query = "SELECT SUM(CASE WHEN estado NOT IN ('APROBADO', 'RECHAZADO') THEN 1 ELSE 0 END) as total_activas, SUM(CASE WHEN DATE(fecha_creacion) = {} THEN 1 ELSE 0 END) as creadas_hoy FROM conexiones".format("date('now')" if is_testing else "CURRENT_DATE")
    cursor.execute(kpi_counts_query)
    kpi_counts = cursor.fetchone()

    if is_testing:
        avg_time_query_sql = "SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_time FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'"
    else:
        avg_time_query_sql = "SELECT AVG(h2.fecha - h1.fecha) as avg_time FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'"
    cursor.execute(avg_time_query_sql)
    avg_time_result = cursor.fetchone()

    if is_testing:
        avg_days = avg_time_result['avg_time'] if avg_time_result and avg_time_result['avg_time'] is not None else 0
        admin_data['kpis']['tiempo_aprobacion'] = f"{avg_days:.1f} días"
    else:
        avg_time = avg_time_result['avg_time'] if avg_time_result and avg_time_result['avg_time'] is not None else timedelta(0)
        admin_data['kpis']['tiempo_aprobacion'] = f"{avg_time.days + avg_time.seconds / 86400.0:.1f} días" if avg_time.total_seconds() > 0 else "N/A"

    cursor.execute(f"SELECT COUNT(id) as total FROM conexiones WHERE estado = 'APROBADO' AND fecha_creacion BETWEEN {p} AND {p}", (start_date, end_date))
    total_aprobadas_en_rango_row = cursor.fetchone()
    cursor.execute(f"SELECT COUNT(DISTINCT conexion_id) as total FROM historial_estados WHERE estado = 'RECHAZADO' AND fecha BETWEEN {p} AND {p}", (start_date, end_date))
    total_rechazadas_en_rango_row = cursor.fetchone()
    cursor.execute(f"SELECT estado, COUNT(id) as total FROM conexiones WHERE fecha_creacion BETWEEN {p} AND {p} GROUP BY estado", (start_date, end_date))
    estados_data = cursor.fetchall()

    date_format_sql = "strftime('%Y-%m', fecha_creacion)" if is_testing else "TO_CHAR(fecha_creacion, 'YYYY-MM')"
    cursor.execute(f"SELECT {date_format_sql} as mes, COUNT(id) as total FROM conexiones WHERE fecha_creacion BETWEEN {p} AND {p} GROUP BY mes ORDER BY mes", (start_date, end_date))
    conexiones_por_mes_data = cursor.fetchall()

    cursor.execute(f"SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.solicitante_id = u.id WHERE c.fecha_creacion BETWEEN {p} AND {p} GROUP BY u.id, u.nombre_completo ORDER BY total DESC LIMIT 5", (start_date, end_date))
    admin_data['charts']['top_solicitantes'] = cursor.fetchall()
    cursor.execute(f"SELECT u.nombre_completo, COUNT(c.id) as total FROM conexiones c JOIN usuarios u ON c.realizador_id = u.id WHERE c.realizador_id IS NOT NULL AND c.fecha_modificacion BETWEEN {p} AND {p} AND c.estado = 'APROBADO' GROUP BY u.id, u.nombre_completo ORDER BY total DESC LIMIT 5", (start_date, end_date))
    admin_data['charts']['top_realizadores'] = cursor.fetchall()
    cursor.close()

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
    tasks = {'pendientes_aprobacion': [], 'mis_asignadas': [], 'disponibles': [], 'mis_solicitudes': []}
    p = "?" if current_app.config.get('TESTING') else "%s"

    cursor = db.cursor()
    if 'APROBADOR' in user_roles:
        query = f"SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id WHERE c.estado = 'REALIZADO' AND pu.usuario_id = {p} ORDER BY c.fecha_modificacion DESC LIMIT 5"
        cursor.execute(query, (user_id,))
        tasks['pendientes_aprobacion'] = cursor.fetchall()
    if 'REALIZADOR' in user_roles:
        query = f"SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.estado = 'EN_PROCESO' AND c.realizador_id = {p} ORDER BY c.fecha_modificacion DESC LIMIT 5"
        cursor.execute(query, (user_id,))
        tasks['mis_asignadas'] = cursor.fetchall()

        query_disponibles = "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON c.proyecto_id = p.id WHERE c.estado = 'SOLICITADO' ORDER BY c.fecha_creacion DESC LIMIT 5"
        cursor.execute(query_disponibles)
        tasks['disponibles'] = cursor.fetchall()
    if 'SOLICITANTE' in user_roles:
        query = f"SELECT id, codigo_conexion, estado, fecha_creacion, tipo FROM conexiones WHERE solicitante_id = {p} AND estado NOT IN ('APROBADO') ORDER BY fecha_creacion DESC LIMIT 5"
        cursor.execute(query, (user_id,))
        tasks['mis_solicitudes'] = cursor.fetchall()
    cursor.close()
    return tasks

def _get_activity_feed(db):
    """Obtiene la actividad reciente del sistema."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT h.objeto_id as conexion_id, h.fecha, u.nombre_completo as usuario_nombre, c.codigo_conexion, h.accion, h.detalles
        FROM auditoria_acciones h
        JOIN usuarios u ON h.usuario_id = u.id
        LEFT JOIN conexiones c ON h.objeto_id = c.id AND h.tipo_objeto = 'conexiones'
        WHERE h.accion IN ('CREAR_CONEXION', 'TOMAR_CONEXION', 'MARCAR_REALIZADO_CONEXION', 'APROBAR_CONEXION', 'RECHAZAR_CONEXION', 'SUBIR_ARCHIVO', 'AGREGAR_COMENTARIO')
        ORDER BY h.fecha DESC LIMIT 10
    """)
    feed = cursor.fetchall()
    cursor.close()
    return feed

@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def dashboard():
    db = get_db()
    user_id = g.user['id']
    user_roles = session.get('user_roles', [])
    is_testing = current_app.config.get('TESTING', False)
    p = "?" if is_testing else "%s"

    dashboard_data = {'kpis': {}, 'charts': {}, 'tareas': {}, 'feed_actividad': [], 'my_summary': {}, 'my_performance': {}, 'my_performance_chart': {}, 'my_projects_summary': [], 'user_prefs': {}}

    date_start_str = request.args.get('date_start', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_end_str = request.args.get('date_end', datetime.now().strftime('%Y-%m-%d'))
    filters = {'start': date_start_str, 'end': date_end_str}
    start_date_obj = datetime.strptime(date_start_str, '%Y-%m-%d')
    end_date_obj = datetime.strptime(date_end_str, '%Y-%m-%d') + timedelta(days=1)

    dashboard_data['my_summary'] = _get_my_summary_data(db, user_id)

    if 'REALIZADOR' in user_roles or 'APROBADOR' in user_roles:
        dashboard_data['my_performance'] = _get_my_performance_data(db, user_id)
        dashboard_data['my_performance_chart'] = _get_my_performance_chart_data(db, user_id)

    dashboard_data['my_projects_summary'] = _get_my_projects_summary(db, user_id)

    cursor = db.cursor()
    cursor.execute(f'SELECT widgets_config FROM user_dashboard_preferences WHERE usuario_id = {p}', (user_id,))
    user_prefs_row = cursor.fetchone()
    cursor.close()
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

    cursor = db.cursor()
    cursor.execute("SELECT id, nombre FROM proyectos ORDER BY nombre")
    all_projects_for_filter = cursor.fetchall()
    cursor.close()

    return render_template('dashboard.html', dashboard_data=dashboard_data, titulo="Dashboard", filters=filters, all_projects_for_filter=all_projects_for_filter)

@main_bp.route('/catalogo')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def catalogo():
    db = get_db()
    json_path = os.path.join(current_app.root_path, 'conexiones.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(f"Error crítico al cargar 'conexiones.json': {e}", exc_info=True)
        flash("Error crítico: No se pudo cargar la configuración de conexiones.", "danger")
        return redirect(url_for('main.dashboard'))

    p = "?" if current_app.config.get('TESTING') else "%s"
    user_roles = session.get('user_roles', [])
    cursor = db.cursor()
    if 'ADMINISTRADOR' in user_roles:
        cursor.execute("SELECT id, nombre FROM proyectos ORDER BY nombre")
    else:
        cursor.execute(f"SELECT p.id, p.nombre FROM proyectos p JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id WHERE pu.usuario_id = {p} ORDER BY p.nombre", (g.user['id'],))
    proyectos = cursor.fetchall()
    cursor.close()

    preselect_project_id = request.args.get('preselect_project_id', type=int)
    return render_template('catalogo.html', estructura=estructura, proyectos=proyectos, preselect_project_id=preselect_project_id, titulo="Catálogo")

@main_bp.route('/buscar')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def buscar():
    query = request.args.get('q', '')
    resultados = []
    db = get_db()
    is_testing = current_app.config.get('TESTING', False)

    if query:
        sanitized_query = re.sub(r'[\\\'\"()\[\]{}*?^:.]', ' ', query).strip()
        words = sanitized_query.split()

        if words:
            if is_testing:
                # Fallback simple para SQLite usado en tests
                p = "?"
                # Construir una consulta LIKE para cada palabra
                like_clauses = " AND ".join([f"(c.descripcion LIKE {p} OR c.codigo_conexion LIKE {p})" for _ in words])
                params = [f'%{word}%' for word in words] * 2 # Duplicar para ambas columnas

                sql = f"""
                    SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre
                    FROM conexiones c
                    JOIN proyectos p ON c.proyecto_id = p.id
                    LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
                    WHERE {like_clauses}
                    ORDER BY c.fecha_creacion DESC
                """
                cursor = db.cursor()
                cursor.execute(sql, params)
                resultados = cursor.fetchall()
                cursor.close()

            else:
                # Búsqueda FTS mejorada para PostgreSQL
                # Usa plainto_tsquery para manejar mejor el input del usuario y el operador OR ('|')
                fts_query = " | ".join(words)
                sql = """
                    SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre,
                           ts_rank(c.fts_document, plainto_tsquery('simple', %s)) as rank
                    FROM conexiones c
                    JOIN proyectos p ON c.proyecto_id = p.id
                    LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
                    WHERE c.fts_document @@ plainto_tsquery('simple', %s)
                    ORDER BY rank DESC
                """
                cursor = db.cursor()
                cursor.execute(sql, (fts_query, fts_query))
                resultados = cursor.fetchall()
                cursor.close()

    return render_template('buscar.html', resultados=resultados, query=query, titulo=f"Resultados para '{query}'")
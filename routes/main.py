import json
import os
import re
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, g, current_app, redirect,
                   url_for, request, session, flash)
from db import get_db
from . import roles_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def dashboard():
    db = get_db()
    user_id = g.user['id']
    user_roles = session.get('user_roles', [])

    dashboard_data = {
        'kpis': {},
        'charts': {},
        'tareas': {},
        'feed_actividad': [],
        'my_summary': {},
        'my_performance': {},
        'my_performance_chart': {},
        'my_projects_summary': [],
        'user_prefs': {}}

    date_start_str = request.args.get(
        'date_start', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_end_str = request.args.get(
        'date_end', datetime.now().strftime('%Y-%m-%d'))
    filters = {'start': date_start_str, 'end': date_end_str}

    summary_query = """
        SELECT
            SUM(CASE WHEN solicitante_id = ? THEN 1 ELSE 0 END) as total_conexiones_creadas,
            SUM(CASE WHEN solicitante_id = ? AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END)
                as conexiones_en_proceso_solicitadas,
            SUM(CASE WHEN solicitante_id = ? AND estado = 'APROBADO' THEN 1 ELSE 0 END)
                as conexiones_aprobadas_solicitadas,
            SUM(CASE WHEN realizador_id = ? AND estado = 'EN_PROCESO' THEN 1 ELSE 0 END)
                as mis_tareas_en_proceso,
            SUM(CASE WHEN realizador_id = ? AND estado = 'REALIZADO'
                AND fecha_modificacion >= date('now', '-30 days') THEN 1 ELSE 0 END)
                as mis_tareas_realizadas_ult_30d,
            SUM(CASE WHEN aprobador_id = ? AND estado = 'APROBADO'
                AND fecha_modificacion >= date('now', '-30 days') THEN 1 ELSE 0 END)
                as aprobadas_por_mi_ult_30d
        FROM conexiones
        WHERE solicitante_id = ? OR realizador_id = ? OR aprobador_id = ?
    """
    params = [user_id] * 9
    cursor = db.cursor()
    cursor.execute(summary_query, params)
    summary_row = cursor.fetchone()

    summary = dict(summary_row) if summary_row else {}
    keys = [
        'total_conexiones_creadas',
        'conexiones_en_proceso_solicitadas',
        'conexiones_aprobadas_solicitadas',
        'mis_tareas_en_proceso',
        'mis_tareas_realizadas_ult_30d',
        'aprobadas_por_mi_ult_30d']
    for key in keys:
        summary.setdefault(key, 0)

    pendientes_query = """
        SELECT COUNT(c.id) as total FROM conexiones c
        JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id
        WHERE c.estado = 'REALIZADO' AND pu.usuario_id = ?
    """
    cursor.execute(pendientes_query, (user_id,))
    pendientes_row = cursor.fetchone()
    summary['pendientes_mi_aprobacion'] = pendientes_row['total'] if pendientes_row else 0
    summary['notificaciones_no_leidas'] = len(g.get('notifications', []))

    dashboard_data['my_summary'] = summary

    if 'REALIZADOR' in user_roles or 'APROBADOR' in user_roles:
        performance = {
            'avg_completion_time': 'N/A',
            'tasks_completed_this_month': 0}

        avg_time_sql = (
            "SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_days "
            "FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id "
            "WHERE h1.usuario_id = ? AND h1.estado = 'EN_PROCESO' AND h2.estado IN ('REALIZADO', 'APROBADO')"
        )
        completed_sql = (
            "SELECT COUNT(id) as total FROM conexiones "
            "WHERE (realizador_id = ? AND estado = 'REALIZADO' AND "
            "strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now')) OR "
            "(aprobador_id = ? AND estado = 'APROBADO' AND "
            "strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now'))"
        )

        cursor.execute(avg_time_sql, (user_id,))
        avg_time_result = cursor.fetchone()
        if avg_time_result and avg_time_result['avg_days'] is not None:
            performance['avg_completion_time'] = f"{avg_time_result['avg_days']:.1f} días"

        cursor.execute(completed_sql, (user_id, user_id))
        completed_query = cursor.fetchone()
        performance['tasks_completed_this_month'] = completed_query['total'] if completed_query else 0

        dashboard_data['my_performance'] = performance

        params = (user_id, user_id, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))

        sql = """
            SELECT date(fecha_modificacion) as completion_date, COUNT(id) as total
            FROM conexiones
            WHERE ((realizador_id = ? AND estado = 'REALIZADO') OR (aprobador_id = ? AND estado = 'APROBADO'))
            AND fecha_modificacion >= ?
            GROUP BY completion_date ORDER BY completion_date
        """
        cursor.execute(sql, params)
        completed_tasks_by_day = cursor.fetchall()

        tasks_map = {row['completion_date']: row['total'] for row in completed_tasks_by_day}

        chart_data = {'labels': [], 'data': []}
        for i in range(29, -1, -1):
            date = (datetime.now() - timedelta(days=i))
            date_str = date.strftime('%Y-%m-%d')
            chart_data['labels'].append(date.strftime('%d %b'))
            chart_data['data'].append(tasks_map.get(date_str, 0))

        dashboard_data['my_performance_chart'] = chart_data

    query = """
        SELECT p.id, p.nombre, COUNT(c.id) AS total_conexiones,
               SUM(CASE WHEN c.estado = 'SOLICITADO' THEN 1 ELSE 0 END) AS solicitadas,
               SUM(CASE WHEN c.estado = 'EN_PROCESO' THEN 1 ELSE 0 END) AS en_proceso,
               SUM(CASE WHEN c.estado = 'APROBADO' THEN 1 ELSE 0 END) AS aprobadas,
               SUM(CASE WHEN c.estado = 'RECHAZADO' THEN 1 ELSE 0 END) AS rechazadas
        FROM proyectos p
        JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id
        LEFT JOIN conexiones c ON p.id = c.proyecto_id
        WHERE pu.usuario_id = ?
        GROUP BY p.id, p.nombre ORDER BY p.nombre
    """
    cursor.execute(query, (user_id,))
    my_projects_summary = cursor.fetchall()
    dashboard_data['my_projects_summary'] = [dict(row) for row in my_projects_summary]

    cursor.execute(
        'SELECT widgets_config FROM user_dashboard_preferences WHERE usuario_id = ?',
        (user_id,)
    )
    user_prefs_row = cursor.fetchone()
    dashboard_data['user_prefs'] = json.loads(
        user_prefs_row['widgets_config']) if user_prefs_row and user_prefs_row['widgets_config'] else {}

    if 'ADMINISTRADOR' in user_roles:
        start_date_obj = datetime.strptime(date_start_str, '%Y-%m-%d')
        end_date_obj = datetime.strptime(date_end_str, '%Y-%m-%d') + timedelta(days=1)

        kpi_counts_query = (
            "SELECT SUM(CASE WHEN estado NOT IN ('APROBADO', 'RECHAZADO') THEN 1 ELSE 0 END) as total_activas, "
            "SUM(CASE WHEN date(fecha_creacion) = date('now') THEN 1 ELSE 0 END) as creadas_hoy FROM conexiones"
        )
        avg_time_sql = (
            "SELECT AVG(julianday(h2.fecha) - julianday(h1.fecha)) as avg_time "
            "FROM historial_estados h1 JOIN historial_estados h2 ON h1.conexion_id = h2.conexion_id "
            "WHERE h1.estado = 'SOLICITADO' AND h2.estado = 'APROBADO'"
        )

        cursor.execute(kpi_counts_query)
        kpi_counts = cursor.fetchone()

        admin_data = {'kpis': {}}
        admin_data['kpis']['total_activas'] = kpi_counts['total_activas'] or 0
        admin_data['kpis']['creadas_hoy'] = kpi_counts['creadas_hoy'] or 0

        cursor.execute(avg_time_sql)
        avg_time_result = cursor.fetchone()
        avg_days = avg_time_result['avg_time'] if avg_time_result and avg_time_result['avg_time'] is not None else 0
        admin_data['kpis']['tiempo_aprobacion'] = f"{avg_days:.1f} días" if avg_days > 0 else "N/A"

        dashboard_data['kpis'] = admin_data['kpis']
        dashboard_data['charts'] = {}

    tasks = {
        'pendientes_aprobacion': [],
        'mis_asignadas': [],
        'disponibles': [],
        'mis_solicitudes': []}

    if 'APROBADOR' in user_roles:
        query = (
            "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, "
            "c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON "
            "c.proyecto_id = p.id JOIN proyecto_usuarios pu ON c.proyecto_id = pu.proyecto_id "
            "WHERE c.estado = 'REALIZADO' AND pu.usuario_id = ? "
            "ORDER BY c.fecha_modificacion DESC LIMIT 5"
        )
        cursor.execute(query, (user_id,))
        tasks['pendientes_aprobacion'] = cursor.fetchall()

    if 'REALIZADOR' in user_roles:
        query = (
            "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, "
            "c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON "
            "c.proyecto_id = p.id WHERE c.estado = 'EN_PROCESO' AND c.realizador_id = ? "
            "ORDER BY c.fecha_modificacion DESC LIMIT 5"
        )
        cursor.execute(query, (user_id,))
        tasks['mis_asignadas'] = cursor.fetchall()

        query_disponibles = (
            "SELECT c.id, c.codigo_conexion, p.nombre as proyecto_nombre, c.fecha_creacion, "
            "c.tipo, c.estado, c.realizador_id FROM conexiones c JOIN proyectos p ON "
            "c.proyecto_id = p.id WHERE c.estado = 'SOLICITADO' "
            "ORDER BY c.fecha_creacion DESC LIMIT 5"
        )
        cursor.execute(query_disponibles)
        tasks['disponibles'] = cursor.fetchall()

    if 'SOLICITANTE' in user_roles:
        query = (
            "SELECT id, codigo_conexion, estado, fecha_creacion, tipo FROM conexiones "
            "WHERE solicitante_id = ? AND estado NOT IN ('APROBADO') "
            "ORDER BY fecha_creacion DESC LIMIT 5"
        )
        cursor.execute(query, (user_id,))
        tasks['mis_solicitudes'] = cursor.fetchall()

    dashboard_data['tareas'] = tasks

    cursor.execute("""
        SELECT h.objeto_id as conexion_id, h.fecha, u.nombre_completo as usuario_nombre,
               c.codigo_conexion, h.accion, h.detalles
        FROM auditoria_acciones h
        JOIN usuarios u ON h.usuario_id = u.id
        LEFT JOIN conexiones c ON h.objeto_id = c.id AND h.tipo_objeto = 'conexiones'
        WHERE h.accion IN ('CREAR_CONEXION', 'TOMAR_CONEXION',
                           'MARCAR_REALIZADO_CONEXION', 'APROBAR_CONEXION',
                           'RECHAZAR_CONEXION', 'SUBIR_ARCHIVO', 'AGREGAR_COMENTARIO')
        ORDER BY h.fecha DESC LIMIT 10
    """)
    dashboard_data['feed_actividad'] = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM proyectos ORDER BY nombre")
    all_projects_for_filter = cursor.fetchall()

    cursor.close()

    return render_template(
        'dashboard.html',
        dashboard_data=dashboard_data,
        titulo="Dashboard",
        filters=filters,
        all_projects_for_filter=all_projects_for_filter)


@main_bp.route('/catalogo')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def catalogo():
    db = get_db()
    cursor = db.cursor()

    try:
        json_path = os.path.join(current_app.root_path, 'conexiones.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            estructura = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.error(
            f"Error crítico al cargar 'conexiones.json': {e}",
            exc_info=True)
        flash(
            "Error crítico: No se pudo cargar la configuración de conexiones.",
            "danger")
        return redirect(url_for('main.dashboard'))

    user_roles = session.get('user_roles', [])
    try:
        if 'ADMINISTRADOR' in user_roles:
            cursor.execute("SELECT id, nombre FROM proyectos ORDER BY nombre")
        else:
            cursor.execute(
                "SELECT p.id, p.nombre FROM proyectos p JOIN proyecto_usuarios pu ON p.id = pu.proyecto_id WHERE pu.usuario_id = ? ORDER BY p.nombre",
                (g.user['id'],
                 ))
        proyectos = cursor.fetchall()
    finally:
        cursor.close()

    preselect_project_id = request.args.get('preselect_project_id', type=int)
    return render_template(
        'catalogo.html',
        estructura=estructura,
        proyectos=proyectos,
        preselect_project_id=preselect_project_id,
        titulo="Catálogo")


@main_bp.route('/buscar')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def buscar():
    query = request.args.get('q', '')
    if not query:
        return render_template(
            'buscar.html',
            resultados=[],
            query=query,
            titulo="Buscar")

    db = get_db()
    cursor = db.cursor()
    resultados = []

    try:
        term = f"%{query}%"
        sql = """
            SELECT c.*, p.nombre as proyecto_nombre, sol.nombre_completo as solicitante_nombre
            FROM conexiones c
            JOIN proyectos p ON c.proyecto_id = p.id
            LEFT JOIN usuarios sol ON c.solicitante_id = sol.id
            WHERE c.codigo_conexion LIKE ? OR c.descripcion LIKE ?
            ORDER BY c.fecha_creacion DESC
        """
        cursor.execute(sql, (term, term))
        resultados = cursor.fetchall()
    finally:
        cursor.close()

    return render_template(
        'buscar.html',
        resultados=resultados,
        query=query,
        titulo=f"Resultados para '{query}'")

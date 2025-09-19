import json
import os
import re
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, g, current_app, redirect,
                   url_for, request, session, flash)
from db import get_db
from . import roles_required
from services.dashboard_service import get_dashboard_data

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def dashboard():
    user_id = g.user['id']
    user_roles = session.get('user_roles', [])

    date_start_str = request.args.get(
        'date_start', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_end_str = request.args.get(
        'date_end', datetime.now().strftime('%Y-%m-%d'))
    filters = {'start': date_start_str, 'end': date_end_str}

    # Fetch all dashboard data from the optimized and cached service
    dashboard_data = get_dashboard_data(user_id, user_roles)

    return render_template(
        'dashboard.html',
        dashboard_data=dashboard_data,
        titulo="Dashboard",
        filters=filters,
        all_projects_for_filter=dashboard_data.get('all_projects_for_filter', []))


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
        resultados = cursor.fetchall()
    finally:
        cursor.close()

    return render_template(
        'buscar.html',
        resultados=resultados,
        query=query,
        titulo=f"Resultados para '{query}'")

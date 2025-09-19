import json
import os
import re
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, g, current_app, redirect,
                   url_for, request, session, flash)
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, g, redirect,
                   url_for, request, session, flash)
from . import roles_required
from services.dashboard_service import get_dashboard_data
from services.main_service import get_catalogo_data, search_conexiones

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
    preselect_project_id = request.args.get('preselect_project_id', type=int)
    try:
        data = get_catalogo_data(preselect_project_id)
        return render_template(
            'catalogo.html',
            estructura=data['estructura'],
            proyectos=data['proyectos'],
            preselect_project_id=data['preselect_project_id'],
            titulo="Catálogo")
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for('main.dashboard'))


@main_bp.route('/buscar')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def buscar():
    query = request.args.get('q', '')
    resultados = search_conexiones(query) if query else []

    return render_template(
        'buscar.html',
        resultados=resultados,
        query=query,
        titulo=f"Resultados para '{query}'" if query else "Buscar")

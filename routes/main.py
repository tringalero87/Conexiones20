from flask import Blueprint, render_template, g, session
from . import roles_required
import services.dashboard_service as ds
import services.main_service as ms
from flask import request, redirect, url_for
from forms import LoginForm

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if g.user:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    return render_template('login.html', form=form, titulo="Iniciar Sesión")

@bp.route('/dashboard')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def dashboard():
    dashboard_data = ds.get_dashboard_data(g.user)
    return render_template('dashboard.html', titulo="Dashboard", **dashboard_data)

@bp.route('/catalogo')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def catalogo():
    preselect_project_id = session.get('last_project_id', None)
    catalogo_data = ms.get_catalogo_data(preselect_project_id)
    return render_template('catalogo.html', titulo="Catálogo de Tipologías", **catalogo_data)

@bp.route('/buscar')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def buscar():
    query = request.args.get('q', '')
    resultados = ms.search_conexiones(query)
    return render_template('buscar.html', resultados=resultados, query=query, titulo=f"Resultados para '{query}'")

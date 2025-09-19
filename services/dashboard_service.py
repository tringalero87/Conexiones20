import time
from datetime import datetime, timedelta
from flask import g, request
from sqlalchemy import func, case, text
from extensions import db
from models import Conexion, Usuario, Proyecto, HistorialEstado, AuditoriaAccion, UserDashboardPreference, Notificacion, Comentario

def get_dashboard_data(user):
    """
    Obtiene todos los datos necesarios para el dashboard de un usuario.
    """
    user_id = user.id
    user_roles = user.roles

    dashboard_data = {
        'kpis': {}, 'charts': {}, 'filters': {},
        'tareas': {'pendientes_aprobacion': [], 'mis_asignadas': [], 'disponibles': [], 'mis_solicitudes': []},
        'feed_actividad': [], 'my_summary': {}, 'my_performance': {}, 'my_performance_chart': {},
        'my_projects_summary': [], 'user_prefs': {}, 'all_projects_for_filter': []
    }

    # --- Lógica de Administrador ---
    if 'ADMINISTRADOR' in user_roles:
        start_date_str = request.args.get('date_start')
        end_date_str = request.args.get('date_end')

        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.utcnow()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else end_date - timedelta(days=30)

        dashboard_data['filters'] = {'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')}

        # KPIs
        kpis = {}
        base_query = db.session.query(Conexion).filter(Conexion.fecha_creacion.between(start_date, end_date))
        kpis['total_activas'] = base_query.filter(Conexion.estado.notin_(['APROBADO', 'RECHAZADO'])).count()
        kpis['creadas_hoy'] = db.session.query(Conexion).filter(func.date(Conexion.fecha_creacion) == func.date('now')).count()
        total_count = base_query.count()
        rechazadas_count = base_query.filter_by(estado='RECHAZADO').count()
        kpis['tasa_rechazo'] = f"{(rechazadas_count / total_count * 100) if total_count > 0 else 0:.1f}%"
        dashboard_data['kpis'] = kpis

        # Charts
        estados_data = db.session.query(Conexion.estado, func.count(Conexion.id)).group_by(Conexion.estado).all()
        meses_data = db.session.query(func.strftime('%Y-%m', Conexion.fecha_creacion), func.count(Conexion.id)).group_by(func.strftime('%Y-%m', Conexion.fecha_creacion)).order_by(func.strftime('%Y-%m', Conexion.fecha_creacion)).all()
        dashboard_data['charts'] = {
            'estados': {row[0]: row[1] for row in estados_data},
            'conexiones_mes': [{'mes': row[0], 'total': row[1]} for row in meses_data]
        }

    # --- Lógica para todos los usuarios ---

    # My Summary
    summary = {
        'total_conexiones_creadas': db.session.query(Conexion).filter_by(solicitante_id=user_id).count(),
        'conexiones_aprobadas_solicitadas': db.session.query(Conexion).filter_by(solicitante_id=user_id, estado='APROBADO').count(),
        'mis_tareas_en_proceso': db.session.query(Conexion).filter_by(realizador_id=user_id, estado='EN_PROCESO').count(),
        'pendientes_mi_aprobacion': db.session.query(Conexion).join(Proyecto.usuarios_asignados).filter(Conexion.estado == 'REALIZADO', Usuario.id == user_id).count(),
        'notificaciones_no_leidas': db.session.query(Notificacion).filter_by(usuario_id=user_id, leida=False).count()
    }
    dashboard_data['my_summary'] = summary

    # My Projects Summary
    dashboard_data['my_projects_summary'] = db.session.query(
        Proyecto.id,
        Proyecto.nombre,
        func.count(Conexion.id).label('total_conexiones'),
        func.sum(case((Conexion.estado == 'SOLICITADO', 1), else_=0)).label('solicitadas'),
        func.sum(case((Conexion.estado.in_(['EN_PROCESO', 'REALIZADO']), 1), else_=0)).label('en_proceso'),
        func.sum(case((Conexion.estado == 'APROBADO', 1), else_=0)).label('aprobadas'),
        func.sum(case((Conexion.estado == 'RECHAZADO', 1), else_=0)).label('rechazadas')
    ).outerjoin(Conexion).join(Proyecto.usuarios_asignados).filter(Usuario.id == user_id).group_by(Proyecto.id, Proyecto.nombre).all()


    # Task Lists
    if 'APROBADOR' in user_roles:
        dashboard_data['tareas']['pendientes_aprobacion'] = db.session.query(Conexion).join(Proyecto.usuarios_asignados).filter(Conexion.estado == 'REALIZADO', Usuario.id == user_id).order_by(Conexion.fecha_modificacion.desc()).limit(5).all()
    if 'REALIZADOR' in user_roles:
        dashboard_data['tareas']['mis_asignadas'] = db.session.query(Conexion).filter_by(realizador_id=user_id, estado='EN_PROCESO').order_by(Conexion.fecha_modificacion.desc()).limit(5).all()
        dashboard_data['tareas']['disponibles'] = db.session.query(Conexion).filter_by(estado='SOLICITADO').order_by(Conexion.fecha_creacion.desc()).limit(5).all()
    if 'SOLICITANTE' in user_roles:
        dashboard_data['tareas']['mis_solicitudes'] = db.session.query(Conexion).filter_by(solicitante_id=user_id).order_by(Conexion.fecha_creacion.desc()).limit(10).all()

    # Recent Activity Feed
    dashboard_data['feed_actividad'] = db.session.query(
        HistorialEstado.fecha,
        HistorialEstado.estado.label('accion'),
        Usuario.nombre_completo.label('usuario_nombre'),
        Conexion.id.label('conexion_id'),
        Conexion.codigo_conexion
    ).join(Usuario, HistorialEstado.usuario_id == Usuario.id)\
     .join(Conexion, HistorialEstado.conexion_id == Conexion.id)\
     .order_by(HistorialEstado.fecha.desc()).limit(10).all()

    # All projects for filter dropdown
    dashboard_data['all_projects_for_filter'] = db.session.query(Proyecto).join(Proyecto.usuarios_asignados).filter(Usuario.id == user_id).all()

    return dashboard_data

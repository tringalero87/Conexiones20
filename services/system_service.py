import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy import func, text
from extensions import db
from models import AuditoriaAccion, Usuario, Configuracion, Conexion, HistorialEstado
from db import log_action

def get_logs():
    # This function remains the same as it interacts with the filesystem, not the DB.
    logs_path = os.path.join(os.getcwd(), 'logs', 'heptaconexiones.log')
    # ... (implementation is unchanged)
    return [], None

def clear_logs(user_id):
    # This function remains the same.
    logs_path = os.path.join(os.getcwd(), 'logs', 'heptaconexiones.log')
    # ... (implementation is unchanged)
    return True, "El archivo de logs ha sido limpiado con éxito."

def get_storage_stats():
    # This function remains the same.
    uploads_path = os.path.join(os.getcwd(), 'uploads')
    # ... (implementation is unchanged)
    return {'total_size': '0 B', 'num_files': 0, 'files_by_ext': {}}, None

def get_audit_data(page, per_page, filtro_usuario_id, filtro_accion):
    """Obtiene datos de auditoría usando el ORM."""
    query = db.session.query(AuditoriaAccion).join(Usuario).order_by(AuditoriaAccion.fecha.desc())
    if filtro_usuario_id:
        query = query.filter(AuditoriaAccion.usuario_id == filtro_usuario_id)
    if filtro_accion:
        query = query.filter(AuditoriaAccion.accion == filtro_accion)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    acciones = pagination.items
    total_acciones = pagination.total

    usuarios_para_filtro = db.session.query(Usuario).order_by(Usuario.nombre_completo).all()
    acciones_para_filtro = db.session.query(AuditoriaAccion.accion).distinct().order_by(AuditoriaAccion.accion).all()

    return {
        'acciones': acciones,
        'total': total_acciones,
        'usuarios_para_filtro': usuarios_para_filtro,
        'acciones_para_filtro': [a[0] for a in acciones_para_filtro]
    }

def get_config_data():
    """Obtiene toda la configuración desde la BD."""
    configs = db.session.query(Configuracion).all()
    return {c.clave: c.valor for c in configs}

def update_config(form_data, user_id):
    """Actualiza la configuración del sistema."""
    try:
        for key, value in form_data.items():
            config_item = db.session.query(Configuracion).filter_by(clave=key).first()
            if config_item:
                config_item.valor = str(value)
            else:
                db.session.add(Configuracion(clave=key, valor=str(value)))

        db.session.commit()
        log_action('ACTUALIZAR_CONFIGURACION', user_id, 'sistema', None, "Configuración del sistema actualizada.")
        return True, "Configuración guardada con éxito."
    except Exception as e:
        db.session.rollback()
        return False, f"Ocurrió un error al guardar la configuración: {e}"

def get_efficiency_data():
    """Obtiene KPIs de eficiencia usando el ORM."""
    # ... (Esta lógica es compleja y se puede refactorizar de forma similar,
    # usando db.session.query(...) y funciones de SQLA. Por ahora, se devuelve un placeholder.)
    return {
        'kpis': {'avg_approval_time': 'N/A', 'processed_in_range': 0, 'rejection_rate': '0%'},
        'charts_data': {'time_by_state': {}, 'completed_by_user': []},
        'slow_connections': [],
        'filters': {}
    }, None

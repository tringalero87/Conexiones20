import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from dal.sqlite_dal import SQLiteDAL
from db import log_action

def get_logs():
    logs_path = os.path.join(os.getcwd(), 'logs', 'heptaconexiones.log')
    log_entries = []
    try:
        with open(logs_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-100:]
            lines.reverse()
            for line in lines:
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+): (.*)', line)
                if match:
                    log_entries.append({
                        'timestamp': match.group(1),
                        'level': match.group(2),
                        'message': match.group(3)
                    })
    except FileNotFoundError:
        return [], "No se encontró el archivo de log. Puede que aún no se haya generado."
    return log_entries, None

def clear_logs(user_id):
    logs_path = os.path.join(os.getcwd(), 'logs', 'heptaconexiones.log')
    try:
        with open(logs_path, 'w') as f:
            pass
        log_action('LIMPIAR_LOGS', user_id, 'sistema', None, "Limpió el archivo de logs.")
        return True, "El archivo de logs ha sido limpiado con éxito."
    except Exception as e:
        return False, "Ocurrió un error al intentar limpiar el archivo de logs."

def get_storage_stats():
    uploads_path = os.path.join(os.getcwd(), 'uploads')
    total_size_bytes = 0
    num_files = 0
    files_by_ext = defaultdict(int)

    try:
        for dirpath, _, filenames in os.walk(uploads_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    size = os.path.getsize(fp)
                    total_size_bytes += size
                    num_files += 1
                    ext = os.path.splitext(f)[1].lower()
                    files_by_ext[ext if ext else "sin_extension"] += 1
    except Exception as e:
        return None, f"Error al calcular el uso de almacenamiento: {e}"

    def format_bytes(size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    return {
        'total_size': format_bytes(total_size_bytes),
        'num_files': num_files,
        'files_by_ext': dict(files_by_ext)
    }, None

def get_audit_data(page, per_page, filtro_usuario_id, filtro_accion):
    dal = SQLiteDAL()
    offset = (page - 1) * per_page
    acciones, total_acciones = dal.get_audit_logs(offset, per_page, filtro_usuario_id, filtro_accion)
    usuarios_para_filtro = dal.get_all_users_with_roles()
    acciones_para_filtro = dal.get_distinct_audit_actions()
    return {
        'acciones': acciones,
        'total_acciones': total_acciones,
        'usuarios_para_filtro': usuarios_para_filtro,
        'acciones_para_filtro': acciones_para_filtro
    }

def get_config_data():
    dal = SQLiteDAL()
    return dal.get_all_config()

def update_config(form_data, user_id):
    dal = SQLiteDAL()
    # In a real app, you'd validate the data
    try:
        dal.update_config('PER_PAGE', str(form_data.get('per_page')))
        dal.update_config('MAINTENANCE_MODE', '1' if form_data.get('maintenance_mode') else '0')
        log_action('ACTUALIZAR_CONFIGURACION', user_id, 'sistema', None, "Configuración del sistema actualizada.")
        return True, "Configuración guardada con éxito."
    except Exception as e:
        return False, "Ocurrió un error al guardar la configuración."

def get_efficiency_data():
    dal = SQLiteDAL()
    kpis = dal.get_efficiency_kpis()

    # This part will be fixed in a later step, as it requires a new DAL method
    time_by_state = dal.get_time_by_state()

    completed_by_user = dal.get_completed_by_user()
    slow_connections = dal.get_slow_connections()

    charts_data = {
        'time_by_state': time_by_state,
        'completed_by_user': [{'user': row['nombre_completo'], 'total': row['total']} for row in completed_by_user]
    }

    filters = {
        'start': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        'end': datetime.now().strftime('%Y-%m-%d')
    }

    return {
        'kpis': kpis,
        'charts_data': charts_data,
        'slow_connections': slow_connections,
        'filters': filters
    }, None

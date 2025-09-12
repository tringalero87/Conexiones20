# Hepta_Conexiones/routes/conexiones.py
import os
import json
import datetime
import bleach
import pandas as pd
from flask import (Blueprint, render_template, request, redirect, url_for, g,
                   current_app, flash, abort, send_from_directory, jsonify, session)
from werkzeug.utils import secure_filename
from collections import defaultdict
from flask_mail import Message
from extensions import mail
import threading

from db import get_db, log_action
from . import roles_required
from forms import ConnectionForm
from utils.computos import calcular_peso_perfil
import re # Asegúrate de que re esté importado al inicio del archivo

# Se define el Blueprint para agrupar todas las rutas de este módulo.
conexiones_bp = Blueprint('conexiones', __name__, url_prefix='/conexiones')

# Define las extensiones de archivo permitidas para la subida.
ALLOWED_EXTENSIONS = {
    'csv', 'ideacon', 'j1', 'j10', 'j100', 'j100000007', 'j1001', 'j1002', 'j1003', 'j1004',
    'j1006', 'j101', 'j1010', 'j1011', 'j1013', 'j1014', 'j1015', 'j1016', 'j1017', 'j1019',
    'j102', 'j1022', 'j1023', 'j1024', 'j1025', 'j1026', 'j1029', 'j103', 'j1030', 'j1031',
    'j1032', 'j1033', 'j1035', 'j1036', 'j1037', 'j1038', 'j1039', 'j104', 'j1040', 'j1041',
    'j1042', 'j1043', 'j1044', 'j1045', 'j1046', 'j1047', 'j1048', 'j1049', 'j105', 'j1050',
    'j1051', 'j1052', 'j1053', 'j1054', 'j1055', 'j1056', 'j1057', 'j1058', 'j1059', 'j106',
    'j1060', 'j1061', 'j1062', 'j1063', 'j1064', 'j1065', 'j1066', 'j1067', 'j1068', 'j1069',
    'j11', 'j110', 'j111', 'j112', 'j113', 'j114', 'j115', 'j116', 'j117', 'j118', 'j119',
    'j12', 'j120', 'j121', 'j123', 'j124', 'j125', 'j126', 'j127', 'j128', 'j129', 'j13',
    'j130', 'j131', 'j132', 'j133', 'j134', 'j135', 'j136', 'j137', 'j14', 'j140', 'j14000104',
    'j141', 'j142', 'j143', 'j144', 'j146', 'j147', 'j148', 'j149', 'j150', 'j150000010',
    'j150000012', 'j150000014', 'j150000110', 'j150000111', 'j150000112', 'j150001008',
    'j150001028', 'j150001030', 'j1501', 'j1502', 'j151', 'j152', 'j1520', 'j1523', 'j1524',
    'j160', 'j161', 'j162', 'j163', 'j164', 'j165', 'j169', 'j17', 'j170', 'j171', 'j175',
    'j176', 'j177', 'j178', 'j179', 'j181', 'j182', 'j183', 'j184', 'j185', 'j186', 'j187',
    'j188', 'j189', 'j19', 'j190', 'j190000002', 'j190000197', 'j192', 'j193', 'j194', 'j195',
    'j196', 'j197', 'j199', 'j2', 'j20', 'j200', 'j210000087', 'j210000089', 'j210000167',
    'j210000169', 'j210000181', 'j210000182', 'j210001050', 'j210001051', 'j22', 'j220000004',
    'j220000008', 'j220000014', 'j220000019', 'j22000004', 'j22000008', 'j220000104',
    'j220000105', 'j220000106', 'j220000110', 'j220000118', 'j22000019', 'j22000105', 'j23',
    'j230000008', 'j230000013', 'j230000014', 'j230000020', 'j230000021', 'j230000022',
    'j230000027', 'j230000028', 'j23000003', 'j23000004', 'j230000105', 'j230000106',
    'j230000109', 'j23000020', 'j23000022', 'j23000025', 'j23000026', 'j23000027', 'j23000028',
    'j230001003', 'j230001004', 'j24', 'j240000008', 'j240000014', 'j24000006', 'j240000101',
    'j240000102', 'j240000104', 'j240000105', 'j240000106', 'j240000199', 'j240001006',
    'j24000101', 'j24000102', 'j24000103', 'j25', 'j250000008', 'j250000014', 'j250000104',
    'j250000105', 'j250000106', 'j250000110', 'j250000118', 'j26', 'j260000008', 'j260000014',
    'j260000105', 'j260000106', 'j260000113', 'j260000115', 'j260000119', 'j260000126', 'j27',
    'j270000008', 'j270000014', 'j270000105', 'j270000106', 'j270000114', 'j270000117',
    'j270000125', 'j270000128', 'j28', 'j280000008', 'j280000014', 'j280000105', 'j280000106',
    'j280000110', 'j280000116', 'j280000127', 'j280000132', 'j280000133', 'j29', 'j290000008',
    'j290000014', 'j290000104', 'j290000105', 'j290000106', 'j290000107', 'j290000108',
    'j290000124', 'j3', 'j30', 'j300000007', 'j300000008', 'j300000014', 'j300000029',
    'j300000105', 'j300000106', 'j300000113', 'j300000115', 'j300000119', 'j300000126',
    'j30000013', 'j30000014', 'j30000075', 'j30000076', 'j30000077', 'j30000078', 'j31',
    'j310000010', 'j310000016', 'j310000024', 'j310000025', 'j310000026', 'j310000027',
    'j310000028', 'j310000029', 'j310000030', 'j310000031', 'j310000032', 'j310000033',
    'j310000034', 'j310000035', 'j310000036', 'j310000037', 'j310000038', 'j310000039',
    'j310000040', 'j310000041', 'j310000042', 'j310000043', 'j310000044', 'j310000045',
    'j310000046', 'j310000047', 'j310000048', 'j310000049', 'j310000050', 'j310000051',
    'j310000052', 'j310000053', 'j310000054', 'j310000055', 'j310000056', 'j310000057',
    'j310000058', 'j310000059', 'j310000060', 'j310000061', 'j310000062', 'j310000063',
    'j310000064', 'j310000065', 'j310000066', 'j310000067', 'j310000068', 'j310000069',
    'j310000070', 'j310000071', 'j310000073', 'j310000074', 'j310000082', 'j310000102',
    'j310000103', 'j310000144', 'j310000149', 'j310000154', 'j310001030', 'j310001031',
    'j310001032', 'j310001033', 'j310001034', 'j32', 'j33', 'j330000008', 'j330000013',
    'j330000014', 'j330000021', 'j330000027', 'j330000028', 'j330000105', 'j330000106',
    'j330001004', 'j34', 'j36', 'j37', 'j38', 'j380000004', 'j39', 'j4', 'j40', 'j400000011',
    'j400000012', 'j400000021', 'j400000185', 'j41', 'j410000008', 'j410000014', 'j410000105',
    'j410000106', 'j410000110', 'j410000118', 'j410000131', 'j410000132', 'j410000133',
    'j410000134', 'j410000135', 'j410000136', 'j410000137', 'j42', 'j420000008', 'j420000014',
    'j420000105', 'j420000106', 'j420000110', 'j420000118', 'j43', 'j430000001', 'j430000002',
    'j430000003', 'j430000005', 'j430000006', 'j430000007', 'j430000008', 'j430000009',
    'j430000010', 'j430000011', 'j44', 'j45', 'j450000008', 'j450000014', 'j450000101',
    'j450000102', 'j450000104', 'j450000105', 'j450000106', 'j46', 'j47', 'j48', 'j49', 'j5',
    'j50', 'j501', 'j502', 'j503', 'j504', 'j505', 'j506', 'j508', 'j51', 'j512', 'j515',
    'j516', 'j517', 'j518', 'j519', 'j52', 'j528', 'j53', 'j530', 'j54', 'j56', 'j57', 'j58',
    'j583', 'j584', 'j585', 'j586', 'j587', 'j588', 'j589', 'j59', 'j590', 'j592', 'j593',
    'j594', 'j6', 'j60', 'j604', 'j605', 'j61', 'j611', 'j612', 'j62', 'j623', 'j63', 'j65',
    'j650000002', 'j650000004', 'j660', 'j661', 'j662', 'j663', 'j664', 'j665', 'j666',
    'j667', 'j668', 'j67', 'j68', 'j69', 'j7', 'j70', 'j71', 'j72', 'j73', 'j74', 'j75',
    'j76', 'j77', 'j8', 'j80', 'j80000001', 'j80000002', 'j80000003', 'j80000004', 'j80000005',
    'j80000006', 'j80000007', 'j80000008', 'j80000009', 'j80000010', 'j80000011', 'j80000012',
    'j80000013', 'j80000014', 'j80000015', 'j80000016', 'j80000018', 'j80000102', 'j80000103',
    'j80000113', 'j80001020', 'j81', 'j82', 'j83', 'j84', 'j85', 'j86', 'j87', 'j88', 'j89',
    'j9', 'j90', 'j90000001', 'j90000002', 'j90000003', 'j90000004', 'j90000005', 'j90000006',
    'j90000007', 'j90000008', 'j90000009', 'j90000010', 'j90000011', 'j90000012', 'j90000013',
    'j90000014', 'j90000015', 'j90000016', 'j90000018', 'j90000019', 'j90000020', 'j90000031',
    'j90000032', 'j90000034', 'j90000038', 'j90000040', 'j90000063', 'j90000068', 'j90000076',
    'j90000087', 'j90000088', 'j90000089', 'j90000092', 'j90000093', 'j90000094', 'j90000095',
    'j90000096', 'j90000097', 'j90000098', 'j90000102', 'j90000104', 'j90000106', 'j90000109',
    'j90000110', 'j90000111', 'j90000114', 'j90000115', 'j90001005', 'j90001006', 'j90001007',
    'j90001008', 'j90001010', 'j90001011', 'j90001028', 'j90001029', 'j90001030', 'j90001033',
    'j90001037', 'j90001040', 'j90001047', 'j90001053', 'j90001054', 'j90001055', 'j92',
    'j93', 'j94', 'j95', 'j97', 'pdf', 'xlsx', 'doc', 'xls', 'docx', 'ppt', 'pptx'
}

def allowed_file(filename):
    """Función auxiliar para verificar si la extensión de un archivo es válida.
    Permite extensiones de la lista blanca.
    CORRECCIÓN DE SEGURIDAD: Se eliminan las reglas inseguras de archivos sin extensión y patrones amplios.
    """
    # 1. CORRECCIÓN DE SEGURIDAD: NO permitir archivos sin extensión o que comiencen con un punto (dotfiles).
    # Un archivo sin nombre de base o un archivo oculto puede ser un vector de ataque o un error.
    if '.' not in filename or filename.startswith('.'):
        return False

    extension = filename.rsplit('.', 1)[1].lower()

    # 2. Permitir solo extensiones de la lista blanca estándar
    return extension in ALLOWED_EXTENSIONS

from services.connection_service import process_connection_state_transition, _get_conexion, _notify_users, get_tipologia_config



# --- Rutas para CREAR Conexiones ---

@conexiones_bp.route('/crear', methods=['GET'])
@roles_required('ADMINISTRADOR', 'SOLICITANTE')
def crear_conexion_form():
    """Muestra un formulario dinámico para crear una nueva conexión."""
    proyecto_id = request.args.get('proyecto_id', type=int)
    tipo = request.args.get('tipo')
    subtipo = request.args.get('subtipo')
    tipologia_nombre = request.args.get('tipologia')

    if not all([proyecto_id, tipo, subtipo, tipologia_nombre]):
        flash("Faltan parámetros para crear la conexión. Por favor, selecciona desde el catálogo.", "danger")
        return redirect(url_for('main.catalogo'))

    db = get_db()
    proyecto = db.execute('SELECT * FROM proyectos WHERE id = ?', (proyecto_id,)).fetchone()
    if not proyecto:
        abort(404)

    tipologia_seleccionada = get_tipologia_config(tipo, subtipo, tipologia_nombre)
    if not tipologia_seleccionada:
        flash("Error: No se pudo encontrar la configuración para la tipología seleccionada.", "danger")
        return redirect(url_for('main.catalogo'))
    
    # La lista de alias se carga aquí, pero la lógica de uso en la plantilla
    # para autocompletado o sugerencias debe estar en JS si es necesario.
    # Por ahora, se mantiene para contexto aunque no usada directamente en la plantilla HTML actual para `input type="text"`.
    lista_de_alias = db.execute("SELECT alias, nombre_perfil FROM alias_perfiles ORDER BY nombre_perfil").fetchall()
    
    return render_template('conexion_form.html',
                           proyecto=proyecto,
                           tipo=tipo,
                           subtipo=subtipo,
                           tipologia=tipologia_seleccionada,
                           lista_alias=lista_de_alias,
                           titulo=f"Nueva Conexión: {tipologia_nombre}")

@conexiones_bp.route('/crear', methods=['POST'])
@roles_required('ADMINISTRADOR', 'SOLICITANTE')
def procesar_creacion_conexion():
    """
    Procesa el formulario, busca si los perfiles digitados tienen un alias
    y genera el código de conexión de forma inteligente.
    """
    db = get_db()
    proyecto_id = request.form.get('proyecto_id', type=int)
    tipo = request.form.get('tipo')
    subtipo = request.form.get('subtipo')
    tipologia_nombre = request.form.get('tipologia_nombre')
    
    tipologia_config = get_tipologia_config(tipo, subtipo, tipologia_nombre)
    if not tipologia_config:
        flash("Error: No se pudo encontrar la configuración de la tipología al procesar.", "danger")
        return redirect(url_for('main.catalogo'))

    plantilla_codigo = tipologia_config.get('plantilla', '')
    num_perfiles = tipologia_config.get('perfiles', 0)
    descripcion = request.form.get('descripcion')

    if not db.execute('SELECT id FROM proyectos WHERE id = ?', (proyecto_id,)).fetchone():
        flash("Error: El proyecto seleccionado ya no existe.", "danger")
        return redirect(url_for('main.catalogo'))

    perfiles_para_plantilla = {}
    perfiles_para_detalles = {} # Almacenará los nombres completos de los perfiles

    for i in range(1, num_perfiles + 1):
        nombre_campo = f'perfil_{i}'
        nombre_completo_perfil = request.form.get(nombre_campo)
        
        if not nombre_completo_perfil:
            flash(f"El campo 'Perfil {i}' es obligatorio.", "danger")
            return redirect(url_for('conexiones.crear_conexion_form', proyecto_id=proyecto_id, tipo=tipo, subtipo=subtipo, tipologia=tipologia_nombre))
        
        # Buscar alias para el nombre_completo_perfil
        alias_row = db.execute('SELECT alias FROM alias_perfiles WHERE nombre_perfil = ?', (nombre_completo_perfil,)).fetchone()
        valor_para_codigo = alias_row['alias'] if alias_row else nombre_completo_perfil # Usar alias si existe, sino el nombre completo
        
        perfiles_para_plantilla[f'p{i}'] = valor_para_codigo
        perfiles_para_detalles[f'Perfil {i}'] = nombre_completo_perfil

    codigo_conexion_base = plantilla_codigo.format(**perfiles_para_plantilla)

    # Optimización: chequear existencia y luego iterar si es necesario.
    if db.execute('SELECT 1 FROM conexiones WHERE codigo_conexion = ?', (codigo_conexion_base,)).fetchone():
        contador = 1
        codigo_conexion_final = codigo_conexion_base
        while db.execute('SELECT 1 FROM conexiones WHERE codigo_conexion = ?', (codigo_conexion_final,)).fetchone():
            contador += 1
            codigo_conexion_final = f"{codigo_conexion_base}-{contador}"
    else:
        codigo_conexion_final = codigo_conexion_base
        
    detalles_json = json.dumps(perfiles_para_detalles)
    
    cursor = db.execute(
        "INSERT INTO conexiones (codigo_conexion, proyecto_id, tipo, subtipo, tipologia, descripcion, detalles_json, solicitante_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (codigo_conexion_final, proyecto_id, tipo, subtipo, tipologia_nombre, descripcion, detalles_json, g.user['id'])
    )
    new_conexion_id = cursor.lastrowid
    
    db.execute('INSERT INTO historial_estados (conexion_id, usuario_id, estado) VALUES (?, ?, ?)', (new_conexion_id, g.user['id'], 'SOLICITADO'))
    db.commit()

    log_action('CREAR_CONEXION', g.user['id'], 'conexiones', new_conexion_id, 
               f"Conexión '{codigo_conexion_final}' creada en proyecto '{_get_conexion(new_conexion_id)['proyecto_nombre']}'.") # Auditoría
    _notify_users(db, new_conexion_id, f"Nueva conexión '{codigo_conexion_final}' lista para ser tomada.", "", ['REALIZADOR', 'ADMINISTRADOR'])
    flash(f'Conexión {codigo_conexion_final} creada con éxito.', 'success')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=new_conexion_id))


# --- Rutas de Gestión de Conexiones ---

@conexiones_bp.route('/<int:conexion_id>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def detalle_conexion(conexion_id):
    """
    Muestra la página de detalle completa de una conexión específica.
    """
    db = get_db()
    conexion = _get_conexion(conexion_id)
    
    archivos_raw = db.execute('SELECT a.*, u.nombre_completo as subido_por FROM archivos a JOIN usuarios u ON a.usuario_id = u.id WHERE a.conexion_id = ? ORDER BY a.fecha_subida DESC', (conexion_id,)).fetchall()
    comentarios = db.execute("SELECT c.*, u.nombre_completo FROM comentarios c JOIN usuarios u ON c.usuario_id = u.id WHERE c.conexion_id = ? ORDER BY c.fecha_creacion DESC", (conexion_id,)).fetchall()
    historial = db.execute("SELECT h.*, u.nombre_completo FROM historial_estados h JOIN usuarios u ON h.usuario_id = u.id WHERE h.conexion_id = ? ORDER BY h.fecha DESC", (conexion_id,)).fetchall()
    
    archivos_agrupados = defaultdict(list)
    for archivo in archivos_raw:
        archivos_agrupados[archivo['tipo_archivo']].append(archivo)

    detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
    tipologia_config = get_tipologia_config(conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    plantilla_archivos = tipologia_config.get('plantilla_archivos', []) if tipologia_config else []

    return render_template('detalle_conexion.html',
                           conexion=conexion,
                           archivos_agrupados=archivos_agrupados,
                           comentarios=comentarios,
                           historial=historial,
                           plantilla_archivos=plantilla_archivos,
                           detalles=detalles,
                           titulo=f"Detalle {conexion['codigo_conexion']}")

@conexiones_bp.route('/<int:conexion_id>/editar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'SOLICITANTE')
def editar_conexion(conexion_id):
    """Permite editar los detalles de una conexión existente."""
    db = get_db()
    conexion = _get_conexion(conexion_id)
    user_roles = session.get('user_roles', [])
    user_id = g.user['id']

    # --- Lógica de Autorización Mejorada ---
    can_edit = False
    if 'ADMINISTRADOR' in user_roles:
        can_edit = True
    elif 'SOLICITANTE' in user_roles and conexion['estado'] == 'SOLICITADO' and conexion['solicitante_id'] == user_id:
        can_edit = True
    elif 'REALIZADOR' in user_roles and conexion['estado'] == 'EN_PROCESO' and conexion['realizador_id'] == user_id:
        can_edit = True

    if not can_edit:
        # Se verifica si el estado es el motivo por el cual no se puede editar para dar un mensaje más claro.
        if conexion['estado'] not in ['SOLICITADO', 'EN_PROCESO']:
             flash('Esta conexión ya no puede ser editada porque ha avanzado en el flujo de trabajo.', 'warning')
        else:
             # Si el estado es correcto pero el usuario no es el propietario, se deniega el acceso.
             abort(403)
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    tipologia_config = get_tipologia_config(conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    if not tipologia_config:
        flash("Error: No se encontró la configuración de la tipología para editar.", "danger")
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))
    
    num_perfiles = tipologia_config.get('perfiles', 0)
    
    form = ConnectionForm()
    # Eliminar campos de perfil no necesarios de la instancia del formulario
    # Esto es un workaround. Lo ideal sería construir el formulario dinámicamente.
    if num_perfiles < 3 and hasattr(form, 'perfil_3'):
        del form.perfil_3
    if num_perfiles < 2 and hasattr(form, 'perfil_2'):
        del form.perfil_2

    if form.validate_on_submit():
        perfiles_nuevos_dict_alias = {}
        perfiles_nuevos_dict_full_name = {}
        
        # Bandera para saber si los perfiles o sus alias han cambiado de forma que afecte el código.
        perfiles_cambiaron_para_codigo = False 
        old_perfiles_in_code = {} # Para almacenar los perfiles como estaban en el código original

        # Recuperar los perfiles de la conexión original para comparar
        old_detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
        for i in range(1, num_perfiles + 1):
            old_full_profile_name = old_detalles.get(f'Perfil {i}')
            if old_full_profile_name:
                old_alias_row = db.execute('SELECT alias FROM alias_perfiles WHERE nombre_perfil = ?', (old_full_profile_name,)).fetchone()
                old_value_for_code = old_alias_row['alias'] if old_alias_row else old_full_profile_name
                old_perfiles_in_code[f'p{i}'] = old_value_for_code

        for i in range(1, num_perfiles + 1):
            nombre_campo = f'perfil_{i}'
            perfil_campo = getattr(form, nombre_campo)
            nombre_completo_perfil_nuevo = perfil_campo.data.strip()
            
            if not nombre_completo_perfil_nuevo:
                flash(f"El campo 'Perfil {i}' es obligatorio.", "danger")
                return render_template('conexion_form_edit.html', form=form, conexion=conexion, tipologia=tipologia_config, titulo="Editar Conexión")
            
            # Buscar alias para el nuevo nombre_completo_perfil
            alias_row_nuevo = db.execute('SELECT alias FROM alias_perfiles WHERE nombre_perfil = ?', (nombre_completo_perfil_nuevo,)).fetchone()
            valor_para_codigo_nuevo = alias_row_nuevo['alias'] if alias_row_nuevo else nombre_completo_perfil_nuevo
            
            perfiles_nuevos_dict_alias[f'p{i}'] = valor_para_codigo_nuevo
            perfiles_nuevos_dict_full_name[f'Perfil {i}'] = nombre_completo_perfil_nuevo

            # Comprobar si el valor que iría en el código ha cambiado
            if old_perfiles_in_code.get(f'p{i}') != valor_para_codigo_nuevo:
                perfiles_cambiaron_para_codigo = True

        nuevo_codigo_base = tipologia_config['plantilla'].format(**perfiles_nuevos_dict_alias)
        
        # Regenerar código de conexión si los perfiles relevantes (o sus alias) han cambiado
        # o si la plantilla de código ha cambiado.
        current_codigo_parsed = conexion['codigo_conexion'].rsplit('-', 1)[0] if '-' in conexion['codigo_conexion'] else conexion['codigo_conexion']
        
        # Si el nuevo código base es diferente del código actual (descontando sufijos numéricos)
        # O si los perfiles usados en el código han cambiado
        # Entonces, regenerar el código desde cero y buscar unicidad
        if nuevo_codigo_base != current_codigo_parsed or perfiles_cambiaron_para_codigo:
            # Optimización: chequear existencia y luego iterar si es necesario.
            if db.execute('SELECT 1 FROM conexiones WHERE codigo_conexion = ? AND id != ?', (nuevo_codigo_base, conexion_id)).fetchone():
                contador = 1
                codigo_conexion_final_generado = nuevo_codigo_base
                while db.execute('SELECT 1 FROM conexiones WHERE codigo_conexion = ? AND id != ?', (codigo_conexion_final_generado, conexion_id)).fetchone():
                    contador += 1
                    codigo_conexion_final_generado = f"{nuevo_codigo_base}-{contador}"
                codigo_a_guardar = codigo_conexion_final_generado
            else:
                codigo_a_guardar = nuevo_codigo_base
            
            if codigo_a_guardar != conexion['codigo_conexion']:
                 flash(f"El código de la conexión se ha actualizado a '{codigo_a_guardar}' debido a cambios en los perfiles o sus alias.", "info")
        else:
            # Si no hay cambios en los perfiles relevantes para el código, mantener el código original
            codigo_a_guardar = conexion['codigo_conexion']

        nuevos_detalles_json = json.dumps(perfiles_nuevos_dict_full_name) # Guardar nombres completos de perfiles

        db.execute(
            'UPDATE conexiones SET codigo_conexion = ?, descripcion = ?, detalles_json = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?',
            (codigo_a_guardar, form.descripcion.data, nuevos_detalles_json, conexion_id)
        )
        db.commit()
        log_action('EDITAR_CONEXION', g.user['id'], 'conexiones', conexion_id,
                   f"Conexión '{conexion['codigo_conexion']}' editada a '{codigo_a_guardar}'.") # Auditoría
        current_app.logger.info(f"Usuario '{g.user['username']}' editó la conexión {conexion_id}.")
        flash('Conexión actualizada con éxito.', 'success')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    if request.method == 'GET':
        detalles_actuales = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
        form.descripcion.data = conexion['descripcion']
        # Rellenar los campos de perfil del formulario según num_perfiles
        for i in range(1, num_perfiles + 1):
            if hasattr(form, f'perfil_{i}'):
                setattr(getattr(form, f'perfil_{i}'), 'data', detalles_actuales.get(f'Perfil {i}'))

    return render_template('conexion_form_edit.html', form=form, conexion=conexion, tipologia=tipologia_config, titulo="Editar Conexión")


@conexiones_bp.route('/<int:conexion_id>/eliminar', methods=['POST'])
@roles_required('ADMINISTRADOR')
def eliminar_conexion(conexion_id):
    """Elimina una conexión (solo para administradores)."""
    conexion = _get_conexion(conexion_id)
    db = get_db()
    db.execute('DELETE FROM conexiones WHERE id = ?', (conexion_id,))
    db.commit()
    log_action('ELIMINAR_CONEXION', g.user['id'], 'conexiones', conexion_id,
               f"Conexión '{conexion['codigo_conexion']}' eliminada.") # Auditoría
    current_app.logger.warning(f"Admin '{g.user['username']}' eliminó la conexión {conexion['codigo_conexion']} (ID: {conexion_id}).")
    flash(f"La conexión {conexion['codigo_conexion']} ha sido eliminada.", 'success')
    return redirect(url_for('proyectos.detalle_proyecto', proyecto_id=conexion['proyecto_id']))


# --- Ruta para IMPORTAR Conexiones ---

from services.import_service import importar_conexiones_from_file

@conexiones_bp.route('/<int:proyecto_id>/importar', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def importar_conexiones(proyecto_id):
    """
    Gestiona la importación masiva de conexiones desde un archivo Excel.
    RECOMENDACIÓN: La importación de archivos grandes puede ser un proceso lento.
    Para mejorar la experiencia del usuario, esta tarea debería ejecutarse de forma asíncrona
    utilizando una cola de tareas como Celery. El usuario podría subir el archivo, recibir una
    confirmación inmediata y ser notificado cuando la importación haya finalizado.
    """
    db = get_db()
    proyecto = db.execute('SELECT * FROM proyectos WHERE id = ?', (proyecto_id,)).fetchone()
    if not proyecto:
        abort(404)
        
    if request.method == 'POST':
        if 'archivo_importacion' not in request.files or not request.files['archivo_importacion'].filename:
            flash('No se seleccionó ningún archivo.', 'danger')
            return redirect(request.url)
        
        file = request.files['archivo_importacion']
        if file and file.filename.endswith('.xlsx'):
            imported_count, error_rows, error_message = importar_conexiones_from_file(file, proyecto_id, g.user['id'])

            if error_message:
                flash(error_message, 'danger')
            else:
                if imported_count > 0:
                    flash(f"Importación completada: Se crearon {imported_count} conexiones.", 'success')
                if error_rows:
                    flash(f"Se encontraron problemas en {len(error_rows)} fila(s) durante la importación. Detalles: {'; '.join(error_rows)}", "warning")
                if imported_count == 0 and not error_rows:
                     flash("No se crearon nuevas conexiones. Revisa el formato de tu archivo o los datos.", "info")
        else:
            flash('Formato de archivo no válido. Por favor, sube un archivo .xlsx.', 'warning')

        return redirect(url_for('proyectos.detalle_proyecto', proyecto_id=proyecto_id))

    return render_template('importar_conexiones.html', proyecto=proyecto, titulo="Importar Conexiones")


# --- Rutas para el Ciclo de Vida de la Conexión ---

@conexiones_bp.route('/<int:conexion_id>/cambiar_estado', methods=('POST',))
@roles_required('ADMINISTRADOR', 'REALIZADOR', 'APROBADOR')
def cambiar_estado(conexion_id):
    """Procesa los cambios de estado de una conexión."""
    db = get_db()
    nuevo_estado_form = request.form.get('estado')
    detalles_form = request.form.get('detalles', '')
    
    success, message, _ = process_connection_state_transition(
        db, conexion_id, nuevo_estado_form, g.user['id'], g.user['nombre_completo'], session.get('user_roles', []), detalles_form
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/asignar', methods=['POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def asignar_realizador(conexion_id):
    """
    Permite a los roles autorizados asignar una conexión a un realizador específico.
    """
    db = get_db()
    conexion = _get_conexion(conexion_id)
    
    # Solo el Administrador, el Solicitante, el Realizador o el Aprobador pueden asignar.
    # El Administrador puede asignar a cualquiera.
    # Solicitante, Realizador y Aprobador solo pueden asignar si la conexión está en ciertos estados
    # y/o si están directamente relacionados con ella (ej. el solicitante original).
    user_roles = session.get('user_roles', [])

    if not ('ADMINISTRADOR' in user_roles or \
            ('SOLICITANTE' in user_roles and g.user['id'] == conexion['solicitante_id']) or \
            ('REALIZADOR' in user_roles and g.user['id'] == conexion['realizador_id']) or \
            ('APROBADOR' in user_roles and conexion['estado'] == 'REALIZADO')):
        flash('No tienes permisos para asignar esta conexión.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    username_a_asignar = request.form.get('username_a_asignar')
    
    if not username_a_asignar:
        flash('Debes especificar un nombre de usuario para asignar la tarea.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    # Eliminar el '@' si el usuario lo ingresa.
    username_a_asignar_limpio = username_a_asignar.lstrip('@')

    # Buscar el ID del usuario a asignar
    usuario_a_asignar = db.execute('SELECT id, nombre_completo FROM usuarios WHERE username = ? AND activo = 1', (username_a_asignar_limpio,)).fetchone()

    if not usuario_a_asignar:
        flash(f"Usuario '{username_a_asignar}' no encontrado o inactivo. Por favor, verifica el nombre de usuario.", 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

    # Actualizar el realizador_id de la conexión.
    # Si la conexión está en estado SOLICITADO, se cambia a EN_PROCESO automáticamente al asignar.
    if conexion['estado'] == 'SOLICITADO':
        nuevo_estado = 'EN_PROCESO'
        mensaje_cambio_estado = f"Conexión '{conexion['codigo_conexion']}' asignada a {usuario_a_asignar['nombre_completo']} y puesta 'En Proceso'."
        db.execute('UPDATE conexiones SET realizador_id = ?, estado = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?',
                   (usuario_a_asignar['id'], nuevo_estado, conexion_id))
        db.execute('INSERT INTO historial_estados (conexion_id, usuario_id, estado, detalles) VALUES (?, ?, ?, ?)',
                   (conexion_id, g.user['id'], nuevo_estado, f"Asignada a {usuario_a_asignar['nombre_completo']}"))
        
        _notify_users(db, conexion_id,
                      f"La conexión {conexion['codigo_conexion']} ha sido asignada a {usuario_a_asignar['nombre_completo']} por {g.user['nombre_completo']}.",
                      "",
                      ['SOLICITANTE', 'REALIZADOR', 'APROBADOR', 'ADMINISTRADOR']) # Notificar a todos los relevantes
    else:
        # Si la conexión ya está en proceso o en otro estado, solo se cambia el realizador.
        db.execute('UPDATE conexiones SET realizador_id = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?',
                   (usuario_a_asignar['id'], conexion_id))
        mensaje_cambio_estado = f"Realizador de la conexión '{conexion['codigo_conexion']}' cambiado a {usuario_a_asignar['nombre_completo']}."
        # No se inserta un nuevo historial de estado si solo se cambia el asignado sin cambiar el estado principal.
        # Se puede añadir un log de auditoría para esto:
        log_action('REASIGNAR_CONEXION', g.user['id'], 'conexiones', conexion_id,
                   f"Conexión '{conexion['codigo_conexion']}' reasignada a '{usuario_a_asignar['nombre_completo']}'.")
        _notify_users(db, conexion_id,
                      f"La conexión {conexion['codigo_conexion']} ha sido reasignada a {usuario_a_asignar['nombre_completo']} por {g.user['nombre_completo']}.",
                      "",
                      ['SOLICITANTE', 'REALIZADOR', 'APROBADOR', 'ADMINISTRADOR']) # Notificar a todos los relevantes
        
    db.commit()
    flash(mensaje_cambio_estado, 'success')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/subir_archivo', methods=('POST',))
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def subir_archivo(conexion_id):
    """Gestiona la subida de archivos para una conexión."""
    db = get_db()
    conexion = _get_conexion(conexion_id)

    if 'archivo' not in request.files or not request.files['archivo'].filename:
        flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))
    
    file = request.files['archivo']
    tipo_archivo = request.form.get('tipo_archivo')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id))
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))
        
        db.execute('INSERT INTO archivos (conexion_id, usuario_id, tipo_archivo, nombre_archivo) VALUES (?, ?, ?, ?)',
                   (conexion_id, g.user['id'], tipo_archivo, filename))
        db.commit()
        log_action('SUBIR_ARCHIVO', g.user['id'], 'archivos', conexion_id,
                   f"Archivo '{filename}' ({tipo_archivo}) subido para conexión '{conexion['codigo_conexion']}'.") # Auditoría
        flash(f"Archivo '{tipo_archivo}' subido con éxito.", 'success')
    else:
        flash('Tipo de archivo no permitido.', 'danger')
        
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/descargar/<path:filename>')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def descargar_archivo(conexion_id, filename):
    """Permite la descarga de un archivo asociado a una conexión."""
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id))
    # Asegúrate de que el archivo exista en la BD antes de intentar servirlo
    db = get_db()
    archivo_db = db.execute('SELECT id FROM archivos WHERE conexion_id = ? AND nombre_archivo = ?', (conexion_id, filename)).fetchone()
    if not archivo_db:
        abort(404, description="El archivo no existe o no está asociado a esta conexión.")
    
    log_action('DESCARGAR_ARCHIVO', g.user['id'], 'archivos', conexion_id,
               f"Archivo '{filename}' descargado de conexión '{_get_conexion(conexion_id)['codigo_conexion']}'.") # Auditoría
    return send_from_directory(directory, filename, as_attachment=True)

@conexiones_bp.route('/<int:conexion_id>/eliminar_archivo/<int:archivo_id>', methods=['POST',])
@roles_required('ADMINISTRADOR', 'REALIZADOR')
def eliminar_archivo(conexion_id, archivo_id):
    """Procesa la eliminación de un archivo subido."""
    db = get_db()
    archivo = db.execute('SELECT * FROM archivos WHERE id = ? AND conexion_id = ?', (archivo_id, conexion_id)).fetchone()
    if archivo:
        # CORRECCIÓN DE FLUJO DE TRABAJO: Permitir que el admin, el que subió el archivo,
        # o el realizador actual de la conexión puedan eliminar el archivo.
        conexion = _get_conexion(conexion_id)
        if 'ADMINISTRADOR' not in session.get('user_roles', []) and g.user['id'] != archivo['usuario_id'] and g.user['id'] != conexion['realizador_id']:
             flash('No tienes permiso para eliminar este archivo.', 'danger')
             return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

        try:
            conexion = _get_conexion(conexion_id) # Se obtiene para el log y el redirect
            # CORRECCIÓN DE SEGURIDAD/ROBUSTEZ: Eliminar el registro de la DB primero, luego el archivo.
            # Esto previene un archivo huérfano si la eliminación de la DB falla.
            db.execute('DELETE FROM archivos WHERE id = ?', (archivo_id,))
            db.commit() # Commit inmediato para asegurar la eliminación de la DB
            
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(conexion_id), archivo['nombre_archivo'])
            if os.path.exists(file_path):
                os.remove(file_path)
            
            log_action('ELIMINAR_ARCHIVO', g.user['id'], 'archivos', conexion_id,
                       f"Archivo '{archivo['nombre_archivo']}' eliminado de conexión '{conexion['codigo_conexion']}'.") # Auditoría
            flash('Archivo eliminado con éxito.', 'success')
        except Exception as e:
            current_app.logger.error(f"Error al eliminar archivo: {e}")
            flash('Ocurrió un error al eliminar el archivo.', 'danger')
            # Rollback si se desea deshacer el commit de la DB si el archivo en disco no se pudo eliminar
            # Sin embargo, generalmente es mejor tener un registro sin archivo que un archivo sin registro.
            # Una solución más avanzada podría mover el archivo a una "papelera" primero.
    else:
        flash('El archivo no existe.', 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id))

@conexiones_bp.route('/<int:conexion_id>/comentar', methods=('POST',))
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def agregar_comentario(conexion_id):
    """Añade un comentario a una conexión."""
    contenido = request.form.get('contenido')
    if contenido:
        sanitized_content = bleach.clean(contenido, tags=bleach.sanitizer.ALLOWED_TAGS + ['p', 'br'], strip=True)
        
        db = get_db()
        db.execute('INSERT INTO comentarios (conexion_id, usuario_id, contenido) VALUES (?, ?, ?)',
                   (conexion_id, g.user['id'], sanitized_content))
        db.commit()
        log_action('AGREGAR_COMENTARIO', g.user['id'], 'conexiones', conexion_id,
                   f"Comentario añadido a conexión '{_get_conexion(conexion_id)['codigo_conexion']}'.") # Auditoría
        _notify_users(db, conexion_id, f"{g.user['nombre_completo']} ha comentado en la conexión '{_get_conexion(conexion_id)['codigo_conexion']}'.", "#comentarios", ['SOLICITANTE', 'REALIZADOR', 'APROBADOR', 'ADMINISTRADOR'])
        flash('Comentario añadido.', 'success')
    else:
        flash('El comentario no puede estar vacío.', 'warning')
        
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")

@conexiones_bp.route('/<int:conexion_id>/eliminar_comentario/<int:comentario_id>', methods=['POST',])
@roles_required('ADMINISTRADOR')
def eliminar_comentario(conexion_id, comentario_id):
    """Elimina un comentario (solo para administradores)."""
    db = get_db()
    comentario = db.execute('SELECT * FROM comentarios WHERE id = ? AND conexion_id = ?', (comentario_id, conexion_id)).fetchone()
    if comentario:
        db.execute('DELETE FROM comentarios WHERE id = ?', (comentario_id,))
        db.commit()
        log_action('ELIMINAR_COMENTARIO', g.user['id'], 'comentarios', comentario_id,
                   f"Comentario (ID: {comentario_id}) eliminado de conexión '{_get_conexion(conexion_id)['codigo_conexion']}'.") # Auditoría
        flash('Comentario eliminado.', 'success')
    else:
        flash('El comentario no existe.', 'danger')
    return redirect(url_for('conexiones.detalle_conexion', conexion_id=conexion_id) + "#comentarios")

from services.computos_service import get_computos_results, calculate_and_save_computos

@conexiones_bp.route('/<int:conexion_id>/computos', methods=['GET', 'POST'])
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def computos_metricos(conexion_id):
    """
    Muestra el formulario para ingresar longitudes de perfiles y calcula los cómputos métricos.
    """
    db = get_db()
    conexion = _get_conexion(conexion_id)
    
    if request.method == 'POST':
        resultados, success_message, error_messages, perfiles = calculate_and_save_computos(conexion_id, request.form, g.user['id'])
        if success_message:
            flash(success_message, 'success')
        if error_messages:
            for error in error_messages:
                flash(error, 'danger')

        # We need to get the latest details for rendering
        conexion = _get_conexion(conexion_id) # Re-fetch to get updated details
        _, detalles = get_computos_results(conexion)

    else: # GET Request
        resultados, detalles = get_computos_results(conexion)
        perfiles = [(key, value) for key, value in detalles.items() if key.startswith('Perfil')]

    return render_template('computos_metricos.html',
                           titulo="Cómputos Métricos",
                           conexion=conexion,
                           perfiles=perfiles,
                           resultados=resultados,
                           detalles=detalles)

@conexiones_bp.route('/<int:conexion_id>/reporte_computos')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_computos(conexion_id):
    """
    Genera y muestra un reporte imprimible de cómputos métricos.
    RECOMENDACIÓN: La generación de reportes (especialmente si se convierten a PDF)
    puede ser una tarea intensiva. Considera usar una cola de tareas como Celery
    para generar el reporte en segundo plano y notificar al usuario cuando esté listo.
    """
    conexion = _get_conexion(conexion_id)
    resultados, _ = get_computos_results(conexion)
    
    log_action('GENERAR_REPORTE_COMPUTOS', g.user['id'], 'conexiones', conexion_id,
               f"Reporte de cómputos generado para conexión '{conexion['codigo_conexion']}'.")

    return render_template('reporte_computos.html',
                           titulo=f"Reporte de Cómputos para {conexion['codigo_conexion']}",
                           conexion=conexion,
                           resultados=resultados)

@conexiones_bp.route('/<int:conexion_id>/reporte')
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def reporte_conexion(conexion_id):
    """
    Genera y muestra un reporte detallado de una conexión para impresión.
    RECOMENDACIÓN: La generación de reportes (especialmente si se convierten a PDF)
    puede ser una tarea intensiva. Considera usar una cola de tareas como Celery
    para generar el reporte en segundo plano y notificar al usuario cuando esté listo.
    """
    db = get_db()
    conexion = _get_conexion(conexion_id)
    
    # Asegúrate de tener todos los datos necesarios para el reporte
    historial = db.execute("SELECT h.*, u.nombre_completo FROM historial_estados h JOIN usuarios u ON h.usuario_id = u.id WHERE h.conexion_id = ? ORDER BY h.fecha ASC", (conexion_id,)).fetchall()
    comentarios = db.execute("SELECT c.*, u.nombre_completo FROM comentarios c JOIN usuarios u ON c.usuario_id = u.id WHERE c.conexion_id = ? ORDER BY c.fecha_creacion ASC", (conexion_id,)).fetchall()
    archivos_raw = db.execute('SELECT a.*, u.nombre_completo as subido_por FROM archivos a JOIN usuarios u ON a.usuario_id = u.id WHERE a.conexion_id = ? ORDER BY a.fecha_subida ASC', (conexion_id,)).fetchall()
    
    # Agrupar archivos por tipo, si tu template los necesita así
    archivos_agrupados = defaultdict(list)
    for archivo in archivos_raw:
        archivos_agrupados[archivo['tipo_archivo']].append(archivo)

    # Cargar detalles adicionales y configuración de tipología
    detalles = json.loads(conexion['detalles_json']) if conexion['detalles_json'] else {}
    tipologia_config = get_tipologia_config(conexion['tipo'], conexion['subtipo'], conexion['tipologia'])
    log_action('GENERAR_REPORTE_CONEXION', g.user['id'], 'conexiones', conexion_id,
               f"Reporte de conexión generado para '{conexion['codigo_conexion']}'.") # Auditoría
    return render_template('reporte_conexion.html',
                           conexion=conexion,
                           historial=historial,
                           comentarios=comentarios,
                           archivos_agrupados=archivos_agrupados,
                           detalles=detalles,
                           tipologia_config=tipologia_config,
                           titulo=f"Reporte de Conexión: {conexion['codigo_conexion']}")
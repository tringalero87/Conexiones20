import os
from werkzeug.utils import secure_filename
from flask import current_app, abort
from dal.sqlite_dal import SQLiteDAL
from db import log_action

ALLOWED_EXTENSIONS = {
    'j1', 'j10', 'j100', 'j100000007', 'j1001', 'j1002', 'j1003', 'j1004', 'j1006',
    'j101', 'j1010', 'j1011', 'j1013', 'j1014', 'j1015', 'j1016', 'j1017', 'j1019',
    'j102', 'j1022', 'j1023', 'j1024', 'j1025', 'j1026', 'j1029', 'j103', 'j1030',
    'j1031', 'j1032', 'j1033', 'j1035', 'j1036', 'j1037', 'j1038', 'j1039', 'j104',
    'j1040', 'j1041', 'j1042', 'j1043', 'j1044', 'j1045', 'j1046', 'j1047', 'j1048',
    'j1049', 'j105', 'j1050', 'j1051', 'j1052', 'j1053', 'j1054', 'j1055', 'j1056',
    'j1057', 'j1058', 'j1059', 'j106', 'j1060', 'j1061', 'j1062', 'j1063', 'j1064',
    'j1065', 'j1066', 'j1067', 'j1068', 'j1069', 'j11', 'j110', 'j111', 'j112',
    'j113', 'j114', 'j115', 'j116', 'j117', 'j118', 'j119', 'j12', 'j120',
    'j121', 'j123', 'j124', 'j125', 'j126', 'j127', 'j128', 'j129', 'j13',
    'j130', 'j131', 'j132', 'j133', 'j134', 'j135', 'j136', 'j137', 'j14',
    'j140', 'j14000104', 'j141', 'j142', 'j143', 'j144', 'j146', 'j147', 'j148',
    'j149', 'j150', 'j150000010', 'j150000012', 'j150000014', 'j150000110',
    'j150000111', 'j150000112', 'j150001008', 'j150001028', 'j150001030', 'j1501',
    'j1502', 'j1503', 'j151', 'j152', 'j1520', 'j1523', 'j1524', 'j1555',
    'j1556', 'j160', 'j161', 'j162', 'j163', 'j164', 'j165', 'j169', 'j17',
    'j170', 'j171', 'j175', 'j176', 'j177', 'j178', 'j179', 'j181', 'j182',
    'j183', 'j184', 'j185', 'j186', 'j187', 'j188', 'j189', 'j19', 'j190',
    'j190000002', 'j190000197', 'j192', 'j193', 'j194', 'j195', 'j196', 'j197',
    'j199', 'j2', 'j20', 'j200', 'j210000087', 'j210000089', 'j210000167',
    'j210000169', 'j210000181', 'j210000182', 'j210001050', 'j210001051', 'j22',
    'j220000004', 'j220000008', 'j220000014', 'j220000019', 'j22000004',
    'j22000008', 'j220000104', 'j220000105', 'j220000106', 'j220000110',
    'j220000118', 'j22000019', 'j22000105', 'j23', 'j230000008', 'j230000013',
    'j230000014', 'j230000020', 'j230000021', 'j230000022', 'j230000027',
    'j230000028', 'j23000003', 'j23000004', 'j230000105', 'j230000106',
    'j230000109', 'j23000020', 'j23000022', 'j23000025', 'j23000026',
    'j230001003', 'j230001004', 'j24', 'j240000008', 'j240000014', 'j24000006',
    'j240000101', 'j240000102', 'j240000104', 'j240000105', 'j240000106',
    'j240000199', 'j240001006', 'j24000101', 'j24000102', 'j24000103', 'j25',
    'j250000008', 'j250000014', 'j250000104', 'j250000105', 'j250000106',
    'j250000110', 'j250000118', 'j26', 'j260000008', 'j260000014', 'j260000105',
    'j260000106', 'j260000113', 'j260000115', 'j260000119', 'j260000126', 'j27',
    'j270000008', 'j270000014', 'j270000105', 'j270000106', 'j270000114',
    'j270000117', 'j270000125', 'j270000128', 'j28', 'j280000008', 'j280000014',
    'j280000105', 'j280000106', 'j280000110', 'j280000116', 'j280000127',
    'j280000132', 'j280000133', 'j29', 'j290000008', 'j290000014', 'j290000104',
    'j290000105', 'j290000106', 'j290000107', 'j290000108', 'j290000124', 'j3',
    'j30', 'j300000007', 'j300000008', 'j300000014', 'j300000029', 'j300000105',
    'j300000106', 'j300000113', 'j300000115', 'j300000119', 'j300000126',
    'j30000013', 'j30000014', 'j30000075', 'j30000076', 'j30000077', 'j30000078',
    'j31', 'j310000010', 'j310000016', 'j310000024', 'j310000025', 'j310000026',
    'j310000027', 'j310000028', 'j310000029', 'j310000030', 'j310000031',
    'j310000032', 'j310000033', 'j310000034', 'j310000035', 'j310000036',
    'j310000037', 'j310000038', 'j310000039', 'j310000040', 'j310000041',
    'j310000042', 'j310000043', 'j310000044', 'j310000045', 'j310000046',
    'j310000047', 'j310000048', 'j310000049', 'j310000050', 'j310000051',
    'j310000052', 'j310000053', 'j310000054', 'j310000055', 'j310000056',
    'j310000057', 'j310000058', 'j310000059', 'j310000060', 'j310000061',
    'j310000062', 'j310000063', 'j310000064', 'j310000065', 'j310000066',
    'j310000067', 'j310000068', 'j310000069', 'j310000070', 'j310000071',
    'j310000073', 'j310000074', 'j310000082', 'j310000102', 'j310000103',
    'j310000144', 'j310000149', 'j310000154', 'j310001030', 'j310001031',
    'j310001032', 'j310001033', 'j310001034', 'j32', 'j33', 'j330000008',
    'j330000013', 'j330000014', 'j330000021', 'j330000027', 'j330000028',
    'j330000105', 'j330000106', 'j330001004', 'j34', 'j36', 'j37', 'j38',
    'j380000004', 'j39', 'j4', 'j40', 'j400000011', 'j400000012', 'j400000021',
    'j400000185', 'j41', 'j410000008', 'j410000014', 'j410000105', 'j410000106',
    'j410000110', 'j410000118', 'j410000131', 'j410000132', 'j410000133',
    'j410000134', 'j410000135', 'j410000136', 'j410000137', 'j42', 'j420000008',
    'j42000014', 'j420000105', 'j420000106', 'j420000110', 'j420000118', 'j43',
    'j430000001', 'j430000002', 'j430000003', 'j430000005', 'j430000006',
    'j430000007', 'j430000008', 'j430000009', 'j430000010', 'j430000011', 'j44',
    'j45', 'j450000008', 'j450000014', 'j450000101', 'j450000102', 'j450000104',
    'j450000105', 'j450000106', 'j46', 'j47', 'j48', 'j49', 'j5', 'j50', 'j501',
    'j502', 'j503', 'j504', 'j505', 'j506', 'j508', 'j51', 'j512', 'j515',
    'j516', 'j517', 'j518', 'j519', 'j52', 'j528', 'j53', 'j530', 'j54', 'j56',
    'j57', 'j58', 'j583', 'j584', 'j585', 'j586', 'j587', 'j588', 'j589', 'j59',
    'j590', 'j592', 'j593', 'j594', 'j6', 'j60', 'j604', 'j605', 'j61', 'j611',
    'j612', 'j62', 'j623', 'j63', 'j65', 'j650000002', 'j650000004', 'j660',
    'j661', 'j662', 'j663', 'j664', 'j665', 'j666', 'j667', 'j668', 'j67', 'j68',
    'j69', 'j7', 'j70', 'j71', 'j72', 'j73', 'j74', 'j75', 'j76', 'j77', 'j8',
    'j80', 'j80000001', 'j80000002', 'j80000003', 'j80000004', 'j80000006',
    'j80000007', 'j80000008', 'j80000009', 'j80000010', 'j80000011', 'j80000012',
    'j80000013', 'j80000014', 'j80000016', 'j80000102', 'j80000103', 'j80001020',
    'j81', 'j82', 'j83', 'j84', 'j85', 'j86', 'j87', 'j88', 'j89', 'j9', 'j90',
    'j90000001', 'j90000002', 'j90000003', 'j90000004', 'j90000005', 'j90000006',
    'j90000007', 'j90000008', 'j90000009', 'j90000010', 'j90000011', 'j90000012',
    'j90000013', 'j90000014', 'j90000015', 'j90000016', 'j90000018', 'j90000019',
    'j90000020', 'j90000031', 'j90000032', 'j90000034', 'j90000038', 'j90000040',
    'j90000063', 'j90000068', 'j90000076', 'j90000087', 'j90000088', 'j90000089',
    'j90000092', 'j90000093', 'j90000095', 'j90000096', 'j90000097', 'j90000098',
    'j90000102', 'j90000104', 'j90000106', 'j90000109', 'j90000110', 'j90000111',
    'j90000114', 'j90000115', 'j90001005', 'j90001006', 'j90001007', 'j90001008',
    'j90001010', 'j90001011', 'j90001028', 'j90001029', 'j90001030', 'j90001033',
    'j90001037', 'j90001040', 'j90001047', 'j90001053', 'j90001054', 'j90001055',
    'j92', 'j93', 'j94', 'j95', 'j97',
    'pdf', 'xlsx', 'xls', 'docx', 'doc', 'csv', 'txt', 'ppt', 'pptx',
    'ideacon', 'dwg', 'dxf', 'ifc'
}


def _allowed_file(filename):
    """Función auxiliar para verificar si la extensión de un archivo es válida."""
    if '.' not in filename or filename.startswith('.'):
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def upload_file(conexion_id, user_id, file, tipo_archivo):
    """
    Sube un archivo, lo guarda en el sistema de archivos y crea un registro en la BD.
    Retorna (True, mensaje_exito) o (False, mensaje_error).
    """
    dal = SQLiteDAL()
    if not file or not file.filename:
        return False, 'No se seleccionó ningún archivo.'

    if not _allowed_file(file.filename):
        return False, 'Tipo de archivo no permitido.'

    try:
        filename = secure_filename(file.filename)
        upload_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], str(conexion_id))
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))

        dal.create_archivo(conexion_id, user_id, tipo_archivo, filename)
        log_action('SUBIR_ARCHIVO', user_id, 'archivos', conexion_id,
                   f"Archivo '{filename}' ({tipo_archivo}) subido.")
        return True, f"Archivo '{tipo_archivo}' subido con éxito."
    except Exception as e:
        current_app.logger.error(
            f"Error al subir archivo para conexión {conexion_id}: {e}", exc_info=True)
        return False, "Ocurrió un error interno al subir el archivo."


def get_file_for_download(conexion_id, filename, user_id):
    """
    Verifica si un archivo existe en la BD para la conexión dada y registra la descarga.
    Retorna la ruta del directorio si es válido, si no, aborta.
    """
    dal = SQLiteDAL()
    archivo_db = dal.get_archivo_by_name(conexion_id, filename)

    if not archivo_db:
        abort(404, description="El archivo no existe o no está asociado a esta conexión.")

    log_action('DESCARGAR_ARCHIVO', user_id, 'archivos',
               conexion_id, f"Archivo '{filename}' descargado.")
    directory = os.path.join(
        current_app.config['UPLOAD_FOLDER'], str(conexion_id))
    return directory


def delete_file(conexion_id, archivo_id, current_user, user_roles):
    """
    Elimina un archivo del sistema de archivos y de la base de datos.
    Realiza comprobaciones de permisos.
    Retorna (True, mensaje_exito) o (False, mensaje_error).
    """
    dal = SQLiteDAL()
    archivo = dal.get_archivo(archivo_id, conexion_id)

    if not archivo:
        return False, 'El archivo no existe.'

    conexion = dal.get_conexion(conexion_id)
    if not conexion:
        return False, 'La conexión asociada no existe.'

    is_admin = 'ADMINISTRADOR' in user_roles
    is_owner = current_user['id'] == archivo['usuario_id']
    is_realizador = current_user['id'] == conexion['realizador_id']

    if not (is_admin or is_owner or is_realizador):
        return False, 'No tienes permiso para eliminar este archivo.'

    try:
        # Eliminar de la base de datos primero
        dal.delete_archivo(archivo_id)

        # Eliminar del sistema de archivos
        safe_filename = secure_filename(archivo['nombre_archivo'])
        file_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], str(conexion_id), safe_filename)

        if os.path.exists(file_path):
            os.remove(file_path)

        log_action('ELIMINAR_ARCHIVO', current_user['id'], 'archivos', archivo_id,
                   f"Archivo '{archivo['nombre_archivo']}' eliminado de la conexión {conexion_id}.")
        return True, 'Archivo eliminado con éxito.'
    except Exception as e:
        current_app.logger.error(
            f"Error al eliminar archivo {archivo_id}: {e}", exc_info=True)
        # Podríamos considerar revertir la eliminación de la BD aquí si la eliminación del archivo falla.
        return False, 'Ocurrió un error interno al eliminar el archivo.'

import io
import csv
import json
from datetime import datetime
import pandas as pd
from weasyprint import HTML
from flask import render_template, current_app
from flask_mail import Message
from extensions import mail
from dal.sqlite_dal import SQLiteDAL
from db import log_action

def get_all_reports():
    dal = SQLiteDAL()
    return dal.get_all_reports()

def get_report_for_edit(reporte_id):
    dal = SQLiteDAL()
    return dal.get_report(reporte_id)

def create_report(form, user_id):
    dal = SQLiteDAL()
    filtros = {
        'proyecto_id': form.proyecto_id.data,
        'estado': form.estado.data,
        'realizador_id': form.realizador_id.data,
        'fecha_inicio': form.fecha_inicio.data.strftime('%Y-%m-%d') if form.fecha_inicio.data else None,
        'fecha_fin': form.fecha_fin.data.strftime('%Y-%m-%d') if form.fecha_fin.data else None,
        'columnas': form.columnas.data,
        'output_format': form.output_format.data
    }

    try:
        report_id = dal.create_report(
            form.nombre.data,
            form.descripcion.data,
            user_id,
            json.dumps(filtros),
            form.programado.data,
            form.frecuencia.data,
            form.destinatarios.data
        )

        if form.programado.data:
            schedule_report_job(report_id, form.nombre.data, form.frecuencia.data)

        log_action('CREAR_REPORTE', user_id, 'reportes', report_id, f"Reporte '{form.nombre.data}' creado.")
        return True, 'Reporte guardado con éxito.'
    except Exception as e:
        # log error e
        return False, 'Ocurrió un error al crear el reporte.'

def update_report(reporte_id, form):
    dal = SQLiteDAL()
    filtros = {
        'proyecto_id': form.proyecto_id.data,
        'estado': form.estado.data,
        'realizador_id': form.realizador_id.data,
        'fecha_inicio': form.fecha_inicio.data.strftime('%Y-%m-%d') if form.fecha_inicio.data else None,
        'fecha_fin': form.fecha_fin.data.strftime('%Y-%m-%d') if form.fecha_fin.data else None,
        'columnas': form.columnas.data,
        'output_format': form.output_format.data
    }

    try:
        dal.update_report(
            reporte_id,
            form.nombre.data,
            form.descripcion.data,
            json.dumps(filtros),
            form.programado.data,
            form.frecuencia.data,
            form.destinatarios.data
        )

        job_id = f"report_{reporte_id}"
        if form.programado.data:
            schedule_report_job(reporte_id, form.nombre.data, form.frecuencia.data)
        else:
            if current_app.scheduler.get_job(job_id):
                current_app.scheduler.remove_job(job_id)

        log_action('EDITAR_REPORTE', g.user['id'], 'reportes', reporte_id, f"Reporte '{form.nombre.data}' editado.")
        return True, 'Reporte actualizado con éxito.'
    except Exception as e:
        # log error e
        return False, 'Ocurrió un error al actualizar el reporte.'

def delete_report(reporte_id, user_id):
    dal = SQLiteDAL()
    reporte = dal.get_report(reporte_id)
    if not reporte:
        return False, "El reporte no fue encontrado."

    job_id = f"report_{reporte_id}"
    if current_app.scheduler.get_job(job_id):
        try:
            current_app.scheduler.remove_job(job_id)
        except Exception as e:
            current_app.logger.error(f"Error al desprogramar el job '{job_id}': {e}", exc_info=True)

    try:
        dal.delete_report(reporte_id)
        log_action('ELIMINAR_REPORTE', user_id, 'reportes', reporte_id, f"El reporte '{reporte['nombre']}' ha sido eliminado.")
        return True, f"El reporte '{reporte['nombre']}' ha sido eliminado."
    except Exception as e:
        return False, "Ocurrió un error al eliminar el reporte."


def run_report(reporte_id, user_id):
    filename, mimetype, file_content, _ = _generate_report_data_and_file(reporte_id, current_app.app_context())
    if not file_content:
        return None, None, None, "No se pudo generar el reporte. Verifique la configuración o los datos."

    dal = SQLiteDAL()
    reporte = dal.get_report(reporte_id)
    log_action('EJECUTAR_REPORTE', user_id, 'reportes', reporte_id, f"Reporte '{reporte['nombre']}' ejecutado y descargado.")
    return filename, mimetype, file_content, f"Reporte '{reporte['nombre']}' ejecutado y descargado."


def schedule_report_job(reporte_id, nombre_reporte, frecuencia):
    job_id = f"report_{reporte_id}"
    interval_map = {
        'diaria': {'days': 1},
        'semanal': {'weeks': 1},
        'mensual': {'months': 1}
    }
    if frecuencia in interval_map:
        try:
            current_app.scheduler.add_job(
                id=job_id,
                func='services.report_service:scheduled_report_job',
                trigger='interval',
                **interval_map[frecuencia],
                args=[reporte_id],
                replace_existing=True
            )
            current_app.logger.info(f"Reporte '{nombre_reporte}' (ID: {reporte_id}) programado con éxito.")
        except Exception as e:
            current_app.logger.error(f"Error al programar el reporte '{nombre_reporte}': {e}", exc_info=True)
            raise e

def scheduled_report_job(reporte_id):
    with current_app.app_context():
        dal = SQLiteDAL()
        reporte = dal.get_report(reporte_id)
        if not reporte or not reporte['programado'] or not reporte['destinatarios']:
            current_app.logger.warning(f"Tarea programada para reporte ID {reporte_id} no ejecutada.")
            return

        recipients = [email.strip() for email in reporte['destinatarios'].split(',') if email.strip()]
        if not recipients:
            return

        filename, mimetype, file_content, preview_results = _generate_report_data_and_file(reporte_id, current_app.app_context())
        if file_content:
            try:
                subject = f"Reporte Programado: {reporte['nombre']} ({datetime.now().strftime('%Y-%m-%d')})"
                msg = Message(subject, recipients=recipients)
                msg.html = render_template('email/reporte_programado.html', reporte={'nombre': reporte['nombre']}, resultados=preview_results, now=datetime.now)
                msg.attach(filename, mimetype, file_content)
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f"Error al enviar reporte programado '{reporte['nombre']}': {e}", exc_info=True)

def _generate_report_data_and_file(reporte_id, app_context):
    with app_context:
        dal = SQLiteDAL()
        reporte = dal.get_report(reporte_id)
        if not reporte:
            return None, None, None, None

        try:
            filtros = json.loads(reporte['filtros'])
        except json.JSONDecodeError:
            return None, None, None, None

        columnas_seleccionadas_input = filtros.get('columnas', [])
        output_format = filtros.get('output_format', 'csv')

        allowed_columns = [
            'id', 'codigo_conexion', 'proyecto_id', 'proyecto_nombre', 'tipo',
            'subtipo', 'tipologia', 'descripcion', 'detalles_json', 'estado',
            'solicitante_id', 'solicitante_nombre', 'realizador_id', 'realizador_nombre',
            'aprobador_id', 'aprobador_nombre', 'fecha_creacion', 'fecha_modificacion',
            'detalles_rechazo'
        ]
        columnas_seleccionadas = [col for col in columnas_seleccionadas_input if col in allowed_columns]
        if not columnas_seleccionadas:
            return None, None, None, None

        resultados_raw = dal.get_report_data(filtros, columnas_seleccionadas)
        preview_results = [dict(row) for row in resultados_raw[:10]]
        resultados_dicts = [dict(row) for row in resultados_raw]

        filename_base = f"reporte_{reporte['nombre'].replace(' ', '_').lower()}"
        file_content = None
        mimetype = None
        filename = None

        if output_format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columnas_seleccionadas)
            for row in resultados_dicts:
                writer.writerow([row[col] for col in columnas_seleccionadas])
            file_content = output.getvalue().encode('utf-8')
            mimetype = "text/csv"
            filename = f"{filename_base}.csv"
        elif output_format == 'xlsx':
            df = pd.DataFrame(resultados_dicts, columns=columnas_seleccionadas)
            output = io.BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            file_content = output.getvalue()
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{filename_base}.xlsx"
        elif output_format == 'pdf':
            html = render_template('email/reporte_programado.html', reporte=reporte, resultados=resultados_dicts, now=datetime.now)
            pdf_bytes = HTML(string=html).write_pdf()
            file_content = pdf_bytes
            mimetype = "application/pdf"
            filename = f"{filename_base}.pdf"

        dal.update_report_last_execution(reporte_id)
        return filename, mimetype, file_content, preview_results

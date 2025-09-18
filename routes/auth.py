import json
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db, log_action
from . import roles_required
from forms import LoginForm, ProfileForm
from dal.sqlite_dal import SQLiteDAL

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
dal = SQLiteDAL()

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        error = None
        user = dal.get_user_by_username(form.username.data)

        # Mitigación de enumeración de usuarios
        password_hash_to_check = user['password_hash'] if user else generate_password_hash("dummy_password_for_timing_attack_mitigation")

        if user is None or not user['activo'] or not check_password_hash(password_hash_to_check, form.password.data):
            error = 'Nombre de usuario o contraseña incorrectos.'

        if error is None and user:
            session.clear()
            session['user_id'] = user['id']
            log_action('INICIAR_SESION', user['id'], 'usuarios', user['id'], f"Inicio de sesión exitoso para el usuario '{form.username.data}'.")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))

        flash(error, 'danger')
        # No registrar el nombre de usuario en intentos fallidos para mayor seguridad
        log_action('INTENTO_FALLIDO_SESION', None, 'usuarios', None, f"Intento de inicio de sesión fallido desde IP: {request.remote_addr}.")

    return render_template('login.html', form=form, titulo="Iniciar Sesión")

@auth_bp.route('/logout')
def logout():
    username = g.user['username'] if g.user else 'desconocido'
    user_id = g.user['id'] if g.user else None
    session.clear()
    log_action('CERRAR_SESION', user_id, 'usuarios', user_id, f"Cierre de sesión para el usuario '{username}'.")
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def perfil():
    form = ProfileForm()
    db = get_db()

    if form.validate_on_submit():
        try:
            changes = {}
            # Actualizar datos del usuario
            if form.nombre_completo.data != g.user['nombre_completo'] or form.email.data != g.user['email']:
                dal.update_user_profile(g.user['id'], form.nombre_completo.data, form.email.data)
                if form.nombre_completo.data != g.user['nombre_completo']:
                    changes['nombre_completo'] = {'old': g.user['nombre_completo'], 'new': form.nombre_completo.data}
                if form.email.data != g.user['email']:
                    changes['email'] = {'old': g.user['email'], 'new': form.email.data}

            # Actualizar contraseña si se proporcionó
            if form.new_password.data:
                password_hash = generate_password_hash(form.new_password.data)
                dal.update_user_password(g.user['id'], password_hash)
                changes['password'] = 'changed'

            # Actualizar preferencias de notificación
            user_prefs = dal.get_notification_preferences(g.user['id'])
            initial_email_notif_estado = user_prefs['email_notif_estado'] if user_prefs else True
            if initial_email_notif_estado != form.email_notif_estado.data:
                dal.upsert_notification_preferences(g.user['id'], form.email_notif_estado.data)
                changes['email_notif_estado'] = {'old': initial_email_notif_estado, 'new': form.email_notif_estado.data}

            db.commit()

            if changes:
                log_action('ACTUALIZAR_PERFIL', g.user['id'], 'usuarios', g.user['id'], f"Perfil y preferencias actualizados. Cambios: {json.dumps(changes)}")
            flash('Perfil y preferencias actualizados con éxito.', 'success')

            return redirect(url_for('auth.perfil'))
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Error al actualizar el perfil del usuario {g.user['id']}: {e}")
            flash('Ocurrió un error al actualizar el perfil.', 'danger')

    elif request.method == 'GET':
        form.nombre_completo.data = g.user['nombre_completo']
        form.email.data = g.user['email']
        user_prefs = dal.get_notification_preferences(g.user['id'])
        form.email_notif_estado.data = user_prefs['email_notif_estado'] if user_prefs else True

    return render_template('perfil.html', titulo="Mi Perfil", form=form)
import json
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db, log_action
from . import roles_required
from forms import LoginForm, ProfileForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        db = get_db()
        cursor = db.cursor()
        error = None
        
        try:
            user_sql = 'SELECT * FROM usuarios WHERE username = ?'
            cursor.execute(user_sql, (form.username.data,))
            user = cursor.fetchone()

            if user is None or not user['activo'] or not check_password_hash(user['password_hash'], form.password.data):
                error = 'Nombre de usuario o contraseña incorrectos.'

            if error is None:
                session.clear()
                session['user_id'] = user['id']
                log_action('INICIAR_SESION', user['id'], 'usuarios', user['id'], f"Inicio de sesión exitoso para el usuario '{form.username.data}'.")
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))

            flash(error, 'danger')
            log_action('INTENTO_FALLIDO_SESION', None, 'usuarios', None, f"Intento de inicio de sesión fallido para el usuario '{form.username.data}'.")
        finally:
            cursor.close()

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
    cursor = db.cursor()

    try:
        if form.validate_on_submit():
            # Iniciar transacción
            changes = {}

            # Actualizar datos del usuario
            sql_update_user = "UPDATE usuarios SET nombre_completo = ?, email = ? WHERE id = ?"
            cursor.execute(sql_update_user, (form.nombre_completo.data, form.email.data, g.user['id']))
            if form.nombre_completo.data != g.user['nombre_completo']: changes['nombre_completo'] = {'old': g.user['nombre_completo'], 'new': form.nombre_completo.data}
            if form.email.data != g.user['email']: changes['email'] = {'old': g.user['email'], 'new': form.email.data}

            # Actualizar contraseña si se proporcionó
            if form.new_password.data:
                password_hash = generate_password_hash(form.new_password.data)
                sql_update_pass = "UPDATE usuarios SET password_hash = ? WHERE id = ?"
                cursor.execute(sql_update_pass, (password_hash, g.user['id']))
                changes['password'] = 'changed'

            # Actualizar preferencias de notificación
            sql_get_prefs = "SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = ?"
            cursor.execute(sql_get_prefs, (g.user['id'],))
            user_prefs = cursor.fetchone()
            initial_email_notif_estado = user_prefs['email_notif_estado'] if user_prefs else True

            sql_upsert_prefs = "INSERT INTO preferencias_notificaciones (usuario_id, email_notif_estado) VALUES (?, ?) ON CONFLICT (usuario_id) DO UPDATE SET email_notif_estado = excluded.email_notif_estado"
            cursor.execute(sql_upsert_prefs, (g.user['id'], form.email_notif_estado.data))

            if initial_email_notif_estado != form.email_notif_estado.data:
                changes['email_notif_estado'] = {'old': initial_email_notif_estado, 'new': form.email_notif_estado.data}

            db.commit()

            if changes:
                log_action('ACTUALIZAR_PERFIL', g.user['id'], 'usuarios', g.user['id'], f"Perfil y preferencias actualizados. Cambios: {json.dumps(changes)}")
            flash('Perfil y preferencias actualizados con éxito.', 'success')

            # No es necesario refrescar g.user aquí, se hará en la próxima solicitud
            return redirect(url_for('auth.perfil'))

        elif request.method == 'GET':
            form.nombre_completo.data = g.user['nombre_completo']
            form.email.data = g.user['email']
            sql_get_prefs = "SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = ?"
            cursor.execute(sql_get_prefs, (g.user['id'],))
            user_prefs = cursor.fetchone()
            form.email_notif_estado.data = user_prefs['email_notif_estado'] if user_prefs else True
    finally:
        cursor.close()

    return render_template('perfil.html', titulo="Mi Perfil", form=form)
import json
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db, log_action
from . import roles_required
from forms import LoginForm, ProfileForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def _is_testing():
    return current_app.config.get('TESTING', False)

def _get_placeholder():
    return "?" if _is_testing() else "%s"

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        db = get_db()
        p = _get_placeholder()
        error = None
        
        user_sql = f'SELECT * FROM usuarios WHERE username = {p}'
        user = db.execute(user_sql, (username,)).fetchone()

        if user is None:
            error = 'Nombre de usuario o contraseña incorrectos.'
        elif not user['activo']:
            # Security fix: Generic error message to prevent user enumeration
            error = 'Nombre de usuario o contraseña incorrectos.'
        elif not check_password_hash(user['password_hash'], password):
            error = 'Nombre de usuario o contraseña incorrectos.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            log_action('INICIAR_SESION', user['id'], 'usuarios', user['id'], 
                       f"Inicio de sesión exitoso para el usuario '{username}'.")
            current_app.logger.info(f"Usuario '{username}' ha iniciado sesión exitosamente.")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))

        flash(error, 'danger')
        log_action('INTENTO_FALLIDO_SESION', None, 'usuarios', None, 
                   f"Intento de inicio de sesión fallido para el usuario '{username}'.")
    return render_template('login.html', form=form, titulo="Iniciar Sesión")


@auth_bp.route('/logout')
def logout():
    username = g.user['username'] if g.user else 'desconocido'
    user_id = g.user['id'] if g.user else None
    session.clear()
    log_action('CERRAR_SESION', user_id, 'usuarios', user_id, 
               f"Cierre de sesión para el usuario '{username}'.")
    flash('Has cerrado la sesión.', 'info')
    current_app.logger.info(f"Usuario '{username}' ha cerrado sesión.")
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def perfil():
    db = get_db()
    p = _get_placeholder()
    form = ProfileForm()
    
    if form.validate_on_submit():
        old_data_sql = f"SELECT nombre_completo, email FROM usuarios WHERE id = {p}"
        old_data = db.execute(old_data_sql, (g.user['id'],)).fetchone()

        update_user_sql = f"UPDATE usuarios SET nombre_completo = {p}, email = {p} WHERE id = {p}"
        db.execute(update_user_sql, (form.nombre_completo.data, form.email.data, g.user['id']))

        changes = {}
        if form.nombre_completo.data != old_data['nombre_completo']:
            changes['nombre_completo'] = {'old': old_data['nombre_completo'], 'new': form.nombre_completo.data}
        if form.email.data != old_data['email']:
            changes['email'] = {'old': old_data['email'], 'new': form.email.data}

        if form.new_password.data:
            password_hash = generate_password_hash(form.new_password.data)
            update_pass_sql = f"UPDATE usuarios SET password_hash = {p} WHERE id = {p}"
            db.execute(update_pass_sql, (password_hash, g.user['id']))
            changes['password'] = 'changed'

        prefs_sql = f"SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = {p}"
        user_prefs = db.execute(prefs_sql, (g.user['id'],)).fetchone()
        initial_email_notif_estado = user_prefs['email_notif_estado'] if user_prefs else True

        if _is_testing():
            insert_or_replace_sql = f"INSERT OR REPLACE INTO preferencias_notificaciones (usuario_id, email_notif_estado) VALUES ({p}, {p})"
        else:
            insert_or_replace_sql = "INSERT INTO preferencias_notificaciones (usuario_id, email_notif_estado) VALUES (%s, %s) ON CONFLICT (usuario_id) DO UPDATE SET email_notif_estado = EXCLUDED.email_notif_estado"

        db.execute(insert_or_replace_sql, (g.user['id'], form.email_notif_estado.data))

        if initial_email_notif_estado != form.email_notif_estado.data:
            changes['email_notif_estado'] = {'old': initial_email_notif_estado, 'new': form.email_notif_estado.data}

        db.commit()

        if changes:
            log_action('ACTUALIZAR_PERFIL', g.user['id'], 'usuarios', g.user['id'],
                       f"Perfil y preferencias actualizados. Cambios: {json.dumps(changes)}")

        flash('Perfil y preferencias actualizados con éxito.', 'success')

        # Refresh user data in g
        g.user = dict(db.execute(f"SELECT * FROM usuarios WHERE id = {p}", (g.user['id'],)).fetchone())

        return redirect(url_for('auth.perfil'))
    elif request.method == 'GET':
        form.nombre_completo.data = g.user['nombre_completo']
        form.email.data = g.user['email']
        user_prefs_sql = f"SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = {p}"
        user_prefs = db.execute(user_prefs_sql, (g.user['id'],)).fetchone()
        form.email_notif_estado.data = user_prefs['email_notif_estado'] if user_prefs else True

    return render_template('perfil.html', titulo="Mi Perfil", form=form)
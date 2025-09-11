# Hepta_Conexiones/routes/auth.py
import json
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash

# Se importa el módulo de base de datos y los formularios necesarios.
from db import get_db, log_action
from . import roles_required
from forms import LoginForm, ProfileForm

# Se define el Blueprint para agrupar todas las rutas de autenticación.
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    """
    Gestiona el inicio de sesión del usuario.
    Si la solicitud es GET, muestra el formulario de login.
    Si es POST, valida las credenciales y crea una sesión para el usuario.
    """
    # Si el usuario ya ha iniciado sesión, se le redirige al dashboard.
    if g.user:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()

    # Se utiliza el método validate_on_submit() de WTForms para procesar el formulario.
    # Este método comprueba si la solicitud es un POST y si los datos son válidos.
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        db = get_db()
        error = None
        
        user = db.execute(
            'SELECT * FROM usuarios WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Nombre de usuario o contraseña incorrectos.'
        elif not user['activo']:
            error = 'Esta cuenta ha sido desactivada. Contacta a un administrador.'
        elif not check_password_hash(user['password_hash'], password):
            error = 'Nombre de usuario o contraseña incorrectos.'

        if error is None:
            # Si las credenciales son válidas, se inicia una nueva sesión.
            session.clear()
            session['user_id'] = user['id']
            log_action('INICIAR_SESION', user['id'], 'usuarios', user['id'], 
                       f"Inicio de sesión exitoso para el usuario '{username}'.")
            current_app.logger.info(f"Usuario '{username}' ha iniciado sesión exitosamente.")
            # Redirige a la página que el usuario intentaba visitar, o al dashboard.
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))

        flash(error, 'danger')
        log_action('INTENTO_FALLIDO_SESION', None, 'usuarios', None, 
                   f"Intento de inicio de sesión fallido para el usuario '{username}'.")
    return render_template('login.html', form=form, titulo="Iniciar Sesión")


@auth_bp.route('/logout')
def logout():
    """
    Cierra la sesión del usuario actual.
    Limpia la sesión y redirige al usuario a la página de login.
    """
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
    """
    Permite al usuario ver y actualizar su propio perfil (nombre completo y contraseña)
    y sus preferencias de notificación.
    """
    db = get_db()
    form = ProfileForm()
    
    if form.validate_on_submit():
        # Toda la validación, incluida la de la contraseña, ahora se maneja en ProfileForm.
        # Simplemente procesamos la actualización si el formulario es válido.
        old_data = db.execute('SELECT nombre_completo, email FROM usuarios WHERE id = ?', (g.user['id'],)).fetchone()
        db.execute('UPDATE usuarios SET nombre_completo = ?, email = ? WHERE id = ?',
                   (form.nombre_completo.data, form.email.data, g.user['id']))
        changes = {}
        if form.nombre_completo.data != old_data['nombre_completo']:
            changes['nombre_completo'] = {'old': old_data['nombre_completo'], 'new': form.nombre_completo.data}
        if form.email.data != old_data['email']:
            changes['email'] = {'old': old_data['email'], 'new': form.email.data}

        # Solo actualizamos la contraseña si se proporcionó una nueva (y ya fue validada).
        if form.new_password.data:
            password_hash = generate_password_hash(form.new_password.data)
            db.execute('UPDATE usuarios SET password_hash = ? WHERE id = ?', (password_hash, g.user['id']))
            changes['password'] = 'changed'

        user_prefs = db.execute('SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = ?', (g.user['id'],)).fetchone()
        initial_email_notif_estado = user_prefs['email_notif_estado'] if user_prefs else True

        db.execute(
            'INSERT OR REPLACE INTO preferencias_notificaciones (usuario_id, email_notif_estado) VALUES (?, ?)',
            (g.user['id'], form.email_notif_estado.data)
        )
        if initial_email_notif_estado != form.email_notif_estado.data:
            changes['email_notif_estado'] = {'old': initial_email_notif_estado, 'new': form.email_notif_estado.data}

        db.commit()

        if changes:
            log_action('ACTUALIZAR_PERFIL', g.user['id'], 'usuarios', g.user['id'],
                       f"Perfil y preferencias actualizados. Cambios: {json.dumps(changes)}")
        current_app.logger.info(f"Usuario '{g.user['username']}' actualizó su perfil y preferencias.")
        flash('Perfil y preferencias actualizados con éxito.', 'success')

        # Actualizar g.user para reflejar los cambios inmediatamente en la misma solicitud.
        g.user = dict(db.execute('SELECT * FROM usuarios WHERE id = ?', (g.user['id'],)).fetchone())

        return redirect(url_for('auth.perfil'))
    elif request.method == 'GET':
        form.nombre_completo.data = g.user['nombre_completo']
        form.email.data = g.user['email']
        user_prefs = db.execute('SELECT email_notif_estado FROM preferencias_notificaciones WHERE usuario_id = ?', (g.user['id'],)).fetchone()
        form.email_notif_estado.data = user_prefs['email_notif_estado'] if user_prefs else True

    return render_template('perfil.html', titulo="Mi Perfil", form=form)
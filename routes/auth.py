from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db
from models import Usuario, PreferenciaNotificacion
from forms import LoginForm, ProfileForm
from db import log_action
from . import roles_required

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(username=form.username.data).first()
        error = None
        if user is None:
            error = 'Nombre de usuario o contraseña incorrectos.'
        elif not user.activo:
            error = 'Tu cuenta ha sido desactivada. Contacta a un administrador.'
        elif not check_password_hash(user.password_hash, form.password.data):
            error = 'Nombre de usuario o contraseña incorrectos.'

        if error is None:
            session.clear()
            session['user_id'] = user.id
            log_action('INICIAR_SESION', user.id, 'usuarios', user.id, "Inicio de sesión exitoso.")
            return redirect(request.args.get('next') or url_for('main.dashboard'))

        flash(error, 'danger')
    return render_template('login.html', form=form, titulo="Iniciar Sesión")

@auth_bp.route('/logout')
def logout():
    log_action('CERRAR_SESION', g.user.id if g.user else None, 'usuarios', g.user.id if g.user else None, "Cierre de sesión.")
    session.clear()
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil', methods=('GET', 'POST'))
@roles_required('ADMINISTRADOR', 'APROBADOR', 'REALIZADOR', 'SOLICITANTE')
def perfil():
    form = ProfileForm(obj=g.user)
    if form.validate_on_submit():
        user = g.user
        user.nombre_completo = form.nombre_completo.data
        user.email = form.email.data
        if form.new_password.data:
            user.password_hash = generate_password_hash(form.new_password.data)

        prefs = g.user.preferencias_notificacion or PreferenciaNotificacion(usuario_id=g.user.id)
        prefs.email_notif_estado = form.email_notif_estado.data
        db.session.add(prefs)

        db.session.commit()
        log_action('ACTUALIZAR_PERFIL', g.user.id, 'usuarios', g.user.id, "Perfil actualizado.")
        flash('Perfil actualizado con éxito.', 'success')
        return redirect(url_for('auth.perfil'))

    if request.method == 'GET' and g.user.preferencias_notificacion:
        form.email_notif_estado.data = g.user.preferencias_notificacion.email_notif_estado

    return render_template('perfil.html', titulo="Mi Perfil", form=form)

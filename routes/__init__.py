"""
routes/__init__.py

Este archivo inicializa el paquete 'routes' de Python y define decoradores
personalizados que se utilizarán en toda la aplicación para gestionar
la autenticación y la autorización.
"""

from functools import wraps
from flask import g, request, redirect, url_for, flash, session, abort


def roles_required(*roles):
    """
    Decorador personalizado para restringir el acceso a rutas basadas en los roles del usuario.

    Un decorador en Python es una función que toma otra función y extiende su
    comportamiento sin modificarla explícitamente. Este decorador se usa para
    proteger las rutas y asegurar que solo los usuarios con los roles correctos
    puedan acceder a ellas.

    Ejemplo de uso:
    @app.route('/admin-only')
    @roles_required('ADMINISTRADOR')
    def admin_page():
        return 'Esta es una página solo para administradores.'

    Args:
        *roles: Una lista de nombres de roles como strings que están permitidos
                para acceder a la ruta.

    Returns:
        La función de la vista si el usuario tiene el rol requerido, o aborta
        con un error 403 (Prohibido) si no lo tiene.
    """
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verificar si hay un usuario autenticado.
            # 'g.user' se establece en el hook 'before_request' en app.py.
            # Si no hay usuario, se le redirige a la página de login.
            if g.user is None:
                flash("Debes iniciar sesión para acceder a esta página.", "warning")
                return redirect(url_for('auth.login', next=request.url))

            # 2. Obtener los roles del usuario de la sesión.
            # Esto es más eficiente que consultar la base de datos en cada solicitud.
            user_roles = set(session.get('user_roles', []))

            # 3. Comprobar si el usuario tiene al menos uno de los roles requeridos.
            # Se convierte la lista de roles requeridos a un conjunto para una comparación eficiente.
            required_roles = set(roles)

            # .isdisjoint() devuelve True si los dos conjuntos no tienen elementos en común.
            # Si no tienen elementos en común, significa que el usuario no tiene ninguno de los roles requeridos.
            if required_roles.isdisjoint(user_roles):
                # Si el usuario no tiene los permisos, se aborta la solicitud con un error 403.
                # Esto activará el manejador de errores @errorhandler(403) en app.py,
                # que mostrará la página de error personalizada.
                abort(403)

            # 4. Si el usuario está autenticado y tiene el rol correcto, se le permite
            #    acceder a la función de la vista original.
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

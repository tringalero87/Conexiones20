from db import get_db
from werkzeug.security import generate_password_hash


def test_profile_update_rejects_duplicate_email(client, app, auth):
    """
    Tests that a user cannot update their profile with an email that
    is already in use by another user.
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Create user1 (will be logged in) and user2 (has the target email)
        password_hash = generate_password_hash('password')
        # user1 is created by the conftest auth fixture ('admin')
        # user2
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, email, activo) VALUES (?, ?, ?, ?, ?)",
            ('user2', password_hash, 'User Two', 'user2@example.com', 1)
        )
        db.commit()

    # Log in as the first user ('admin' from conftest)
    auth.login('admin', 'password')

    # Attempt to change email to user2's email
    response = client.post('/auth/perfil', data={
        'nombre_completo': 'Admin User Updated',
        'email': 'user2@example.com',  # This email is already taken
        'current_password': '',
        'new_password': '',
        'confirm_password': ''
    }, follow_redirects=True)

    # The buggy code will crash with an IntegrityError (500).
    # A robust test would check for that, but for simplicity, we'll check
    # that the expected validation message is NOT present.
    # The fixed code will show a validation error message.

    # This assertion will pass with the buggy code, and fail after the fix
    # if we check for the error message. Let's write it for the fixed behavior.
    assert b'Este correo electr\xc3\xb3nico ya est\xc3\xa1 registrado.' in response.data

    # And check that the email was not actually updated
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT email FROM usuarios WHERE username = 'admin'")
        user1 = cursor.fetchone()
        assert user1['email'] == 'admin@test.com'


def test_profile_password_change_wrong_current_password(client, auth):
    """
    Tests that changing a password with an incorrect current password
    fails and shows a form validation error.
    """
    auth.login('admin', 'password')

    response = client.post('/auth/perfil', data={
        'nombre_completo': 'Admin User',
        'email': 'admin@test.com',
        'current_password': 'wrongpassword',
        'new_password': 'newpassword',
        'confirm_password': 'newpassword',
        'email_notif_estado': 'y'
    })  # No longer following redirects to inspect the form response

    assert response.status_code == 200
    # Check for the form-level validation error message
    assert b'La contrase\xc3\xb1a actual no es correcta.' in response.data
    # Ensure it's not a flashed message by checking for the absence of the alert div
    with client.session_transaction() as session:
        flashes = session.get('_flashes', [])
        assert not any(
            'La contraseña actual no es correcta.' in msg for cat, msg in flashes)

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectMultipleField, TextAreaField, IntegerField, SelectField, RadioField, widgets
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange, ValidationError
import re

class LoginForm(FlaskForm):
    """
    Formulario para el inicio de sesión de usuarios.
    Se utiliza en la página de login para autenticar a los usuarios. Define los campos
    básicos de usuario y contraseña como obligatorios.
    """
    username = StringField('Usuario',
        validators=[DataRequired(message="El nombre de usuario es obligatorio.")],
        render_kw={"placeholder": "Ej: j.perez"})

    password = PasswordField('Contraseña',
        validators=[DataRequired(message="La contraseña es obligatoria.")],
        render_kw={"placeholder": "Ingresa tu contraseña"})

    submit = SubmitField('Iniciar Sesión')

class ProjectForm(FlaskForm):
    """
    Formulario para crear y editar proyectos.
    Utilizado por los administradores para gestionar los proyectos en el sistema.
    """
    nombre = StringField(
        'Nombre del Proyecto',
        validators=[
            DataRequired(message="El nombre del proyecto es obligatorio."),
            Length(min=3, max=100, message="El nombre debe tener entre 3 y 100 caracteres.")
        ],
        render_kw={"placeholder": "Ej: Remodelación Edificio Central"}
    )
    descripcion = TextAreaField(
        'Descripción (opcional)',
        render_kw={"rows": 4, "placeholder": "Añade una breve descripción del alcance del proyecto..."}
    )
    submit = SubmitField('Guardar Proyecto')

class UserForm(FlaskForm):
    """
    Formulario para crear y editar usuarios en el panel de administración.
    Incluye una lógica condicional para el campo de la contraseña, haciéndola
    obligatoria solo al crear un nuevo usuario.
    """
    username = StringField('Nombre de usuario', validators=[
        DataRequired(message="El nombre de usuario es requerido."),
        Length(min=4, max=25, message="Debe tener entre 4 y 25 caracteres.")
    ])

    nombre_completo = StringField('Nombre Completo', validators=[
        DataRequired(message="El nombre completo es requerido.")
    ])

    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El email es requerido."),
        Email(message="Por favor, introduce una dirección de correo válida.")
    ])

    password = PasswordField('Contraseña', validators=[
        Optional(),
        Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")
    ])

    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        EqualTo('password', message='Las contraseñas deben coincidir.')
    ])

    roles = SelectMultipleField('Roles', coerce=str,
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
        validators=[DataRequired(message="Debes seleccionar al menos un rol.")])

    activo = BooleanField('Activo')

    submit = SubmitField('Guardar Usuario')

    def __init__(self, original_username=None, original_email=None, *args, **kwargs):
        """
        Constructor personalizado del formulario.
        Se utiliza para añadir una validación condicional a la contraseña
        y para validar la unicidad del username y email al editar.
        """
        super(UserForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email

        if not kwargs.get('obj'):
            self.password.validators.insert(0, DataRequired(message="La contraseña es obligatoria para nuevos usuarios."))

    def validate_username(self, username):
        from db import get_db
        from flask import current_app
        db = get_db()

        if not self.original_username or username.data.lower() != self.original_username.lower():
            is_testing = current_app.config.get('TESTING', False)
            sql = 'SELECT id FROM usuarios WHERE LOWER(username) = ?' if is_testing else 'SELECT id FROM usuarios WHERE LOWER(username) = %s'

            cursor = db.cursor()
            cursor.execute(sql, (username.data.lower(),))
            user = cursor.fetchone()
            cursor.close()

            if user:
                raise ValidationError('Este nombre de usuario ya está en uso. Por favor, elige otro.')

    def validate_email(self, email):
        from db import get_db
        from flask import current_app
        db = get_db()

        if not self.original_email or email.data.lower() != self.original_email.lower():
            is_testing = current_app.config.get('TESTING', False)
            sql = 'SELECT id FROM usuarios WHERE LOWER(email) = ?' if is_testing else 'SELECT id FROM usuarios WHERE LOWER(email) = %s'

            cursor = db.cursor()
            cursor.execute(sql, (email.data.lower(),))
            user = cursor.fetchone()
            cursor.close()

            if user:
                raise ValidationError('Este correo electrónico ya está registrado. Por favor, elige otro.')


class ProfileForm(FlaskForm):
    """
    Formulario para ver y actualizar el perfil del usuario actual.
    Permite al usuario cambiar su nombre, email y contraseña.
    """
    nombre_completo = StringField('Nombre Completo', validators=[
        DataRequired(message="El nombre completo es requerido.")
    ])

    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El email es requerido."),
        Email(message="Por favor, introduce una dirección de correo válida.")
    ])

    current_password = PasswordField('Contraseña Actual', validators=[
        Optional()
    ])

    new_password = PasswordField('Nueva Contraseña', validators=[
        Optional(),
        Length(min=6, message="La nueva contraseña debe tener al menos 6 caracteres.")
    ])

    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        EqualTo('new_password', message='Las nuevas contraseñas deben coincidir.')
    ])

    email_notif_estado = BooleanField('Recibir notificaciones por email sobre cambios de estado de conexiones')

    submit = SubmitField('Actualizar Perfil')

    def validate_email(self, email):
        from db import get_db
        from flask import g, current_app
        db = get_db()
        if email.data.lower() != g.user['email'].lower():
            is_testing = current_app.config.get('TESTING', False)
            sql = 'SELECT id FROM usuarios WHERE LOWER(email) = ?' if is_testing else 'SELECT id FROM usuarios WHERE LOWER(email) = %s'

            cursor = db.cursor()
            cursor.execute(sql, (email.data.lower(),))
            user = cursor.fetchone()
            cursor.close()

            if user:
                raise ValidationError('Este correo electrónico ya está registrado. Por favor, elige otro.')

    def validate_current_password(self, field):
        from flask import g
        from werkzeug.security import check_password_hash

        if self.new_password.data or self.confirm_password.data:
            if not field.data:
                raise ValidationError("Debes proporcionar tu contraseña actual para cambiarla.")

            if not g.user or not check_password_hash(g.user['password_hash'], field.data):
                raise ValidationError("La contraseña actual no es correcta.")

class ConfigurationForm(FlaskForm):
    """
    Formulario para la configuración general del sistema, accesible por administradores.
    """
    per_page = IntegerField('Elementos por página',
        validators=[
            DataRequired(),
            NumberRange(min=5, max=50, message="El valor debe ser un número entre 5 y 50.")
        ],
        description="Define cuántos registros se muestran en las tablas de Proyectos, Conexiones, etc., antes de pasar a la siguiente página.")

    maintenance_mode = BooleanField('Activar modo mantenimiento')

    submit = SubmitField('Guardar Configuración')

class ReportForm(FlaskForm):
    """
    Formulario para crear y editar reportes personalizados.
    Define todos los campos necesarios para que un administrador pueda construir
    un reporte a medida, filtrando datos y seleccionando las columnas a mostrar.
    """
    nombre = StringField('Nombre del Reporte',
        validators=[DataRequired(message="El nombre es obligatorio.")],
        render_kw={"placeholder": "Ej: Reporte Mensual de Conexiones Aprobadas"})

    descripcion = TextAreaField('Descripción',
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "Añade una breve descripción del propósito de este reporte..."})

    proyecto_id = SelectField('Proyecto', coerce=int, validators=[Optional()])
    estado = SelectField('Estado de Conexión', choices=[
        ('', 'Todos los Estados'),
        ('SOLICITADO', 'Solicitado'),
        ('EN_PROCESO', 'En Proceso'),
        ('REALIZADO', 'Realizado'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado')
    ], validators=[Optional()])
    realizador_id = SelectField('Realizador', coerce=int, validators=[Optional()])
    fecha_inicio = DateField('Fecha de Inicio', validators=[Optional()], format='%Y-%m-%d')
    fecha_fin = DateField('Fecha de Fin', validators=[Optional()], format='%Y-%m-%d')


    columnas = SelectMultipleField('Columnas a Incluir',
        choices=[
            ('codigo_conexion', 'Código Conexión'),
            ('tipologia', 'Tipología'),
            ('estado', 'Estado'),
            ('solicitante_nombre', 'Solicitante'),
            ('realizador_nombre', 'Realizador'),
            ('aprobador_nombre', 'Aprobador'),
            ('fecha_creacion', 'Fecha de Creación'),
            ('fecha_modificacion', 'Fecha de Modificación')
        ],
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
        validators=[DataRequired(message="Debes seleccionar al menos una columna.")])

    output_format = RadioField('Formato de Salida', choices=[
        ('csv', 'CSV (.csv)'),
        ('xlsx', 'Excel (.xlsx)'),
        ('pdf', 'PDF (.pdf)')
    ], default='csv', validators=[DataRequired(message="Debes seleccionar un formato de salida.")])

    programado = BooleanField('Programar envío por email')
    frecuencia = SelectField('Frecuencia', choices=[('diaria', 'Diaria'), ('semanal', 'Semanal'), ('mensual', 'Mensual')], validators=[Optional()])
    destinatarios = TextAreaField('Destinatarios (emails separados por coma)',
        render_kw={"placeholder": "ejemplo1@heptapro.com, ejemplo2@heptapro.com"},
        validators=[Optional()]
    )

    submit = SubmitField('Guardar Reporte')

    def validate_destinatarios(self, field):
        """Valida que todos los emails en el campo destinatarios sean válidos."""
        if self.programado.data:
            if not field.data:
                raise ValidationError('Este campo es obligatorio si el reporte está programado.')
            
            emails = [e.strip() for e in field.data.split(',') if e.strip()]
            if not emails:
                raise ValidationError('Debe ingresar al menos un correo electrónico si el reporte está programado.')

            email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            for email in emails:
                if not email_regex.match(email):
                    raise ValidationError(f'El correo electrónico "{email}" no es válido.')

    def validate(self, extra_validators=None):
        """
        Método de validación extendido.
        Además de las validaciones estándar de los campos, este método comprueba
        que la fecha de inicio no sea posterior a la fecha de fin.
        """
        initial_validation = super(ReportForm, self).validate(extra_validators)
        if not initial_validation:
            return False

        if self.fecha_inicio.data and self.fecha_fin.data:
            if self.fecha_inicio.data > self.fecha_fin.data:
                self.fecha_fin.errors.append('La fecha de fin no puede ser anterior a la fecha de inicio.')
                return False

        return True


class ComputosReportForm(FlaskForm):
    """Formulario para generar reportes de cómputos métricos."""
    proyecto_id = SelectField('Proyecto', coerce=int, validators=[DataRequired(message="Debe seleccionar un proyecto.")])
    fecha_inicio = DateField('Fecha de Inicio (Opcional)', validators=[Optional()], format='%Y-%m-%d')
    fecha_fin = DateField('Fecha de Fin (Opcional)', validators=[Optional()], format='%Y-%m-%d')
    submit = SubmitField('Generar Reporte')

    def validate(self, extra_validators=None):
        """
        Validación extendida para asegurar que la fecha de inicio no sea posterior a la fecha de fin.
        """
        initial_validation = super(ComputosReportForm, self).validate(extra_validators)
        if not initial_validation:
            return False

        if self.fecha_inicio.data and self.fecha_fin.data:
            if self.fecha_inicio.data > self.fecha_fin.data:
                self.fecha_fin.errors.append('La fecha de fin no puede ser anterior a la fecha de inicio.')
                return False

        return True


class AliasForm(FlaskForm):
    """Formulario para crear y editar alias de perfiles."""
    nombre_perfil = StringField('Nombre Completo del Perfil',
        validators=[DataRequired(message="El nombre del perfil es obligatorio.")],
        render_kw={"placeholder": "Ej: IPE-300"})
    alias = StringField('Alias',
        validators=[DataRequired(message="El alias es obligatorio.")],
        render_kw={"placeholder": "Ej: P30"})
    norma = StringField('Norma', validators=[Optional()], render_kw={"placeholder": "Ej: AISC, Eurocode"})
    submit = SubmitField('Guardar Alias')

class ConnectionForm(FlaskForm):
    """
    Formulario para editar los detalles y perfiles de una conexión existente.
    """
    perfil_1 = StringField('Perfil 1', validators=[DataRequired(message="El Perfil 1 es obligatorio.")])
    perfil_2 = StringField('Perfil 2', validators=[Optional()])
    perfil_3 = StringField('Perfil 3', validators=[Optional()])

    descripcion = TextAreaField('Descripción (opcional)',
        render_kw={"rows": 4, "placeholder": "Añade o edita los detalles de la conexión..."})
    submit = SubmitField('Guardar Cambios')
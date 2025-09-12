from abc import ABC, abstractmethod

class BaseDAL(ABC):

    @abstractmethod
    def get_conexion(self, conexion_id):
        pass

    @abstractmethod
    def get_conexiones_by_proyecto(self, proyecto_id):
        pass

    @abstractmethod
    def create_conexion(self, conexion_data):
        pass

    @abstractmethod
    def update_conexion(self, conexion_id, conexion_data):
        pass

    @abstractmethod
    def delete_conexion(self, conexion_id):
        pass

    @abstractmethod
    def search_conexiones(self, query):
        pass

    @abstractmethod
    def get_proyectos_for_user(self, user_id, is_admin):
        pass

    @abstractmethod
    def get_proyecto(self, proyecto_id):
        pass

    @abstractmethod
    def get_alias(self, nombre_perfil):
        pass

    @abstractmethod
    def get_all_aliases(self):
        pass

    @abstractmethod
    def get_all_conexiones_codes(self):
        pass

    @abstractmethod
    def get_archivos_by_conexion(self, conexion_id):
        pass

    @abstractmethod
    def get_comentarios_by_conexion(self, conexion_id):
        pass

    @abstractmethod
    def get_historial_by_conexion(self, conexion_id):
        pass

    @abstractmethod
    def get_usuario_a_asignar(self, username):
        pass

    @abstractmethod
    def update_conexion_realizador(self, conexion_id, realizador_id, nuevo_estado=None):
        pass

    @abstractmethod
    def add_historial_estado(self, conexion_id, usuario_id, estado, detalles=None):
        pass

    @abstractmethod
    def create_archivo(self, conexion_id, usuario_id, tipo_archivo, filename):
        pass

    @abstractmethod
    def get_archivo(self, archivo_id, conexion_id):
        pass

    @abstractmethod
    def delete_archivo(self, archivo_id):
        pass

    @abstractmethod
    def create_comentario(self, conexion_id, usuario_id, contenido):
        pass

    @abstractmethod
    def get_comentario(self, comentario_id, conexion_id):
        pass

    @abstractmethod
    def delete_comentario(self, comentario_id):
        pass

    @abstractmethod
    def get_users_for_notification(self, proyecto_id, roles_to_notify):
        pass

    @abstractmethod
    def create_notification(self, usuario_id, mensaje, url, conexion_id):
        pass

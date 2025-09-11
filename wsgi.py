# wsgi.py
import os
from app import create_app

# Activa el entorno virtual si no está activado por el servicio de Windows
# Esto es especialmente útil si ejecutas el script directamente o si el servicio no carga el entorno
# Si usas NSSM, NSSM maneja la ruta al ejecutable de Python dentro del venv
# venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
# if os.path.exists(venv_path):
#     activate_this_file = os.path.join(venv_path, 'Scripts', 'activate_this.py')
#     with open(activate_this_file) as f:
#         exec(f.read(), {'__file__': activate_this_file})

# Carga las variables de entorno del archivo .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = create_app()

if __name__ == "__main__":
    from waitress import serve
    # Aquí la aplicación escuchará en el puerto 5000 (o el que elijas)
    # Esto es el puerto INTERNO para Waitress, no el que IIS expondrá al público
    serve(app, host="127.0.0.1", port=5000)
# Usa una imagen base oficial de Python con la versión 3.11
FROM python:3.11-slim-bullseye

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de requerimientos e instala las dependencias
# Esto ayuda a Docker a cachear capas y acelerar builds si requirements.txt no cambia
COPY requirements.txt ./
# Instala dependencias, incluyendo las necesarias para WeasyPrint
# build-essential y libffi-dev para compilación
# libglib2.0-0, libharfbuzz0b, libpango-1.0-0, libpangocairo-1.0-0, libgdk-pixbuf2.0-0, libcairo2
# libjpeg-dev, zlib1g-dev para WeasyPrint (PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libglib2.0-0 \
    libharfbuzz0b \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    pango1.0-tools \
    # Limpiar caché de apt-get
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación
COPY . .

# Crear un usuario no privilegiado
RUN groupadd -r appgroup && useradd -r -g appgroup -s /sbin/nologin -d /app appuser
# Cambiar la propiedad de los archivos
RUN chown -R appuser:appgroup /app
# Cambiar al usuario no privilegiado
USER appuser

# Expone el puerto que Gunicorn usará (ej. 5001)
EXPOSE 5001

# Comando para ejecutar la aplicación con Gunicorn
# Usa 'python -m gunicorn' para asegurar que el ejecutable de gunicorn se encuentre correctamente
# Se usa 'exec' para que Gunicorn sea el proceso principal (PID 1) y reciba las señales de Docker.
# El número de workers se define con una variable de entorno para flexibilidad, con un default razonable.
CMD exec python -m gunicorn --bind 0.0.0.0:5001 --workers ${GUNICORN_WORKERS:-5} --timeout 120 --log-level info "app:app"
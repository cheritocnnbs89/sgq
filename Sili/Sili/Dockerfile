# Imagen base
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

# Crear directorio de la app
WORKDIR /app

# Instalar dependencias del sistema: build-essential (compilar libs Python),
# curl/gnupg (agregar repo Microsoft), libs de weasyprint (generar PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl gnupg unixodbc-dev \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-xlib-2.0-0 libffi-dev shared-mime-info \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# Copiar requisitos (ajusta según tu requirements.txt real)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el proyecto
COPY . /app

# Exponer puerto
EXPOSE 5000

# Comando
CMD ["python", "app.py"]

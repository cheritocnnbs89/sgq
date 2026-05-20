# Imagen base
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

# Crear directorio de la app
WORKDIR /app

# Instalar dependencias del sistema (si openpyxl, sqlite, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     && rm -rf /var/lib/apt/lists/*

# Copiar requisitos (ajusta según tu requirements.txt real)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el proyecto
COPY . /app

# Exponer puerto
EXPOSE 5000

# Comando
CMD ["python", "app.py"]

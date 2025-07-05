FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 appuser

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar código de la aplicación
COPY . .

# Cambiar permisos y propietario
RUN chown -R appuser:appuser /app
USER appuser

# Crear directorios necesarios
RUN mkdir -p /app/descargas /app/logs

# Exponer puerto (opcional, para debugging)
EXPOSE 8080

# Comando por defecto
CMD ["python", "main.py", "--help"] 
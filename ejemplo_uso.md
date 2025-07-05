# Ejemplos de Uso - Facebook Profile Downloader

Este documento muestra ejemplos prácticos de cómo usar el Facebook Profile Downloader.

## 🚀 Ejemplos Básicos

### 1. Descargar todo el contenido de un perfil

```bash
# Con Docker (recomendado)
docker-compose run --rm facebook-downloader python main.py descargar usuario123

# Con instalación local
python main.py descargar usuario123
```

### 2. Descargar con límites específicos

```bash
# Descargar solo las primeras 50 fotos
python main.py descargar usuario123 --max-fotos 50

# Descargar solo los primeros 10 videos
python main.py descargar usuario123 --max-videos 10

# Descargar 30 fotos y 5 videos
python main.py descargar usuario123 --max-fotos 30 --max-videos 5
```

### 3. Especificar ruta de descarga

```bash
# Descargar a una carpeta específica
python main.py descargar usuario123 --ruta /ruta/personalizada/descargas

# Con Docker
docker-compose run --rm -v /ruta/personalizada/descargas:/app/descargas facebook-downloader python main.py descargar usuario123
```

## 🖼️ Procesamiento de Imágenes

### 1. Procesar imágenes descargadas

```bash
# Procesar con modelo por defecto (llava:latest)
python main.py procesar-imagenes usuario123

# Procesar con modelo específico
python main.py procesar-imagenes usuario123 --modelo llava:13b
```

### 2. Procesar imágenes en ruta específica

```bash
python main.py procesar-imagenes usuario123 --ruta /ruta/personalizada/descargas
```

## 📊 Información del Perfil

### 1. Ver información básica de un perfil

```bash
python main.py info usuario123
```

## 🔧 Ejemplos Avanzados

### 1. Script de descarga automática

```bash
#!/bin/bash
# script_descarga.sh

USUARIO="usuario123"
RUTA_DESCARGAS="./descargas_personalizadas"

echo "Iniciando descarga de $USUARIO..."

# Descargar contenido
python main.py descargar $USUARIO --ruta $RUTA_DESCARGAS --max-fotos 100 --max-videos 20

# Procesar imágenes
python main.py procesar-imagenes $USUARIO --ruta $RUTA_DESCARGAS

echo "Proceso completado!"
```

### 2. Descarga múltiple de perfiles

```bash
#!/bin/bash
# descarga_multiple.sh

PERFILES=("usuario1" "usuario2" "usuario3")

for perfil in "${PERFILES[@]}"; do
    echo "Descargando perfil: $perfil"
    python main.py descargar $perfil --max-fotos 50 --max-videos 10
    echo "Procesando imágenes de: $perfil"
    python main.py procesar-imagenes $perfil
    echo "Completado: $perfil"
    echo "---"
done
```

### 3. Uso con variables de entorno

```bash
# Configurar variables de entorno
export DOWNLOAD_PATH="/ruta/personalizada"
export MAX_PHOTOS=100
export MAX_VIDEOS=20
export OLLAMA_MODEL="llava:13b"

# Ejecutar sin parámetros (usa variables de entorno)
python main.py descargar usuario123
python main.py procesar-imagenes usuario123
```

## 🐳 Ejemplos con Docker

### 1. Descarga básica con Docker

```bash
# Construir imagen
docker build -t facebook-downloader .

# Ejecutar descarga
docker run --rm -v $(pwd)/descargas:/app/descargas facebook-downloader python main.py descargar usuario123
```

### 2. Docker Compose con configuración personalizada

```bash
# Crear docker-compose.override.yml
version: '3.8'
services:
  facebook-downloader:
    environment:
      - MAX_PHOTOS=100
      - MAX_VIDEOS=20
      - OLLAMA_MODEL=llava:13b
    volumes:
      - ./descargas_personalizadas:/app/descargas

# Ejecutar
docker-compose run --rm facebook-downloader python main.py descargar usuario123
```

### 3. Docker con GUI (Linux)

```bash
# Permitir conexiones X11
xhost +local:docker

# Ejecutar con interfaz gráfica
docker-compose run --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  facebook-downloader python main.py descargar usuario123
```

## 📝 Ejemplos de Configuración

### 1. Archivo de configuración personalizada

```python
# config_personalizada.py
from config import Config

class ConfigPersonalizada(Config):
    # Sobrescribir configuración
    DEFAULT_MAX_PHOTOS = 200
    DEFAULT_MAX_VIDEOS = 50
    REQUEST_DELAY = 2.0  # Más lento para evitar detección
    
    # Configuración personalizada de selectores
    SELECTORS = {
        **Config.SELECTORS,
        'custom_selector': '[data-testid="custom_element"]'
    }
```

### 2. Script de configuración automática

```bash
#!/bin/bash
# setup_config.sh

# Crear directorios necesarios
mkdir -p descargas logs

# Configurar permisos
chmod 755 descargas logs

# Verificar instalaciones
echo "Verificando instalaciones..."

# Verificar Python
python --version || echo "Python no encontrado"

# Verificar Tesseract
tesseract --version || echo "Tesseract no encontrado"

# Verificar Ollama
ollama --version || echo "Ollama no encontrado"

echo "Configuración completada!"
```

## 🔍 Ejemplos de Troubleshooting

### 1. Verificar estado de instalación

```bash
# Ejecutar tests básicos
python test_cli.py

# Verificar dependencias
pip list | grep -E "(playwright|typer|rich|pytesseract|pillow)"
```

### 2. Debug de descarga

```bash
# Ejecutar con logging detallado
LOG_LEVEL=DEBUG python main.py descargar usuario123

# Ver logs en tiempo real
tail -f descargas/usuario123/descarga.log
```

### 3. Limpiar archivos de procesamiento

```python
# script_limpieza.py
from image_processor import ImageProcessor
from pathlib import Path

processor = ImageProcessor()
processor.cleanup_processed_files(Path("./descargas/usuario123/imagenes"))
```

## 📊 Ejemplos de Análisis

### 1. Script de estadísticas

```python
# estadisticas.py
import json
from pathlib import Path

def generar_estadisticas(usuario):
    ruta_perfil = Path(f"./descargas/{usuario}")
    
    if not ruta_perfil.exists():
        print(f"Perfil {usuario} no encontrado")
        return
    
    # Contar archivos
    fotos = len(list((ruta_perfil / "imagenes").glob("*.jpg")))
    videos = len(list((ruta_perfil / "videos").glob("*.mp4")))
    descripciones = len(list((ruta_perfil / "imagenes").glob("*.desc.txt")))
    ocr_files = len(list((ruta_perfil / "imagenes").glob("*.ocr.txt")))
    
    print(f"Estadísticas para {usuario}:")
    print(f"  - Fotos: {fotos}")
    print(f"  - Videos: {videos}")
    print(f"  - Descripciones: {descripciones}")
    print(f"  - Archivos OCR: {ocr_files}")

# Uso
generar_estadisticas("usuario123")
```

### 2. Script de backup

```bash
#!/bin/bash
# backup.sh

USUARIO="usuario123"
FECHA=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/${USUARIO}_${FECHA}"

echo "Creando backup de $USUARIO..."

# Crear directorio de backup
mkdir -p $BACKUP_DIR

# Copiar archivos
cp -r ./descargas/$USUARIO $BACKUP_DIR/

# Comprimir
tar -czf "${BACKUP_DIR}.tar.gz" $BACKUP_DIR

# Limpiar directorio temporal
rm -rf $BACKUP_DIR

echo "Backup creado: ${BACKUP_DIR}.tar.gz"
```

## 🎯 Casos de Uso Comunes

### 1. Descarga de perfil público

```bash
# Perfil público sin login
python main.py descargar perfil_publico --max-fotos 100
```

### 2. Descarga de perfil privado (requiere login)

```bash
# Nota: Para perfiles privados, necesitarás implementar login
# Este es un ejemplo conceptual
python main.py descargar perfil_privado --login --max-fotos 50
```

### 3. Procesamiento en lote

```bash
# Procesar múltiples perfiles
for perfil in perfil1 perfil2 perfil3; do
    python main.py descargar $perfil --max-fotos 20
    python main.py procesar-imagenes $perfil
done
```

### 4. Monitoreo continuo

```bash
# Script de monitoreo
while true; do
    echo "Verificando nuevos perfiles..."
    # Lógica de verificación
    sleep 3600  # Esperar 1 hora
done
```

---

**Nota**: Recuerda respetar los términos de servicio de Facebook y las leyes de tu jurisdicción al usar esta herramienta. 
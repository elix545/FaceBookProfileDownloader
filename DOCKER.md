# Facebook Profile Downloader - Docker

Este documento explica cómo usar el Facebook Profile Downloader con Docker.

## 🐳 Requisitos

- Docker
- Docker Compose (opcional)

## 🚀 Uso Rápido

### Con Docker Compose (Recomendado)

1. **Construir y ejecutar:**
```bash
docker-compose up --build
```

2. **Ejecutar comandos específicos:**
```bash
# Descargar contenido de un perfil
docker-compose run --rm facebook-downloader python main.py descargar usuario123

# Procesar imágenes descargadas
docker-compose run --rm facebook-downloader python main.py procesar-imagenes usuario123

# Ver ayuda
docker-compose run --rm facebook-downloader python main.py --help
```

### Con Docker directamente

1. **Construir la imagen:**
```bash
docker build -t facebook-downloader .
```

2. **Ejecutar comandos:**
```bash
# Descargar contenido
docker run --rm -v $(pwd)/descargas:/app/descargas facebook-downloader python main.py descargar usuario123

# Procesar imágenes
docker run --rm -v $(pwd)/descargas:/app/descargas facebook-downloader python main.py procesar-imagenes usuario123
```

## 📁 Estructura de Volúmenes

El contenedor monta automáticamente:
- `./descargas` → `/app/descargas` (archivos descargados)
- `./logs` → `/app/logs` (logs del sistema)

## 🔧 Configuración

### Variables de Entorno

Puedes configurar variables de entorno en el `docker-compose.yml`:

```yaml
environment:
  - PYTHONUNBUFFERED=1
  - DISPLAY=${DISPLAY}  # Para GUI (Linux)
```

### Modo Interactivo

Para usar el contenedor de forma interactiva:

```bash
docker-compose run --rm -it facebook-downloader bash
```

## 🖥️ Uso con GUI (Linux)

Para usar el navegador con interfaz gráfica en Linux:

1. **Permitir conexiones X11:**
```bash
xhost +local:docker
```

2. **Ejecutar con GUI:**
```bash
docker-compose run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix facebook-downloader python main.py descargar usuario123
```

## 🐛 Troubleshooting

### Error de permisos
```bash
# En Linux/Mac
sudo chown -R $USER:$USER descargas/
```

### Error de memoria
```bash
# Aumentar memoria disponible
docker run --rm -m 4g -v $(pwd)/descargas:/app/descargas facebook-downloader python main.py descargar usuario123
```

### Error de red
```bash
# Usar red del host
docker run --rm --network host -v $(pwd)/descargas:/app/descargas facebook-downloader python main.py descargar usuario123
```

## 📝 Ejemplos de Uso

### Descargar con límite de fotos
```bash
docker-compose run --rm facebook-downloader python main.py descargar usuario123 --max-fotos 50
```

### Descargar a carpeta específica
```bash
docker-compose run --rm facebook-downloader python main.py descargar usuario123 --ruta /app/descargas/mi_perfil
```

### Procesar imágenes con modelo específico
```bash
docker-compose run --rm facebook-downloader python main.py procesar-imagenes usuario123 --modelo llava:13b
```

## 🔒 Seguridad

- El contenedor se ejecuta como usuario no-root
- Las descargas se almacenan en volúmenes montados
- No se requieren permisos especiales del sistema

## 📊 Monitoreo

Para ver logs en tiempo real:
```bash
docker-compose logs -f facebook-downloader
```

## 🧹 Limpieza

Para limpiar contenedores e imágenes no utilizadas:
```bash
docker system prune -a
``` 
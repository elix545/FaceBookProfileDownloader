# Facebook Profile Downloader

Herramienta CLI completa para descargar todas las imágenes y videos de un perfil de Facebook, organizando el contenido en carpetas por perfil, extrayendo metadatos y procesando imágenes con IA local.

## 🚀 Características

- **Descarga automática** de fotos y videos de perfiles de Facebook
- **Login opcional** con credenciales de Facebook (si el contenido lo requiere)
- **Scroll infinito** para obtener todo el historial de publicaciones
- **Organización automática** en carpetas por perfil (imágenes/videos)
- **Extracción de metadatos** (descripción, hashtags, fecha, autor)
- **Procesamiento de imágenes** con Ollama (descripciones automáticas)
- **OCR con Tesseract** para extraer texto de imágenes
- **Evita duplicados** automáticamente
- **Logging completo** de todas las operaciones
- **CLI robusto** con validación y manejo de errores

## 📋 Requisitos

### Software necesario
- **Python 3.8+**
- **Tesseract OCR** (para extracción de texto de imágenes)
- **Ollama** (para generación de descripciones de imágenes)

### Dependencias de Python
```
playwright
requests
typer[all]
rich
pytesseract
pillow
```

## 🛠️ Instalación

### Opción 1: Docker (Recomendado)

La forma más fácil de usar la herramienta es con Docker:

```bash
# Clonar el repositorio
git clone https://github.com/elix545/FaceBookProfileDownloader.git
cd FaceBookProfileDownloader

# Construir y ejecutar con Docker Compose
docker-compose up --build

# O ejecutar comandos específicos
docker-compose run --rm facebook-downloader python main.py descargar usuario123
```

Ver [DOCKER.md](DOCKER.md) para más detalles sobre el uso con Docker.

### Opción 2: Instalación Local

#### 1. Clonar el repositorio
```bash
git clone https://github.com/elix545/FaceBookProfileDownloader.git
cd FaceBookProfileDownloader
```

#### 2. Instalar dependencias de Python
```bash
pip install -r requirements.txt
```

#### 3. Instalar navegadores de Playwright
```bash
python -m playwright install
```

#### 4. Instalar Tesseract OCR

##### Windows:
1. Descargar desde: https://github.com/tesseract-ocr/tesseract/releases
2. Instalar y agregar al PATH del sistema: `C:\Program Files\Tesseract-OCR\`
3. Verificar instalación: `tesseract --version`

##### macOS:
```bash
brew install tesseract
```

##### Linux (Ubuntu/Debian):
```bash
sudo apt install tesseract-ocr
```

#### 5. Instalar Ollama
1. Descargar desde: https://ollama.ai/
2. Instalar y ejecutar: `ollama serve`
3. Descargar modelo visual: `ollama pull llava:latest`

## 📖 Uso

### Comandos principales

#### Descargar contenido de un perfil
```bash
# Con Docker (recomendado)
docker-compose run --rm facebook-downloader python main.py descargar <usuario_facebook> [opciones]

# Con instalación local
python main.py descargar <usuario_facebook> [opciones]
```

#### Procesar imágenes descargadas
```bash
# Con Docker
docker-compose run --rm facebook-downloader python main.py procesar-imagenes <usuario_facebook> [opciones]

# Con instalación local
python main.py procesar-imagenes <usuario_facebook> [opciones]
```

### Ejemplos de uso

#### Descargar todo el contenido de un perfil
```bash
# Con Docker
docker-compose run --rm facebook-downloader python main.py descargar usuario123 --ruta /app/descargas

# Con instalación local
python main.py descargar usuario123 --ruta ./descargas
```

#### Descargar solo las primeras 50 fotos
```bash
# Con Docker
docker-compose run --rm facebook-downloader python main.py descargar usuario123 --max-fotos 50

# Con instalación local
python main.py descargar usuario123 --max-fotos 50
```

#### Procesar imágenes con modelo personalizado
```bash
# Con Docker
docker-compose run --rm facebook-downloader python main.py procesar-imagenes usuario123 --modelo llava:13b

# Con instalación local
python main.py procesar-imagenes usuario123 --modelo llava:13b
```

### Opciones disponibles

#### Comando `descargar`:
- `usuario`: Nombre de usuario de Facebook (sin @)
- `--ruta`: Ruta base para descargas (por defecto: ./descargas)
- `--max-fotos`: Máximo número de fotos a descargar (0 = sin límite)
- `--max-videos`: Máximo número de videos a descargar (0 = sin límite)

#### Comando `procesar-imagenes`:
- `usuario`: Nombre de usuario de Facebook (sin @)
- `--ruta`: Ruta base para descargas (por defecto: ./descargas)
- `--modelo`: Modelo de Ollama para descripción (por defecto: llava:latest)

## 📁 Estructura del proyecto

```
FaceBookProfileDownloader/
├── main.py              # Script principal con CLI
├── requirements.txt     # Dependencias de Python
├── README.md           # Documentación principal
├── DOCKER.md           # Documentación específica para Docker
├── Dockerfile          # Configuración del contenedor Docker
├── docker-compose.yml  # Configuración de Docker Compose
├── .dockerignore       # Archivos a excluir del contenedor
├── .gitignore          # Archivos a excluir del repositorio
├── test_cli.py         # Tests básicos
└── descargas/          # Carpeta de descargas (se crea automáticamente)
    └── <perfil>/
        ├── imagenes/   # Imágenes descargadas
        │   ├── imagen1.jpg
        │   ├── imagen1.desc.txt    # Descripción generada por Ollama
        │   └── imagen1.ocr.txt     # Texto extraído por Tesseract
        ├── videos/     # Videos descargados
        │   ├── video1.mp4
        │   └── video1.json        # Metadatos del video
        └── descarga.log           # Log de operaciones
```

## 🔧 Funcionalidades detalladas

### Descarga de contenido
- **Scroll infinito**: Recorre automáticamente todo el perfil
- **Detección de login**: Identifica si se requiere autenticación
- **Manejo de errores**: Reintentos automáticos ante fallos
- **Evita duplicados**: No descarga archivos ya existentes
- **Metadatos**: Extrae y guarda información de cada publicación

### Procesamiento de imágenes
- **Descripción automática**: Usa Ollama para generar descripciones en español
- **OCR**: Extrae texto visible en las imágenes
- **Procesamiento incremental**: Solo procesa imágenes nuevas
- **Archivos separados**: Guarda descripción y texto en archivos distintos

### Logging y monitoreo
- **Log detallado**: Registra todas las operaciones en `descarga.log`
- **Progreso en tiempo real**: Muestra avance en consola
- **Resumen final**: Estadísticas de descarga al finalizar

## 🧪 Tests

Ejecutar tests básicos:
```bash
python test_cli.py
```

## ⚠️ Troubleshooting

### Error: "No module named 'typer'"
```bash
pip install -r requirements.txt
```

### Error: "tesseract: command not found"
- Verificar que Tesseract esté instalado y en el PATH
- En Windows: agregar `C:\Program Files\Tesseract-OCR` al PATH del sistema

### Error: "ollama: command not found"
- Instalar Ollama desde https://ollama.ai/
- Ejecutar `ollama serve` antes de usar el comando

### Error de login en Facebook
- Verificar credenciales
- Algunos perfiles pueden requerir verificación adicional

### Timeout o errores de red
- La herramienta incluye reintentos automáticos
- Verificar conexión a internet
- Algunos perfiles pueden tener restricciones geográficas

## 📝 Logs

Todos los logs se guardan en `descargas/<perfil>/descarga.log` con:
- Timestamp de cada operación
- Nivel de log (INFO, WARNING, ERROR)
- Detalles de errores y advertencias
- Estadísticas de descarga

## 🤝 Contribuir

1. Fork el proyecto
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## ⚖️ Disclaimer

Esta herramienta es para uso educativo y personal. Respeta los términos de servicio de Facebook y las leyes de tu jurisdicción. El uso de herramientas automatizadas puede violar los términos de servicio de Facebook.

---

**Desarrollado con ❤️ para la comunidad de desarrolladores** 
"""
Configuración del Facebook Profile Downloader
"""

import os
from pathlib import Path
from typing import Dict, Any

class Config:
    """Configuración principal de la aplicación"""
    
    # Configuración de la aplicación
    APP_NAME = "Facebook Profile Downloader"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Herramienta CLI para descargar fotos y videos de perfiles de Facebook"
    
    # URLs
    FACEBOOK_BASE_URL = "https://www.facebook.com"
    FACEBOOK_LOGIN_URL = "https://www.facebook.com/login"
    
    # Configuración de descargas
    DEFAULT_DOWNLOAD_PATH = "./descargas"
    DEFAULT_MAX_PHOTOS = 0  # 0 = sin límite
    DEFAULT_MAX_VIDEOS = 0  # 0 = sin límite
    
    # Configuración de tiempo
    REQUEST_DELAY = 1.0  # segundos entre descargas
    SCROLL_DELAY = 2.0   # segundos entre scrolls
    TIMEOUT = 30         # segundos de timeout
    
    # Configuración de procesamiento de imágenes
    DEFAULT_OLLAMA_MODEL = "llava:latest"
    SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    
    # Configuración de logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = "logs/facebook_downloader.log"
    
    # Configuración de Playwright
    PLAYWRIGHT_ARGS = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor'
    ]
    
    USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )
    
    # Configuración de selectores CSS
    SELECTORS = {
        'profile_name': 'h1',
        'profile_description': '[data-testid="profile_tab_container"] p',
        'photos_tab': [
            'a[href*="/photos"]',
            '[data-testid="photos_tab"]',
            'a:has-text("Photos")',
            'a:has-text("Fotos")'
        ],
        'videos_tab': [
            'a[href*="/videos"]',
            '[data-testid="videos_tab"]',
            'a:has-text("Videos")',
            'a:has-text("Vídeos")'
        ],
        'photo_images': 'img[src*="scontent"]',
        'video_elements': 'video source, video[src]',
        'login_indicators': [
            'text="Log In"',
            'text="Iniciar sesión"',
            '[data-testid="login_button"]',
            '.login-button'
        ]
    }
    
    # Configuración de OCR
    OCR_LANGUAGES = ['spa', 'eng']
    OCR_CONFIG = '--oem 3 --psm 6'
    
    # Configuración de metadatos
    METADATA_FIELDS = [
        'url',
        'fecha_descarga',
        'tipo',
        'tamaño',
        'resolución',
        'formato'
    ]
    
    @classmethod
    def get_download_path(cls) -> Path:
        """Obtiene la ruta de descarga desde variables de entorno o usa la predeterminada"""
        return Path(os.getenv('DOWNLOAD_PATH', cls.DEFAULT_DOWNLOAD_PATH))
    
    @classmethod
    def get_max_photos(cls) -> int:
        """Obtiene el máximo de fotos desde variables de entorno o usa la predeterminada"""
        return int(os.getenv('MAX_PHOTOS', cls.DEFAULT_MAX_PHOTOS))
    
    @classmethod
    def get_max_videos(cls) -> int:
        """Obtiene el máximo de videos desde variables de entorno o usa la predeterminada"""
        return int(os.getenv('MAX_VIDEOS', cls.DEFAULT_MAX_VIDEOS))
    
    @classmethod
    def get_ollama_model(cls) -> str:
        """Obtiene el modelo de Ollama desde variables de entorno o usa la predeterminada"""
        return os.getenv('OLLAMA_MODEL', cls.DEFAULT_OLLAMA_MODEL)
    
    @classmethod
    def get_request_delay(cls) -> float:
        """Obtiene el delay entre requests desde variables de entorno o usa la predeterminada"""
        return float(os.getenv('REQUEST_DELAY', cls.REQUEST_DELAY))
    
    @classmethod
    def get_timeout(cls) -> int:
        """Obtiene el timeout desde variables de entorno o usa la predeterminada"""
        return int(os.getenv('TIMEOUT', cls.TIMEOUT))
    
    @classmethod
    def get_log_level(cls) -> str:
        """Obtiene el nivel de log desde variables de entorno o usa la predeterminada"""
        return os.getenv('LOG_LEVEL', cls.LOG_LEVEL)
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convierte la configuración a un diccionario"""
        return {
            'app_name': cls.APP_NAME,
            'app_version': cls.APP_VERSION,
            'facebook_base_url': cls.FACEBOOK_BASE_URL,
            'download_path': str(cls.get_download_path()),
            'max_photos': cls.get_max_photos(),
            'max_videos': cls.get_max_videos(),
            'ollama_model': cls.get_ollama_model(),
            'request_delay': cls.get_request_delay(),
            'timeout': cls.get_timeout(),
            'log_level': cls.get_log_level(),
            'supported_image_formats': list(cls.SUPPORTED_IMAGE_FORMATS),
            'supported_video_formats': list(cls.SUPPORTED_VIDEO_FORMATS)
        } 
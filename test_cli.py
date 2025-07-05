#!/usr/bin/env python3
"""
Tests básicos para Facebook Profile Downloader
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

# Agregar el directorio actual al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from facebook_scraper import FacebookScraper
from image_processor import ImageProcessor
from main import FacebookProfileDownloader

console = Console()

class TestFacebookScraper:
    """Tests para FacebookScraper"""
    
    @pytest.mark.asyncio
    async def test_init(self):
        """Test de inicialización"""
        scraper = FacebookScraper()
        assert scraper.base_url == "https://www.facebook.com"
        assert scraper.browser is None
        assert scraper.page is None
    
    @pytest.mark.asyncio
    async def test_get_high_resolution_url(self):
        """Test de conversión de URL a alta resolución"""
        scraper = FacebookScraper()
        
        # Test con parámetros
        url = "https://scontent.xx.fbcdn.net/v/t1.0-9/123456_789.jpg?_nc_cat=1&ccb=1-7&_nc_sid=123&_nc_ohc=abc&_nc_ht=scontent.xx.fbcdn.net&oh=123&oe=456"
        expected = "https://scontent.xx.fbcdn.net/v/t1.0-9/123456_789.jpg"
        
        result = scraper._get_high_resolution_url(url)
        assert result == expected
        
        # Test sin parámetros
        url2 = "https://scontent.xx.fbcdn.net/v/t1.0-9/123456_789.jpg"
        result2 = scraper._get_high_resolution_url(url2)
        assert result2 == url2

class TestImageProcessor:
    """Tests para ImageProcessor"""
    
    def test_init(self):
        """Test de inicialización"""
        processor = ImageProcessor()
        expected_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        assert processor.supported_formats == expected_formats
    
    def test_get_image_files(self):
        """Test de obtención de archivos de imagen"""
        processor = ImageProcessor()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Crear archivos de prueba
            (temp_path / "test1.jpg").touch()
            (temp_path / "test2.png").touch()
            (temp_path / "test3.txt").touch()
            (temp_path / "test4.JPG").touch()
            
            image_files = processor._get_image_files(temp_path)
            
            # Debería encontrar 3 archivos de imagen
            assert len(image_files) == 3
            assert any("test1.jpg" in str(f) for f in image_files)
            assert any("test2.png" in str(f) for f in image_files)
            assert any("test4.JPG" in str(f) for f in image_files)
    
    @pytest.mark.asyncio
    async def test_save_text_file(self):
        """Test de guardado de archivo de texto"""
        processor = ImageProcessor()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test.txt"
            content = "Test content\nSecond line"
            
            await processor._save_text_file(temp_path, content)
            
            assert temp_path.exists()
            with open(temp_path, 'r', encoding='utf-8') as f:
                saved_content = f.read()
            
            assert saved_content == content

class TestFacebookProfileDownloader:
    """Tests para FacebookProfileDownloader"""
    
    def test_init(self):
        """Test de inicialización"""
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = FacebookProfileDownloader(base_path=temp_dir)
            assert downloader.base_path == Path(temp_dir)
            assert isinstance(downloader.scraper, FacebookScraper)
            assert isinstance(downloader.image_processor, ImageProcessor)
    
    @pytest.mark.asyncio
    async def test_download_profile_directory_creation(self):
        """Test de creación de directorios"""
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = FacebookProfileDownloader(base_path=temp_dir)
            
            # Mock del scraper
            downloader.scraper.scrape_profile = AsyncMock(return_value={
                'photos': 0,
                'videos': 0,
                'errors': 0,
                'duration': 0
            })
            
            await downloader.download_profile("testuser")
            
            # Verificar que se crearon los directorios
            profile_dir = Path(temp_dir) / "testuser"
            assert profile_dir.exists()
            assert (profile_dir / "imagenes").exists()
            assert (profile_dir / "videos").exists()
            assert (profile_dir / "descarga.log").exists()

def test_cli_help():
    """Test de ayuda de CLI"""
    from main import app
    
    # Simular comando de ayuda
    with patch('sys.argv', ['main.py', '--help']):
        try:
            app()
        except SystemExit:
            pass  # Typer sale con SystemExit al mostrar ayuda

def test_cli_descargar_command():
    """Test del comando descargar"""
    from main import app
    
    # Mock de la función principal
    with patch('main.FacebookProfileDownloader.download_profile') as mock_download:
        mock_download.return_value = {
            'photos': 5,
            'videos': 2,
            'errors': 0,
            'duration': 10.5
        }
        
        # Simular comando de descarga
        with patch('sys.argv', ['main.py', 'descargar', 'testuser']):
            try:
                app()
            except SystemExit:
                pass

def test_cli_procesar_imagenes_command():
    """Test del comando procesar-imagenes"""
    from main import app
    
    # Mock de la función principal
    with patch('main.FacebookProfileDownloader.process_images') as mock_process:
        mock_process.return_value = {
            'processed': 10,
            'descriptions': 8,
            'ocr_texts': 6,
            'errors': 1,
            'duration': 15.2
        }
        
        # Simular comando de procesamiento
        with patch('sys.argv', ['main.py', 'procesar-imagenes', 'testuser']):
            try:
                app()
            except SystemExit:
                pass

def run_basic_tests():
    """Ejecuta tests básicos"""
    console.print("[bold blue]Ejecutando tests básicos...[/bold blue]")
    
    # Test de inicialización
    try:
        scraper = FacebookScraper()
        console.print("[green]✓ FacebookScraper inicializado correctamente[/green]")
    except Exception as e:
        console.print(f"[red]✗ Error inicializando FacebookScraper: {e}[/red]")
    
    try:
        processor = ImageProcessor()
        console.print("[green]✓ ImageProcessor inicializado correctamente[/green]")
    except Exception as e:
        console.print(f"[red]✗ Error inicializando ImageProcessor: {e}[/red]")
    
    # Test de validación de instalaciones
    try:
        ollama_ok = processor.validate_ollama_installation()
        tesseract_ok = processor.validate_tesseract_installation()
        
        if ollama_ok:
            console.print("[green]✓ Ollama está instalado[/green]")
        else:
            console.print("[yellow]⚠ Ollama no está instalado o no es accesible[/yellow]")
        
        if tesseract_ok:
            console.print("[green]✓ Tesseract está instalado[/green]")
        else:
            console.print("[yellow]⚠ Tesseract no está instalado o no es accesible[/yellow]")
            
    except Exception as e:
        console.print(f"[red]✗ Error validando instalaciones: {e}[/red]")
    
    # Test de creación de directorios
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = FacebookProfileDownloader(base_path=temp_dir)
            console.print("[green]✓ FacebookProfileDownloader inicializado correctamente[/green]")
    except Exception as e:
        console.print(f"[red]✗ Error inicializando FacebookProfileDownloader: {e}[/red]")
    
    console.print("[bold green]Tests básicos completados![/bold green]")

if __name__ == "__main__":
    run_basic_tests() 
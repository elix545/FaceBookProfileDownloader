"""
Image Processor Module
Maneja el procesamiento de imágenes con IA (Ollama) y OCR (Tesseract)
"""

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        
    async def process_directory(self, photos_dir: Path, model: str = "llava:latest") -> Dict:
        """Procesa todas las imágenes en un directorio"""
        
        start_time = time.time()
        stats = {
            'processed': 0,
            'descriptions': 0,
            'ocr_texts': 0,
            'errors': 0,
            'duration': 0
        }
        
        try:
            # Obtener lista de imágenes
            image_files = self._get_image_files(photos_dir)
            
            if not image_files:
                logger.warning(f"No se encontraron imágenes en {photos_dir}")
                return stats
            
            logger.info(f"Procesando {len(image_files)} imágenes")
            
            # Procesar cada imagen
            for image_file in image_files:
                try:
                    await self._process_single_image(image_file, model, stats)
                    stats['processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error procesando {image_file.name}: {str(e)}")
                    stats['errors'] += 1
                
                # Pausa entre procesamientos
                await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error durante el procesamiento: {str(e)}")
            stats['errors'] += 1
        
        stats['duration'] = time.time() - start_time
        return stats
    
    def _get_image_files(self, directory: Path) -> List[Path]:
        """Obtiene lista de archivos de imagen en el directorio"""
        image_files = []
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                image_files.append(file_path)
        
        return sorted(image_files)
    
    async def _process_single_image(self, image_path: Path, model: str, stats: Dict):
        """Procesa una imagen individual"""
        
        # Verificar si ya fue procesada
        desc_file = image_path.with_suffix('.desc.txt')
        ocr_file = image_path.with_suffix('.ocr.txt')
        
        # Generar descripción con IA si no existe
        if not desc_file.exists():
            try:
                description = await self._generate_description(image_path, model)
                if description:
                    await self._save_text_file(desc_file, description)
                    stats['descriptions'] += 1
                    logger.info(f"Descripción generada para {image_path.name}")
            except Exception as e:
                logger.error(f"Error generando descripción para {image_path.name}: {str(e)}")
        
        # Extraer texto con OCR si no existe
        if not ocr_file.exists():
            try:
                ocr_text = await self._extract_text_ocr(image_path)
                if ocr_text:
                    await self._save_text_file(ocr_file, ocr_text)
                    stats['ocr_texts'] += 1
                    logger.info(f"Texto OCR extraído para {image_path.name}")
            except Exception as e:
                logger.error(f"Error en OCR para {image_path.name}: {str(e)}")
    
    async def _generate_description(self, image_path: Path, model: str) -> Optional[str]:
        """Genera descripción de la imagen usando Ollama"""
        
        try:
            # Comando para Ollama
            cmd = [
                'ollama', 'run', model,
                f'Describe esta imagen en español de manera detallada: {image_path}'
            ]
            
            # Ejecutar comando
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                description = stdout.decode('utf-8').strip()
                return description
            else:
                logger.error(f"Error en Ollama: {stderr.decode('utf-8')}")
                return None
                
        except Exception as e:
            logger.error(f"Error ejecutando Ollama: {str(e)}")
            return None
    
    async def _extract_text_ocr(self, image_path: Path) -> Optional[str]:
        """Extrae texto de la imagen usando Tesseract OCR"""
        
        try:
            # Abrir imagen con PIL
            with Image.open(image_path) as img:
                # Convertir a RGB si es necesario
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Extraer texto con Tesseract
                text = pytesseract.image_to_string(img, lang='spa+eng')
                
                # Limpiar texto
                text = text.strip()
                
                if text:
                    return text
                else:
                    return "No se detectó texto en la imagen"
                    
        except Exception as e:
            logger.error(f"Error en OCR: {str(e)}")
            return None
    
    async def _save_text_file(self, file_path: Path, content: str):
        """Guarda contenido en un archivo de texto"""
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
        except Exception as e:
            logger.error(f"Error guardando archivo {file_path}: {str(e)}")
    
    async def process_single_image(self, image_path: Path, model: str = "llava:latest") -> Dict:
        """Procesa una imagen individual y retorna estadísticas"""
        
        stats = {
            'description_generated': False,
            'ocr_extracted': False,
            'errors': 0
        }
        
        try:
            # Verificar que el archivo existe
            if not image_path.exists():
                raise FileNotFoundError(f"Archivo no encontrado: {image_path}")
            
            # Verificar formato soportado
            if image_path.suffix.lower() not in self.supported_formats:
                raise ValueError(f"Formato no soportado: {image_path.suffix}")
            
            # Generar descripción
            desc_file = image_path.with_suffix('.desc.txt')
            if not desc_file.exists():
                description = await self._generate_description(image_path, model)
                if description:
                    await self._save_text_file(desc_file, description)
                    stats['description_generated'] = True
            
            # Extraer texto OCR
            ocr_file = image_path.with_suffix('.ocr.txt')
            if not ocr_file.exists():
                ocr_text = await self._extract_text_ocr(image_path)
                if ocr_text:
                    await self._save_text_file(ocr_file, ocr_text)
                    stats['ocr_extracted'] = True
            
        except Exception as e:
            logger.error(f"Error procesando imagen: {str(e)}")
            stats['errors'] += 1
        
        return stats
    
    def get_processing_status(self, image_path: Path) -> Dict:
        """Obtiene el estado de procesamiento de una imagen"""
        
        desc_file = image_path.with_suffix('.desc.txt')
        ocr_file = image_path.with_suffix('.ocr.txt')
        
        return {
            'image_exists': image_path.exists(),
            'description_exists': desc_file.exists(),
            'ocr_exists': ocr_file.exists(),
            'description_size': desc_file.stat().st_size if desc_file.exists() else 0,
            'ocr_size': ocr_file.stat().st_size if ocr_file.exists() else 0
        }
    
    async def cleanup_processed_files(self, directory: Path):
        """Limpia archivos de procesamiento (descripciones y OCR)"""
        
        try:
            files_removed = 0
            
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix in ['.desc.txt', '.ocr.txt']:
                    file_path.unlink()
                    files_removed += 1
            
            logger.info(f"Archivos de procesamiento eliminados: {files_removed}")
            
        except Exception as e:
            logger.error(f"Error limpiando archivos: {str(e)}")
    
    def validate_ollama_installation(self) -> bool:
        """Verifica si Ollama está instalado y funcionando"""
        
        try:
            result = subprocess.run(['ollama', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False
    
    def validate_tesseract_installation(self) -> bool:
        """Verifica si Tesseract está instalado y funcionando"""
        
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False 
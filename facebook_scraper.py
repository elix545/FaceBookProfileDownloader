"""
Facebook Scraper Module
Maneja la extracción de fotos y videos de perfiles de Facebook
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

class FacebookScraper:
    def __init__(self):
        self.base_url = "https://www.facebook.com"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        )
        self.page = await self.browser.new_page()
        
        # Configurar user agent
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def get_profile_info(self, username: str) -> Dict:
        """Obtiene información básica del perfil"""
        profile_url = f"{self.base_url}/{username}"
        
        try:
            await self.page.goto(profile_url, wait_until='networkidle')
            
            # Esperar a que cargue el contenido
            await self.page.wait_for_selector('[data-testid="profile_tab_container"]', timeout=10000)
            
            # Extraer información del perfil
            info = {}
            
            # Nombre del perfil
            try:
                name_element = await self.page.query_selector('h1')
                if name_element:
                    info['nombre'] = await name_element.text_content()
            except:
                info['nombre'] = username
            
            # Descripción
            try:
                desc_element = await self.page.query_selector('[data-testid="profile_tab_container"] p')
                if desc_element:
                    info['descripcion'] = await desc_element.text_content()
            except:
                info['descripcion'] = "No disponible"
            
            # URL del perfil
            info['url'] = profile_url
            
            return info
            
        except Exception as e:
            logger.error(f"Error obteniendo información del perfil {username}: {str(e)}")
            return {
                'nombre': username,
                'descripcion': 'Error al obtener información',
                'url': profile_url
            }
    
    async def scrape_profile(
        self, 
        username: str, 
        photos_dir: Path, 
        videos_dir: Path,
        max_photos: int = 0,
        max_videos: int = 0
    ) -> Dict:
        """Extrae fotos y videos del perfil de Facebook"""
        
        start_time = time.time()
        stats = {
            'photos': 0,
            'videos': 0,
            'errors': 0,
            'duration': 0
        }
        
        try:
            # Navegar al perfil
            profile_url = f"{self.base_url}/{username}"
            await self.page.goto(profile_url, wait_until='networkidle')
            
            # Verificar si necesitamos login
            if await self._needs_login():
                logger.warning("Se requiere login para acceder a este perfil")
                # Aquí podrías implementar login automático si es necesario
            
            # Navegar a la pestaña de fotos
            await self._navigate_to_photos_tab()
            
            # Descargar fotos
            if max_photos != 0:
                stats['photos'] = await self._download_photos(photos_dir, max_photos)
            
            # Navegar a la pestaña de videos
            await self._navigate_to_videos_tab()
            
            # Descargar videos
            if max_videos != 0:
                stats['videos'] = await self._download_videos(videos_dir, max_videos)
            
        except Exception as e:
            logger.error(f"Error durante el scraping: {str(e)}")
            stats['errors'] += 1
        
        stats['duration'] = time.time() - start_time
        return stats
    
    async def _needs_login(self) -> bool:
        """Verifica si se requiere login"""
        try:
            # Buscar elementos que indiquen que se requiere login
            login_indicators = [
                'text="Log In"',
                'text="Iniciar sesión"',
                '[data-testid="login_button"]',
                '.login-button'
            ]
            
            for indicator in login_indicators:
                element = await self.page.query_selector(indicator)
                if element:
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def _navigate_to_photos_tab(self):
        """Navega a la pestaña de fotos"""
        try:
            # Intentar diferentes selectores para la pestaña de fotos
            photo_tab_selectors = [
                'a[href*="/photos"]',
                '[data-testid="photos_tab"]',
                'a:has-text("Photos")',
                'a:has-text("Fotos")'
            ]
            
            for selector in photo_tab_selectors:
                try:
                    photo_tab = await self.page.query_selector(selector)
                    if photo_tab:
                        await photo_tab.click()
                        await self.page.wait_for_load_state('networkidle')
                        return
                except:
                    continue
            
            logger.warning("No se pudo encontrar la pestaña de fotos")
            
        except Exception as e:
            logger.error(f"Error navegando a la pestaña de fotos: {str(e)}")
    
    async def _navigate_to_videos_tab(self):
        """Navega a la pestaña de videos"""
        try:
            # Intentar diferentes selectores para la pestaña de videos
            video_tab_selectors = [
                'a[href*="/videos"]',
                '[data-testid="videos_tab"]',
                'a:has-text("Videos")',
                'a:has-text("Vídeos")'
            ]
            
            for selector in video_tab_selectors:
                try:
                    video_tab = await self.page.query_selector(selector)
                    if video_tab:
                        await video_tab.click()
                        await self.page.wait_for_load_state('networkidle')
                        return
                except:
                    continue
            
            logger.warning("No se pudo encontrar la pestaña de videos")
            
        except Exception as e:
            logger.error(f"Error navegando a la pestaña de videos: {str(e)}")
    
    async def _download_photos(self, photos_dir: Path, max_photos: int) -> int:
        """Descarga las fotos del perfil"""
        downloaded = 0
        
        try:
            # Scroll para cargar más fotos
            await self._scroll_to_load_content()
            
            # Buscar enlaces de fotos
            photo_links = await self._find_photo_links()
            
            for i, photo_url in enumerate(photo_links):
                if max_photos > 0 and downloaded >= max_photos:
                    break
                
                try:
                    filename = f"foto_{downloaded + 1:04d}.jpg"
                    filepath = photos_dir / filename
                    
                    if await self._download_file(photo_url, filepath):
                        downloaded += 1
                        logger.info(f"Foto descargada: {filename}")
                        
                        # Guardar metadatos
                        await self._save_metadata(filepath, {
                            'url': photo_url,
                            'fecha_descarga': datetime.now().isoformat(),
                            'tipo': 'foto'
                        })
                    
                except Exception as e:
                    logger.error(f"Error descargando foto {i}: {str(e)}")
                    continue
                
                # Pausa entre descargas
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error durante la descarga de fotos: {str(e)}")
        
        return downloaded
    
    async def _download_videos(self, videos_dir: Path, max_videos: int) -> int:
        """Descarga los videos del perfil"""
        downloaded = 0
        
        try:
            # Scroll para cargar más videos
            await self._scroll_to_load_content()
            
            # Buscar enlaces de videos
            video_links = await self._find_video_links()
            
            for i, video_url in enumerate(video_links):
                if max_videos > 0 and downloaded >= max_videos:
                    break
                
                try:
                    filename = f"video_{downloaded + 1:04d}.mp4"
                    filepath = videos_dir / filename
                    
                    if await self._download_file(video_url, filepath):
                        downloaded += 1
                        logger.info(f"Video descargado: {filename}")
                        
                        # Guardar metadatos
                        await self._save_metadata(filepath.with_suffix('.json'), {
                            'url': video_url,
                            'fecha_descarga': datetime.now().isoformat(),
                            'tipo': 'video'
                        })
                    
                except Exception as e:
                    logger.error(f"Error descargando video {i}: {str(e)}")
                    continue
                
                # Pausa entre descargas
                await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error durante la descarga de videos: {str(e)}")
        
        return downloaded
    
    async def _scroll_to_load_content(self):
        """Hace scroll para cargar más contenido"""
        try:
            for _ in range(5):  # Scroll 5 veces
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                # Esperar a que cargue nuevo contenido
                await self.page.wait_for_timeout(2000)
                
        except Exception as e:
            logger.error(f"Error durante el scroll: {str(e)}")
    
    async def _find_photo_links(self) -> List[str]:
        """Encuentra enlaces de fotos en la página"""
        try:
            # Buscar elementos de imagen
            photo_elements = await self.page.query_selector_all('img[src*="scontent"]')
            
            photo_urls = []
            for element in photo_elements:
                src = await element.get_attribute('src')
                if src and 'scontent' in src:
                    # Obtener URL de alta resolución
                    high_res_url = self._get_high_resolution_url(src)
                    if high_res_url:
                        photo_urls.append(high_res_url)
            
            return list(set(photo_urls))  # Eliminar duplicados
            
        except Exception as e:
            logger.error(f"Error encontrando enlaces de fotos: {str(e)}")
            return []
    
    async def _find_video_links(self) -> List[str]:
        """Encuentra enlaces de videos en la página"""
        try:
            # Buscar elementos de video
            video_elements = await self.page.query_selector_all('video source, video[src]')
            
            video_urls = []
            for element in video_elements:
                src = await element.get_attribute('src')
                if src:
                    video_urls.append(src)
            
            return list(set(video_urls))  # Eliminar duplicados
            
        except Exception as e:
            logger.error(f"Error encontrando enlaces de videos: {str(e)}")
            return []
    
    def _get_high_resolution_url(self, url: str) -> Optional[str]:
        """Convierte URL de imagen a alta resolución"""
        try:
            # Facebook usa parámetros para diferentes resoluciones
            # Eliminar parámetros de tamaño para obtener la imagen original
            base_url = url.split('?')[0]
            return base_url
        except:
            return url
    
    async def _download_file(self, url: str, filepath: Path) -> bool:
        """Descarga un archivo desde una URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(content)
                        return True
                    else:
                        logger.warning(f"Error HTTP {response.status} para {url}")
                        return False
        except Exception as e:
            logger.error(f"Error descargando {url}: {str(e)}")
            return False
    
    async def _save_metadata(self, filepath: Path, metadata: Dict):
        """Guarda metadatos en un archivo JSON"""
        try:
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error guardando metadatos: {str(e)}") 
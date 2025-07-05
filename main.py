#!/usr/bin/env python3
"""
Facebook Profile Downloader
Herramienta CLI para descargar fotos y videos de perfiles de Facebook
"""

import typer
from pathlib import Path
from rich import print
from playwright.sync_api import sync_playwright
import requests
from urllib.parse import urlparse, parse_qs
import re
import logging
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import json
import pytesseract
from PIL import Image
import subprocess

app = typer.Typer(help="Descarga todas las imágenes y videos de un perfil de Facebook, organizando el contenido en carpetas y guardando metadatos.")

@app.command()
def descargar(
    usuario: str = typer.Argument(..., help="Nombre de usuario de Facebook (sin @)"),
    ruta: Path = typer.Option("./descargas", help="Ruta base para descargas (por defecto ./descargas)"),
    max_fotos: int = typer.Option(0, help="Máximo de fotos a descargar (0 = sin límite)"),
    max_videos: int = typer.Option(0, help="Máximo de videos a descargar (0 = sin límite)")
):
    """Descarga imágenes y videos de un perfil de Facebook."""
    if not usuario or not usuario.strip():
        print("[red]Debes ingresar un nombre de usuario válido.[/]")
        raise typer.Exit(code=1)
    if not isinstance(ruta, Path):
        ruta = Path(ruta)
    
    # Crear el directorio base si no existe
    ruta.mkdir(parents=True, exist_ok=True)
    
    log_file = ruta / 'descarga.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    print(f"[bold green]Iniciando descarga para:[/] {usuario}")
    print(f"[bold blue]Ruta de descarga:[/] {ruta}")
    logger.info(f"Iniciando descarga para: {usuario}")
    logger.info(f"Ruta de descarga: {ruta}")

    perfil_dir = ruta / usuario
    imagenes_dir = perfil_dir / "imagenes"
    videos_dir = perfil_dir / "videos"

    for d in [imagenes_dir, videos_dir]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[green]Directorio creado o existente:[/] {d}")
        logger.info(f"Directorio creado o existente: {d}")

    # Aquí irá la lógica de scraping y descarga
    perfil_url = f"https://www.facebook.com/{usuario}"
    print(f"[yellow]Abriendo perfil:[/] {perfil_url}")
    logger.info(f"Abriendo perfil: {perfil_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        # Configurar viewport para parecer más humano
        page.set_viewport_size({"width": 1366, "height": 768})
        # Ejecutar script para ocultar webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        if not safe_goto(page, perfil_url, logger):
            browser.close()
            return
        print("[yellow]Si ves la página de login, inicia sesión manualmente en la ventana del navegador y presiona Enter aquí para continuar...[/]")
        input("Presiona Enter para continuar una vez hayas iniciado sesión (si es necesario)...")

        # --- Scraping de fotos ---
        print("[yellow]Recolectando enlaces de fotos...[/]")
        logger.info("Recolectando enlaces de fotos...")
        
        # Navegar a la pestaña de fotos
        navigate_to_photos_tab(page, logger)
        
        photo_links = set()
        last_height = 0
        scroll_tries = 0
        max_scroll_tries = 10
        while scroll_tries < max_scroll_tries:
            page.wait_for_timeout(2000)
            # Extrae todos los enlaces de fotos visibles
            anchors = page.query_selector_all('a[href*="/photo/"]')
            for a in anchors:
                href = a.get_attribute('href')
                if href and href.startswith('https://www.facebook.com/'):
                    photo_links.add(href)
            # Scroll al fondo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                scroll_tries += 1
            else:
                scroll_tries = 0
            last_height = new_height
        print(f"[bold cyan]Total de fotos encontradas:[/] {len(photo_links)}")
        logger.info(f"Total de fotos encontradas: {len(photo_links)}")
        for link in photo_links:
            print(link)
            logger.info(f"Foto encontrada: {link}")

        # --- Scraping de videos ---
        print("[yellow]Recolectando enlaces de videos...[/]")
        logger.info("Recolectando enlaces de videos...")
        
        # Navegar a la pestaña de videos
        navigate_to_videos_tab(page, logger)
        
        video_links = set()
        last_height = 0
        scroll_tries = 0
        max_scroll_tries = 10
        while scroll_tries < max_scroll_tries:
            page.wait_for_timeout(2000)
            # Extrae todos los enlaces de videos visibles
            anchors = page.query_selector_all('a[href*="/video/"]')
            for a in anchors:
                href = a.get_attribute('href')
                if href and href.startswith('https://www.facebook.com/'):
                    video_links.add(href)
            # Scroll al fondo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                scroll_tries += 1
            else:
                scroll_tries = 0
            last_height = new_height
        print(f"[bold cyan]Total de videos encontrados:[/] {len(video_links)}")
        logger.info(f"Total de videos encontrados: {len(video_links)}")
        for link in video_links:
            print(link)
            logger.info(f"Video encontrado: {link}")

        def sanitize_filename(name):
            return re.sub(r'[^\w\-_\. ]', '_', name)

        total_videos = 0
        total_imagenes = 0
        errores = 0
        
        # Procesar fotos
        for idx, photo_url in enumerate(photo_links, 1):
            if max_fotos and idx > max_fotos:
                print(f"[yellow]Límite de fotos alcanzado ({max_fotos}).[/]")
                break
            print(f"[yellow]Procesando foto {idx}/{len(photo_links)}:[/] {photo_url}")
            logger.info(f"Procesando foto {idx}/{len(photo_links)}: {photo_url}")
            try:
                if not safe_goto(page, photo_url, logger):
                    continue
                # Esperar a que la página de la foto se cargue completamente
                page.wait_for_timeout(5000)
                
                # Extraer metadatos de la foto
                photo_id = get_photo_id_from_url(photo_url)
                meta = {}
                try:
                    # Descripción
                    desc = page.query_selector('[data-testid="post_message"]')
                    if desc:
                        meta['descripcion'] = desc.inner_text()
                    else:
                        meta['descripcion'] = ''
                    # Fecha
                    fecha = page.query_selector('[data-testid="post_timestamp"]')
                    if fecha:
                        meta['fecha'] = fecha.inner_text()
                    else:
                        meta['fecha'] = ''
                    # Hashtags
                    hashtags = []
                    for a in page.query_selector_all('a[href*="/hashtag/"]'):
                        tag = a.inner_text()
                        if tag.startswith('#'):
                            hashtags.append(tag)
                    meta['hashtags'] = hashtags
                    # Autor
                    autor = page.query_selector('[data-testid="post_author"]')
                    if autor:
                        meta['autor'] = autor.inner_text()
                    else:
                        meta['autor'] = usuario
                    # URL
                    meta['url'] = photo_url
                except Exception as e:
                    logger.error(f"Error extrayendo metadatos de {photo_url}: {e}")
                
                # Guardar metadatos
                meta_file = imagenes_dir / f"{photo_id}.json"
                
                # Intentar extraer imagen principal con múltiples selectores
                img_tag = None
                img_selectors = [
                    'img[src*="scontent"]',
                    'img[data-testid="post_image"]',
                    'img[class*="photo"]',
                    'img[src*="facebook"]',
                    'div[data-testid="post_image"] img',
                    'div[class*="photo"] img'
                ]
                
                for selector in img_selectors:
                    try:
                        img_tag = page.query_selector(selector)
                        if img_tag:
                            print(f"[green]Imagen encontrada con selector: {selector}[/]")
                            break
                    except Exception as e:
                        continue
                
                if img_tag:
                    src = img_tag.get_attribute('src')
                    # Verificar si el src es válido
                    if src and (src.startswith('http') or src.startswith('//')):
                        if src.startswith('//'):
                            src = 'https:' + src
                        
                        # Obtener URL de alta resolución
                        high_res_src = get_high_resolution_url(src)
                        
                        filename = sanitize_filename(f"{photo_id}.jpg")
                        dest = imagenes_dir / filename
                        if dest.exists():
                            print(f"[blue]Ya existe:[/] {dest}")
                            logger.info(f"Ya existe: {dest}")
                        else:
                            print(f"[green]Descargando imagen:[/] {dest}")
                            logger.info(f"Descargando imagen: {dest}")
                            try:
                                r = requests.get(high_res_src, stream=True, timeout=30)
                                with open(dest, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                total_imagenes += 1
                            except Exception as e:
                                print(f"[red]Error descargando imagen:[/] {e}")
                                logger.error(f"Error descargando imagen {photo_url}: {e}")
                                errores += 1
                    else:
                        print("[red]No se encontró src de imagen válido.[/]")
                        logger.warning(f"No se encontró src de imagen válido en {photo_url}")
                    
                    # Guardar metadatos junto a la imagen
                    with open(meta_file, 'w', encoding='utf-8') as mf:
                        json.dump(meta, mf, ensure_ascii=False, indent=2)
                else:
                    print("[red]No se encontró imagen para este enlace.[/]")
                    logger.warning(f"No se encontró imagen para {photo_url}")
                    errores += 1
            except Exception as e:
                print(f"[red]Error procesando foto {photo_url}: {e}[/]")
                logger.error(f"Error procesando foto {photo_url}: {e}")
                errores += 1
                continue
        
        # Procesar videos
        for idx, video_url in enumerate(video_links, 1):
            if max_videos and idx > max_videos:
                print(f"[yellow]Límite de videos alcanzado ({max_videos}).[/]")
                break
            print(f"[yellow]Procesando video {idx}/{len(video_links)}:[/] {video_url}")
            logger.info(f"Procesando video {idx}/{len(video_links)}: {video_url}")
            try:
                if not safe_goto(page, video_url, logger):
                    continue
                # Esperar a que la página del video se cargue completamente
                page.wait_for_timeout(5000)
                
                # Extraer metadatos del video
                video_id = get_video_id_from_url(video_url)
                meta = {}
                try:
                    # Descripción
                    desc = page.query_selector('[data-testid="post_message"]')
                    if desc:
                        meta['descripcion'] = desc.inner_text()
                    else:
                        meta['descripcion'] = ''
                    # Fecha
                    fecha = page.query_selector('[data-testid="post_timestamp"]')
                    if fecha:
                        meta['fecha'] = fecha.inner_text()
                    else:
                        meta['fecha'] = ''
                    # Hashtags
                    hashtags = []
                    for a in page.query_selector_all('a[href*="/hashtag/"]'):
                        tag = a.inner_text()
                        if tag.startswith('#'):
                            hashtags.append(tag)
                    meta['hashtags'] = hashtags
                    # Autor
                    autor = page.query_selector('[data-testid="post_author"]')
                    if autor:
                        meta['autor'] = autor.inner_text()
                    else:
                        meta['autor'] = usuario
                    # URL
                    meta['url'] = video_url
                except Exception as e:
                    logger.error(f"Error extrayendo metadatos de {video_url}: {e}")
                
                # Guardar metadatos
                meta_file = videos_dir / f"{video_id}.json"
                
                # Intentar extraer video principal con múltiples selectores
                video_tag = None
                video_selectors = [
                    'video',
                    'video[data-testid]',
                    'video[data-testid="post_video"]',
                    'video[class*="video"]',
                    'video[src]',
                    'div[data-testid="post_video"] video',
                    'div[class*="video"] video'
                ]
                
                for selector in video_selectors:
                    try:
                        video_tag = page.query_selector(selector)
                        if video_tag:
                            print(f"[green]Video encontrado con selector: {selector}[/]")
                            break
                    except Exception as e:
                        continue
                
                # Si no encuentra video, intentar buscar en iframes
                if not video_tag:
                    try:
                        iframes = page.query_selector_all('iframe')
                        for iframe in iframes:
                            try:
                                iframe_video = iframe.query_selector('video')
                                if iframe_video:
                                    video_tag = iframe_video
                                    print("[green]Video encontrado en iframe[/]")
                                    break
                            except:
                                continue
                    except Exception as e:
                        pass
                
                if video_tag:
                    src = video_tag.get_attribute('src')
                    # Verificar si el src es válido o buscar en data-src
                    if not src or not src.startswith('http'):
                        src = video_tag.get_attribute('data-src')
                    
                    if src and (src.startswith('http') or src.startswith('//')):
                        if src.startswith('//'):
                            src = 'https:' + src
                        
                        filename = sanitize_filename(f"{video_id}.mp4")
                        dest = videos_dir / filename
                        if dest.exists():
                            print(f"[blue]Ya existe:[/] {dest}")
                            logger.info(f"Ya existe: {dest}")
                        else:
                            print(f"[green]Descargando video:[/] {dest}")
                            logger.info(f"Descargando video: {dest}")
                            try:
                                r = requests.get(src, stream=True, timeout=30)
                                with open(dest, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                total_videos += 1
                            except Exception as e:
                                print(f"[red]Error descargando video:[/] {e}")
                                logger.error(f"Error descargando video {video_url}: {e}")
                                errores += 1
                    else:
                        print("[red]No se encontró src de video válido.[/]")
                        logger.warning(f"No se encontró src de video válido en {video_url}")
                    
                    # Guardar metadatos junto al video
                    with open(meta_file, 'w', encoding='utf-8') as mf:
                        json.dump(meta, mf, ensure_ascii=False, indent=2)
                else:
                    print("[red]No se encontró video para este enlace.[/]")
                    logger.warning(f"No se encontró video para {video_url}")
                    errores += 1
            except Exception as e:
                print(f"[red]Error procesando video {video_url}: {e}[/]")
                logger.error(f"Error procesando video {video_url}: {e}")
                errores += 1
                continue
        browser.close()

    print(f"\n[bold green]Resumen de descarga:[/]")
    print(f"Fotos descargadas: [cyan]{total_imagenes}[/]")
    print(f"Videos descargados: [cyan]{total_videos}[/]")
    print(f"Errores: [red]{errores}[/]")
    logger.info(f"Resumen: Fotos={total_imagenes}, Videos={total_videos}, Errores={errores}")

@app.command()
def procesar_imagenes(
    usuario: str = typer.Argument(..., help="Nombre de usuario de Facebook (sin @)"),
    ruta: Path = typer.Option("./descargas", help="Ruta base para descargas (por defecto ./descargas)"),
    modelo: str = typer.Option("llava:latest", help="Modelo de Ollama para descripción de imágenes")
):
    """Procesa imágenes descargadas: genera descripción con Ollama y extrae texto con Tesseract solo para imágenes sin .txt asociado."""
    imagenes_dir = Path(ruta) / usuario / "imagenes"
    if not imagenes_dir.exists():
        print(f"[red]No existe el directorio de imágenes: {imagenes_dir}[/]")
        raise typer.Exit(code=1)
    imagenes = list(imagenes_dir.glob("*.jpg"))
    nuevas = [img for img in imagenes if not (img.with_suffix('.desc.txt').exists() or img.with_suffix('.ocr.txt').exists())]
    print(f"[bold]Imágenes a procesar:[/] {len(nuevas)} de {len(imagenes)}")
    for img_path in nuevas:
        print(f"[yellow]Procesando:[/] {img_path.name}")
        # Descripción con Ollama
        desc_txt = img_path.with_suffix('.desc.txt')
        try:
            prompt = "Describe la imagen de manera detallada en español."
            result = subprocess.run([
                "ollama", "run", modelo, "--image", str(img_path), prompt
            ], capture_output=True, text=True, timeout=120)
            desc = result.stdout.strip()
            with open(desc_txt, 'w', encoding='utf-8') as f:
                f.write(desc)
            print(f"[green]Descripción generada:[/] {desc_txt.name}")
        except Exception as e:
            print(f"[red]Error con Ollama:[/] {e}")
        # OCR con Tesseract
        ocr_txt = img_path.with_suffix('.ocr.txt')
        try:
            texto = pytesseract.image_to_string(Image.open(img_path), lang='spa')
            with open(ocr_txt, 'w', encoding='utf-8') as f:
                f.write(texto)
            print(f"[green]Texto extraído:[/] {ocr_txt.name}")
        except Exception as e:
            print(f"[red]Error con Tesseract:[/] {e}")
    print("[bold green]Procesamiento finalizado.[/]")

@app.command()
def info(
    usuario: str = typer.Argument(..., help="Nombre de usuario de Facebook (sin @)")
):
    """Muestra información básica de un perfil de Facebook."""
    perfil_url = f"https://www.facebook.com/{usuario}"
    print(f"[yellow]Obteniendo información del perfil:[/] {perfil_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            if safe_goto(page, perfil_url):
                # Extraer información del perfil
                info = {}
                
                # Nombre del perfil
                name_element = page.query_selector('h1')
                if name_element:
                    info['nombre'] = name_element.inner_text()
                else:
                    info['nombre'] = usuario
                
                # Descripción
                desc_element = page.query_selector('[data-testid="profile_tab_container"] p')
                if desc_element:
                    info['descripcion'] = desc_element.inner_text()
                else:
                    info['descripcion'] = "No disponible"
                
                # URL del perfil
                info['url'] = perfil_url
                
                print(f"\n[bold green]Información del perfil:[/]")
                for key, value in info.items():
                    print(f"{key.title()}: [cyan]{value}[/]")
            else:
                print("[red]No se pudo cargar el perfil.[/]")
        except Exception as e:
            print(f"[red]Error obteniendo información: {e}[/]")
        finally:
            browser.close()

def safe_goto(page, url, logger=None, max_retries=3, wait=3000):
    for attempt in range(1, max_retries+1):
        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(wait)
            # Verificar que la página cargó correctamente
            if page.url and "facebook.com" in page.url:
                return True
            return True
        except PlaywrightTimeoutError as e:
            print(f"[red]Timeout al cargar {url}. Intento {attempt}/{max_retries}.[/]")
            if logger:
                logger.error(f"Timeout al cargar {url}: {e}")
            time.sleep(3 * attempt)
    print(f"[red]No se pudo cargar {url} tras {max_retries} intentos.[/]")
    if logger:
        logger.error(f"No se pudo cargar {url} tras {max_retries} intentos.")
    return False

def navigate_to_photos_tab(page, logger):
    """Navega a la pestaña de fotos del perfil."""
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
                photo_tab = page.query_selector(selector)
                if photo_tab:
                    photo_tab.click()
                    page.wait_for_timeout(3000)
                    print(f"[green]Navegado a pestaña de fotos con selector: {selector}[/]")
                    return True
            except:
                continue
        
        print("[yellow]No se pudo encontrar la pestaña de fotos[/]")
        return False
        
    except Exception as e:
        logger.error(f"Error navegando a la pestaña de fotos: {str(e)}")
        return False

def navigate_to_videos_tab(page, logger):
    """Navega a la pestaña de videos del perfil."""
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
                video_tab = page.query_selector(selector)
                if video_tab:
                    video_tab.click()
                    page.wait_for_timeout(3000)
                    print(f"[green]Navegado a pestaña de videos con selector: {selector}[/]")
                    return True
            except:
                continue
        
        print("[yellow]No se pudo encontrar la pestaña de videos[/]")
        return False
        
    except Exception as e:
        logger.error(f"Error navegando a la pestaña de videos: {str(e)}")
        return False

def get_high_resolution_url(url):
    """Convierte URL de imagen de Facebook a alta resolución."""
    try:
        # Facebook usa parámetros para diferentes resoluciones
        # Eliminar parámetros de tamaño para obtener la imagen original
        base_url = url.split('?')[0]
        return base_url
    except:
        return url

def get_photo_id_from_url(url):
    """Genera un ID único y sanitizado para fotos basado en la URL."""
    try:
        parsed = urlparse(url)
        # Extraer fbid de los parámetros de query
        query_params = parse_qs(parsed.query)
        fbid = query_params.get('fbid', ['unknown'])[0]
        set_param = query_params.get('set', ['unknown'])[0]
        
        # Crear un ID único combinando fbid y set
        photo_id = f"photo_{fbid}_{set_param}"
        return sanitize_filename(photo_id)
    except:
        # Fallback: usar hash de la URL completa
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"photo_{url_hash}"

def get_video_id_from_url(url):
    """Genera un ID único y sanitizado para videos basado en la URL."""
    try:
        parsed = urlparse(url)
        # Extraer el último segmento del path
        path_segments = [seg for seg in parsed.path.split('/') if seg]
        if path_segments:
            video_id = path_segments[-1]
        else:
            # Si no hay path, usar hash de la URL
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            video_id = f"video_{url_hash}"
        
        return sanitize_filename(video_id)
    except:
        # Fallback: usar hash de la URL completa
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"video_{url_hash}"

if __name__ == "__main__":
    app() 

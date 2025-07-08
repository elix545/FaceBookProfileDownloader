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

def sanitize_filename(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

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
        processed_photos = set()  # Para evitar procesar la misma foto múltiples veces
        last_height = 0
        scroll_tries = 0
        max_scroll_tries = 30  # Aumentar el número de intentos
        no_new_content_count = 0
        max_no_new_content = 8  # Si no encuentra contenido nuevo en 8 intentos, parar
        
        # Variables para el procesamiento
        total_imagenes = 0
        total_videos = 0
        errores = 0
        
        def process_photo_links(new_links, logger):
            """Procesa las fotos encontradas mientras se hace scroll"""
            nonlocal total_imagenes, errores
            logger.info(f"Iniciando procesamiento de {len(new_links)} nuevas fotos")
            
            for i, photo_url in enumerate(new_links, 1):
                if photo_url in processed_photos:
                    logger.debug(f"Foto ya procesada, saltando: {photo_url}")
                    continue
                    
                processed_photos.add(photo_url)
                print(f"[yellow]Procesando foto {i}/{len(new_links)}:[/] {photo_url}")
                logger.info(f"Procesando foto {i}/{len(new_links)}: {photo_url}")
                
                try:
                    logger.info(f"Navegando a página de foto: {photo_url}")
                    if not safe_goto(page, photo_url, logger):
                        logger.error(f"No se pudo navegar a la página de la foto: {photo_url}")
                        continue
                    
                    # Esperar a que la página de la foto se cargue completamente
                    logger.info("Esperando carga completa de la página de foto")
                    page.wait_for_timeout(3000)
                    
                    # Extraer metadatos de la foto
                    photo_id = get_photo_id_from_url(photo_url)
                    logger.info(f"ID de foto extraído: {photo_id}")
                    
                    meta = {}
                    try:
                        logger.info("Extrayendo metadatos de la foto")
                        
                        # Descripción
                        desc = page.query_selector('[data-testid="post_message"]')
                        if desc:
                            meta['descripcion'] = desc.inner_text()
                            logger.debug(f"Descripción extraída: {meta['descripcion'][:100]}...")
                        else:
                            meta['descripcion'] = ''
                            logger.debug("No se encontró descripción")
                        
                        # Fecha
                        fecha = page.query_selector('[data-testid="post_timestamp"]')
                        if fecha:
                            meta['fecha'] = fecha.inner_text()
                            logger.debug(f"Fecha extraída: {meta['fecha']}")
                        else:
                            meta['fecha'] = ''
                            logger.debug("No se encontró fecha")
                        
                        # Hashtags
                        hashtags = []
                        hashtag_elements = page.query_selector_all('a[href*="/hashtag/"]')
                        logger.debug(f"Encontrados {len(hashtag_elements)} elementos de hashtag")
                        for a in hashtag_elements:
                            tag = a.inner_text()
                            if tag.startswith('#'):
                                hashtags.append(tag)
                        meta['hashtags'] = hashtags
                        logger.debug(f"Hashtags extraídos: {hashtags}")
                        
                        # Autor
                        autor = page.query_selector('[data-testid="post_author"]')
                        if autor:
                            meta['autor'] = autor.inner_text()
                            logger.debug(f"Autor extraído: {meta['autor']}")
                        else:
                            meta['autor'] = usuario
                            logger.debug(f"Usando usuario como autor: {usuario}")
                        
                        # URL
                        meta['url'] = photo_url
                        logger.info("Metadatos extraídos exitosamente")
                        
                    except Exception as e:
                        logger.error(f"Error extrayendo metadatos de {photo_url}: {e}")
                    
                    # Guardar metadatos
                    meta_file = imagenes_dir / f"{photo_id}.json"
                    logger.info(f"Guardando metadatos en: {meta_file}")
                    
                    # Intentar extraer imagen principal con múltiples selectores
                    img_tag = None
                    img_selectors = [
                        'img[src*="scontent"]',
                        'img[data-testid="post_image"]',
                        'img[class*="photo"]',
                        'img[src*="facebook"]',
                        'div[data-testid="post_image"] img',
                        'div[class*="photo"] img',
                        'img'  # Selector genérico como último recurso
                    ]
                    
                    logger.info(f"Buscando imagen con {len(img_selectors)} selectores")
                    for j, selector in enumerate(img_selectors, 1):
                        try:
                            logger.debug(f"Probando selector {j}/{len(img_selectors)}: {selector}")
                            img_tag = page.query_selector(selector)
                            if img_tag:
                                print(f"[green]Imagen encontrada con selector: {selector}[/]")
                                logger.info(f"Imagen encontrada con selector: {selector}")
                                break
                            else:
                                logger.debug(f"Selector no encontró imagen: {selector}")
                        except Exception as e:
                            logger.warning(f"Error con selector {selector}: {e}")
                            continue
                    
                    if img_tag:
                        logger.info("Elemento de imagen encontrado, extrayendo atributos")
                        src = img_tag.get_attribute('src')
                        logger.debug(f"Atributo src encontrado: {src}")
                        
                        # Verificar si el src es válido
                        if src and (src.startswith('http') or src.startswith('//')):
                            if src.startswith('//'):
                                src = 'https:' + src
                                logger.debug(f"URL convertida a HTTPS: {src}")
                            
                            # Obtener URL de alta resolución
                            high_res_src = get_high_resolution_url(src)
                            logger.info(f"URL de alta resolución: {high_res_src}")
                            
                            filename = sanitize_filename(f"{photo_id}.jpg")
                            dest = imagenes_dir / filename
                            logger.info(f"Archivo de destino: {dest}")
                            
                            if dest.exists():
                                print(f"[blue]Ya existe:[/] {dest}")
                                logger.info(f"Archivo ya existe, saltando descarga: {dest}")
                            else:
                                print(f"[green]Descargando imagen:[/] {dest}")
                                logger.info(f"Iniciando descarga de imagen: {dest}")
                                # Descargar la imagen usando Playwright request (contexto autenticado)
                                try:
                                    response = page.request.get(high_res_src)
                                    if response.status == 200:
                                        content_type = response.headers.get("content-type", "")
                                        if content_type.startswith("image/"):
                                            img_bytes = response.body()
                                            if img_bytes and len(img_bytes) > 1000:
                                                with open(dest, 'wb') as f:
                                                    f.write(img_bytes)
                                                logger.info(f"Imagen guardada exitosamente: {dest}")
                                                total_imagenes += 1
                                                print(f"[green]✓ Imagen descargada ({len(img_bytes)} bytes)[/]")
                                            else:
                                                logger.error(f"La imagen descargada es muy pequeña o vacía. No se guardó. URL: {high_res_src}")
                                                print(f"[red]La imagen descargada es muy pequeña o vacía. No se guardó.[/]")
                                        else:
                                            logger.error(f"El recurso no es una imagen. Content-Type: {content_type}. URL: {high_res_src}")
                                            print(f"[red]El recurso no es una imagen. Content-Type: {content_type}[/]")
                                    else:
                                        logger.error(f"Error HTTP {response.status} al descargar la imagen. URL: {high_res_src}")
                                        print(f"[red]Error HTTP {response.status} al descargar la imagen.[/]")
                                except Exception as e:
                                    logger.error(f"Error descargando imagen con Playwright request: {e}")
                                    print(f"[yellow]Fallo Playwright request, intentando método fetch en el DOM...[/]")
                                    # Fallback: método fetch en el DOM
                                    try:
                                        img_bytes = page.evaluate("""
                                            async (imgSrc) => {
                                                const response = await fetch(imgSrc, {credentials: 'include'});
                                                const blob = await response.blob();
                                                const arrayBuffer = await blob.arrayBuffer();
                                                return Array.from(new Uint8Array(arrayBuffer));
                                            }
                                        """, high_res_src)
                                        if img_bytes and len(img_bytes) > 1000:
                                            with open(dest, 'wb') as f:
                                                f.write(bytes(img_bytes))
                                            logger.info(f"Imagen guardada exitosamente (fallback): {dest}")
                                            total_imagenes += 1
                                            print(f"[green]✓ Imagen descargada (fallback) ({len(img_bytes)} bytes)[/]")
                                        else:
                                            logger.error(f"El fallback también falló. Imagen muy pequeña o vacía. URL: {high_res_src}")
                                            print(f"[red]El fallback también falló. Imagen muy pequeña o vacía.[/]")
                                    except Exception as e2:
                                        logger.error(f"Error en fallback de descarga de imagen: {e2}")
                                        print(f"[red]Error en fallback de descarga de imagen: {e2}[/]")
                                    errores += 1
                        else:
                            print("[red]No se encontró src de imagen válido.[/]")
                            logger.warning(f"No se encontró src de imagen válido en {photo_url}")
                            logger.debug(f"Valor de src: {src}")
                        
                        # Guardar metadatos junto a la imagen
                        try:
                            with open(meta_file, 'w', encoding='utf-8') as mf:
                                json.dump(meta, mf, ensure_ascii=False, indent=2)
                            logger.info(f"Metadatos guardados exitosamente: {meta_file}")
                        except Exception as e:
                            logger.error(f"Error guardando metadatos: {e}")
                    else:
                        print("[red]No se encontró imagen para este enlace.[/]")
                        logger.warning(f"No se encontró imagen para {photo_url}")
                        logger.debug("Ningún selector encontró un elemento de imagen válido")
                        errores += 1
                except Exception as e:
                    print(f"[red]Error procesando foto {photo_url}: {e}[/]")
                    logger.error(f"Error procesando foto {photo_url}: {e}")
                    errores += 1
                    # Volver a la pestaña de fotos para continuar el scroll
                    navigate_to_photos_tab(page, logger)
                    continue
                
                # Volver a la pestaña de fotos para continuar el scroll
                navigate_to_photos_tab(page, logger)
        
        while scroll_tries < max_scroll_tries and no_new_content_count < max_no_new_content:
            print(f"[cyan]Intento de scroll {scroll_tries + 1}/{max_scroll_tries}[/]")
            logger.info(f"Iniciando intento de scroll {scroll_tries + 1}/{max_scroll_tries}")
            
            # Método 1: Scroll incremental (más efectivo)
            try:
                # Obtener altura actual
                current_height = page.evaluate("document.documentElement.scrollHeight")
                logger.debug(f"Altura actual de la página: {current_height}")
                
                # Scroll incremental (500px a la vez)
                logger.debug("Ejecutando scroll incremental de 500px")
                page.evaluate("window.scrollBy(0, 500)")
                page.wait_for_timeout(1000)
                
                # Scroll adicional para asegurar que cargue
                logger.debug("Ejecutando scroll adicional de 300px")
                page.evaluate("window.scrollBy(0, 300)")
                page.wait_for_timeout(2000)
                
                # Intentar hacer scroll hasta el final de la página
                logger.debug("Ejecutando scroll al final de la página")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(3000)
                
                # Método 2: Usar teclas de flecha (alternativo)
                logger.debug("Ejecutando scroll con tecla End")
                page.keyboard.press("End")
                page.wait_for_timeout(2000)
                
                # Método 3: Scroll suave con JavaScript
                logger.debug("Ejecutando scroll suave")
                page.evaluate("""
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                """)
                page.wait_for_timeout(4000)
                
                logger.info("Scroll completado exitosamente")
                
            except Exception as e:
                print(f"[yellow]Error en scroll: {e}[/]")
                logger.warning(f"Error en scroll: {e}")
                logger.debug(f"Detalles del error de scroll: {type(e).__name__}: {str(e)}")
            
            # Verificar si el scroll funcionó
            new_height = page.evaluate("document.documentElement.scrollHeight")
            print(f"[cyan]Altura anterior: {last_height}, Nueva altura: {new_height}[/]")
            
            if new_height == last_height:
                scroll_tries += 1
                print(f"[yellow]No se detectó cambio de altura en el scroll[/]")
            else:
                scroll_tries = 0
                print(f"[green]Scroll exitoso - Nueva altura detectada[/]")
            last_height = new_height
            
            # Esperar a que cargue el contenido dinámico
            try:
                # Esperar a que aparezcan elementos de carga o contenido
                page.wait_for_timeout(3000)
                
                # Intentar detectar si hay elementos cargando
                loading_elements = page.query_selector_all('[class*="loading"], [class*="spinner"], [class*="skeleton"]')
                if loading_elements:
                    print(f"[yellow]Detectados {len(loading_elements)} elementos cargando, esperando...[/]")
                    page.wait_for_timeout(5000)
                
            except Exception as e:
                print(f"[yellow]Error esperando carga: {e}[/]")
            
            # Ahora buscar enlaces de fotos después del scroll
            initial_count = len(photo_links)
            logger.info(f"Buscando enlaces de fotos (total actual: {initial_count})")
            
            # Extrae todos los enlaces de fotos visibles con múltiples selectores
            photo_selectors = [
                'a[href*="/photo/"]',
                'a[href*="fbid="]',
                'a[data-testid*="photo"]',
                'a[class*="photo"]'
            ]
            
            logger.info(f"Probando {len(photo_selectors)} selectores para enlaces de fotos")
            new_links = set()
            
            for i, selector in enumerate(photo_selectors, 1):
                try:
                    logger.debug(f"Probando selector {i}/{len(photo_selectors)}: {selector}")
                    anchors = page.query_selector_all(selector)
                    logger.debug(f"Encontrados {len(anchors)} elementos con selector: {selector}")
                    
                    for j, a in enumerate(anchors, 1):
                        try:
                            href = a.get_attribute('href')
                            if href and href.startswith('https://www.facebook.com/'):
                                if href not in photo_links:
                                    photo_links.add(href)
                                    new_links.add(href)
                                    logger.debug(f"Nuevo enlace de foto encontrado: {href}")
                                else:
                                    logger.debug(f"Enlace de foto ya existente: {href}")
                            else:
                                logger.debug(f"Enlace no válido: {href}")
                        except Exception as e:
                            logger.warning(f"Error procesando enlace {j} del selector {selector}: {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error con selector {selector}: {e}")
                    continue
            
            # También buscar en elementos de imagen que puedan tener enlaces
            try:
                img_elements = page.query_selector_all('img[src*="scontent"]')
                for img in img_elements:
                    # Buscar el enlace padre más cercano
                    parent_link = img.evaluate("""
                        (img) => {
                            let parent = img.parentElement;
                            while (parent && parent.tagName !== 'A') {
                                parent = parent.parentElement;
                                if (!parent) break;
                            }
                            return parent ? parent.href : null;
                        }
                    """)
                    if parent_link and parent_link.startswith('https://www.facebook.com/'):
                        if parent_link not in photo_links:
                            photo_links.add(parent_link)
                            new_links.add(parent_link)
            except Exception as e:
                print(f"[yellow]Error buscando enlaces en imágenes: {e}[/]")
            
            # Procesar las nuevas fotos encontradas
            if new_links:
                print(f"[green]Encontradas {len(new_links)} nuevas fotos, procesando...[/]")
                process_photo_links(new_links, logger)
                no_new_content_count = 0  # Resetear contador si encontramos contenido nuevo
            else:
                no_new_content_count += 1
                print(f"[yellow]No se encontraron nuevas fotos en el intento {no_new_content_count}/{max_no_new_content}[/]")
                
                # Intentar scroll adicional si no encontramos contenido
                if no_new_content_count >= 3:
                    print(f"[yellow]Intentando scroll adicional...[/]")
                    try:
                        # Scroll más agresivo
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight + 1000)")
                        page.wait_for_timeout(5000)
                        
                        # Intentar hacer clic en "Ver más" si existe
                        ver_mas_buttons = page.query_selector_all('button:has-text("Ver más"), button:has-text("Show more"), a:has-text("Ver más"), a:has-text("Show more")')
                        for button in ver_mas_buttons:
                            try:
                                button.click()
                                print(f"[green]Clic en 'Ver más'[/]")
                                page.wait_for_timeout(3000)
                                break
                            except:
                                continue
                    except Exception as e:
                        print(f"[yellow]Error en scroll adicional: {e}[/]")
            
            print(f"[cyan]Total de fotos encontradas hasta ahora: {len(photo_links)}[/]")
            
            # Verificar límite de fotos
            if max_fotos and len(processed_photos) >= max_fotos:
                print(f"[yellow]Límite de fotos alcanzado ({max_fotos}).[/]")
                break
        
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
        processed_videos = set()  # Para evitar procesar el mismo video múltiples veces
        last_height = 0
        scroll_tries = 0
        max_scroll_tries = 30  # Aumentar el número de intentos
        no_new_content_count = 0
        max_no_new_content = 8  # Si no encuentra contenido nuevo en 8 intentos, parar
        
        def process_video_links(new_links, logger):
            """Procesa los videos encontrados mientras se hace scroll"""
            nonlocal total_videos, errores
            for video_url in new_links:
                if video_url in processed_videos:
                    continue
                    
                processed_videos.add(video_url)
                print(f"[yellow]Procesando video encontrado:[/] {video_url}")
                logger.info(f"Procesando video encontrado: {video_url}")
                
                try:
                    if not safe_goto(page, video_url, logger):
                        continue
                    # Esperar a que la página del video se cargue completamente
                    page.wait_for_timeout(3000)
                    
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
                                        print(f"[green]Video encontrado en iframe[/]")
                                        break
                                except:
                                    continue
                        except Exception as e:
                            logger.error(f"Error buscando video en iframe: {e}")
                    
                    if video_tag:
                        src = video_tag.get_attribute('src')
                        if not src:
                            # Intentar obtener src de source tags dentro del video
                            source_tags = video_tag.query_selector_all('source')
                            for source in source_tags:
                                src = source.get_attribute('src')
                                if src:
                                    break
                        
                        # Verificar si el src es válido
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
                                    # Descargar el video usando Playwright (fetch autenticado)
                                    video_bytes = page.evaluate("""
                                        async (src) => {
                                            const response = await fetch(src, {credentials: 'include'});
                                            const buffer = await response.arrayBuffer();
                                            return Array.from(new Uint8Array(buffer));
                                        }
                                    """, src)
                                    with open(dest, 'wb') as f:
                                        f.write(bytes(video_bytes))
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
                    
                    # Volver a la pestaña de videos para continuar el scroll
                    navigate_to_videos_tab(page, logger)
                    
                except Exception as e:
                    print(f"[red]Error procesando video {video_url}: {e}[/]")
                    logger.error(f"Error procesando video {video_url}: {e}")
                    errores += 1
                    # Volver a la pestaña de videos para continuar el scroll
                    navigate_to_videos_tab(page, logger)
                    continue
        
        while scroll_tries < max_scroll_tries and no_new_content_count < max_no_new_content:
            print(f"[cyan]Intento de scroll de videos {scroll_tries + 1}/{max_scroll_tries}[/]")
            
            # Método 1: Scroll incremental (más efectivo)
            try:
                # Obtener altura actual
                current_height = page.evaluate("document.documentElement.scrollHeight")
                
                # Scroll incremental (500px a la vez)
                page.evaluate("window.scrollBy(0, 500)")
                page.wait_for_timeout(1000)
                
                # Scroll adicional para asegurar que cargue
                page.evaluate("window.scrollBy(0, 300)")
                page.wait_for_timeout(2000)
                
                # Intentar hacer scroll hasta el final de la página
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(3000)
                
                # Método 2: Usar teclas de flecha (alternativo)
                page.keyboard.press("End")
                page.wait_for_timeout(2000)
                
                # Método 3: Scroll suave con JavaScript
                page.evaluate("""
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                """)
                page.wait_for_timeout(4000)
                
            except Exception as e:
                print(f"[yellow]Error en scroll de videos: {e}[/]")
                logger.warning(f"Error en scroll de videos: {e}")
            
            # Verificar si el scroll funcionó
            new_height = page.evaluate("document.documentElement.scrollHeight")
            print(f"[cyan]Altura anterior: {last_height}, Nueva altura: {new_height}[/]")
            
            if new_height == last_height:
                scroll_tries += 1
                print(f"[yellow]No se detectó cambio de altura en el scroll de videos[/]")
            else:
                scroll_tries = 0
                print(f"[green]Scroll de videos exitoso - Nueva altura detectada[/]")
            last_height = new_height
            
            # Esperar a que cargue el contenido dinámico
            try:
                # Esperar a que aparezcan elementos de carga o contenido
                page.wait_for_timeout(3000)
                
                # Intentar detectar si hay elementos cargando
                loading_elements = page.query_selector_all('[class*="loading"], [class*="spinner"], [class*="skeleton"]')
                if loading_elements:
                    print(f"[yellow]Detectados {len(loading_elements)} elementos cargando en videos, esperando...[/]")
                    page.wait_for_timeout(5000)
                
            except Exception as e:
                print(f"[yellow]Error esperando carga de videos: {e}[/]")
            
            # Ahora buscar enlaces de videos después del scroll
            initial_count = len(video_links)
            
            # Extrae todos los enlaces de videos visibles con múltiples selectores
            video_selectors = [
                'a[href*="/video/"]',
                'a[href*="videos/"]',
                'a[data-testid*="video"]',
                'a[class*="video"]'
            ]
            
            new_links = set()
            for selector in video_selectors:
                try:
                    anchors = page.query_selector_all(selector)
                    for a in anchors:
                        href = a.get_attribute('href')
                        if href and href.startswith('https://www.facebook.com/'):
                            if href not in video_links:
                                video_links.add(href)
                                new_links.add(href)
                except Exception as e:
                    continue
            
            # También buscar en elementos de video que puedan tener enlaces
            try:
                video_elements = page.query_selector_all('video')
                for video in video_elements:
                    # Buscar el enlace padre más cercano
                    parent_link = video.evaluate("""
                        (video) => {
                            let parent = video.parentElement;
                            while (parent && parent.tagName !== 'A') {
                                parent = parent.parentElement;
                                if (!parent) break;
                            }
                            return parent ? parent.href : null;
                        }
                    """)
                    if parent_link and parent_link.startswith('https://www.facebook.com/'):
                        if parent_link not in video_links:
                            video_links.add(parent_link)
                            new_links.add(parent_link)
            except Exception as e:
                print(f"[yellow]Error buscando enlaces en videos: {e}[/]")
            
            # Procesar los nuevos videos encontrados
            if new_links:
                print(f"[green]Encontrados {len(new_links)} nuevos videos, procesando...[/]")
                process_video_links(new_links, logger)
                no_new_content_count = 0  # Resetear contador si encontramos contenido nuevo
            else:
                no_new_content_count += 1
                print(f"[yellow]No se encontraron nuevos videos en el intento {no_new_content_count}/{max_no_new_content}[/]")
                
                # Intentar scroll adicional si no encontramos contenido
                if no_new_content_count >= 3:
                    print(f"[yellow]Intentando scroll adicional para videos...[/]")
                    try:
                        # Scroll más agresivo
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight + 1000)")
                        page.wait_for_timeout(5000)
                        
                        # Intentar hacer clic en "Ver más" si existe
                        ver_mas_buttons = page.query_selector_all('button:has-text("Ver más"), button:has-text("Show more"), a:has-text("Ver más"), a:has-text("Show more")')
                        for button in ver_mas_buttons:
                            try:
                                button.click()
                                print(f"[green]Clic en 'Ver más' para videos[/]")
                                page.wait_for_timeout(3000)
                                break
                            except:
                                continue
                    except Exception as e:
                        print(f"[yellow]Error en scroll adicional de videos: {e}[/]")
            
            print(f"[cyan]Total de videos encontrados hasta ahora: {len(video_links)}[/]")
            
            # Verificar límite de videos
            if max_videos and len(processed_videos) >= max_videos:
                print(f"[yellow]Límite de videos alcanzado ({max_videos}).[/]")
                break
        
        print(f"[bold cyan]Total de videos encontrados:[/] {len(video_links)}")
        logger.info(f"Total de videos encontrados: {len(video_links)}")
        for link in video_links:
            print(link)
            logger.info(f"Video encontrado: {link}")

        # Mostrar resumen final
        print(f"\n[bold green]Resumen de descarga:[/]")
        print(f"[cyan]Fotos descargadas:[/] {total_imagenes}")
        print(f"[cyan]Videos descargados:[/] {total_videos}")
        print(f"[cyan]Errores:[/] {errores}")
        print(f"[cyan]Enlaces de fotos encontrados:[/] {len(photo_links)}")
        print(f"[cyan]Enlaces de videos encontrados:[/] {len(video_links)}")
        print(f"[cyan]Fotos procesadas:[/] {len(processed_photos)}")
        print(f"[cyan]Videos procesados:[/] {len(processed_videos)}")
        
        logger.info(f"Resumen final: Fotos={total_imagenes}, Videos={total_videos}, Errores={errores}")
        logger.info(f"Estadísticas: Enlaces_fotos={len(photo_links)}, Enlaces_videos={len(video_links)}")
        logger.info(f"Procesamiento: Fotos_procesadas={len(processed_photos)}, Videos_procesados={len(processed_videos)}")
        
        # Log de configuración utilizada
        logger.info(f"Configuración: max_fotos={max_fotos}, max_videos={max_videos}")
        logger.info(f"Ruta de descarga: {ruta}")
        logger.info(f"Usuario: {usuario}")
        
        browser.close()
        logger.info("Navegador cerrado")

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
    """Navega de forma segura a una URL con reintentos y logging detallado."""
    for attempt in range(1, max_retries+1):
        try:
            logger.info(f"Intentando navegar a {url} (intento {attempt}/{max_retries})")
            page.goto(url, timeout=30000)
            page.wait_for_timeout(wait)
            
            # Verificar que la página cargó correctamente
            current_url = page.url
            logger.info(f"URL actual después de navegación: {current_url}")
            
            if current_url and "facebook.com" in current_url:
                logger.info(f"Navegación exitosa a {url}")
                return True
            else:
                logger.warning(f"URL inesperada después de navegar a {url}: {current_url}")
                return True
                
        except PlaywrightTimeoutError as e:
            print(f"[red]Timeout al cargar {url}. Intento {attempt}/{max_retries}.[/]")
            if logger:
                logger.error(f"Timeout al cargar {url} (intento {attempt}): {e}")
            time.sleep(3 * attempt)
        except Exception as e:
            print(f"[red]Error al cargar {url}. Intento {attempt}/{max_retries}.[/]")
            if logger:
                logger.error(f"Error al cargar {url} (intento {attempt}): {e}")
            time.sleep(3 * attempt)
    
    print(f"[red]No se pudo cargar {url} tras {max_retries} intentos.[/]")
    if logger:
        logger.error(f"No se pudo cargar {url} tras {max_retries} intentos.")
    return False

def navigate_to_photos_tab(page, logger):
    """Navega a la pestaña de fotos del perfil con logging detallado."""
    logger.info("Iniciando navegación a pestaña de fotos")
    
    try:
        # Intentar diferentes selectores para la pestaña de fotos
        photo_tab_selectors = [
            'a[href*="/photos"]',
            '[data-testid="photos_tab"]',
            'a:has-text("Photos")',
            'a:has-text("Fotos")',
            'a[aria-label*="Photos"]',
            'a[aria-label*="Fotos"]',
            'div[role="tab"]:has-text("Photos")',
            'div[role="tab"]:has-text("Fotos")'
        ]
        
        logger.info(f"Probando {len(photo_tab_selectors)} selectores para pestaña de fotos")
        
        for i, selector in enumerate(photo_tab_selectors, 1):
            try:
                logger.info(f"Probando selector {i}/{len(photo_tab_selectors)}: {selector}")
                photo_tab = page.query_selector(selector)
                if photo_tab:
                    logger.info(f"Elemento encontrado con selector: {selector}")
                    
                    # Verificar si el elemento es visible y clickeable
                    is_visible = photo_tab.is_visible()
                    logger.info(f"Elemento visible: {is_visible}")
                    
                    if is_visible:
                        photo_tab.click()
                        page.wait_for_timeout(3000)
                        print(f"[green]Navegado a pestaña de fotos con selector: {selector}[/]")
                        logger.info(f"Navegación exitosa a pestaña de fotos con selector: {selector}")
                        return True
                    else:
                        logger.warning(f"Elemento encontrado pero no visible: {selector}")
                else:
                    logger.debug(f"Selector no encontrado: {selector}")
            except Exception as e:
                logger.warning(f"Error con selector {selector}: {e}")
                continue
        
        # Si no se encuentra con selectores, intentar buscar por texto
        logger.info("Intentando búsqueda por texto en la página")
        try:
            page_content = page.content()
            if "photos" in page_content.lower() or "fotos" in page_content.lower():
                logger.info("Texto 'photos' o 'fotos' encontrado en la página")
                # Intentar hacer clic en cualquier enlace que contenga "photos"
                photo_links = page.query_selector_all('a')
                for link in photo_links:
                    try:
                        href = link.get_attribute('href') or ''
                        text = link.inner_text().lower()
                        if 'photos' in href.lower() or 'photos' in text or 'fotos' in text:
                            logger.info(f"Encontrado enlace de fotos: {href} - {text}")
                            link.click()
                            page.wait_for_timeout(3000)
                            print(f"[green]Navegado a pestaña de fotos por enlace: {href}[/]")
                            return True
                    except:
                        continue
        except Exception as e:
            logger.error(f"Error en búsqueda por texto: {e}")
        
        print("[yellow]No se pudo encontrar la pestaña de fotos[/]")
        logger.warning("No se pudo encontrar la pestaña de fotos con ningún método")
        return False
        
    except Exception as e:
        logger.error(f"Error navegando a la pestaña de fotos: {str(e)}")
        return False

def navigate_to_videos_tab(page, logger):
    """Navega a la pestaña de videos del perfil con logging detallado."""
    logger.info("Iniciando navegación a pestaña de videos")
    
    try:
        # Intentar diferentes selectores para la pestaña de videos
        video_tab_selectors = [
            'a[href*="/videos"]',
            '[data-testid="videos_tab"]',
            'a:has-text("Videos")',
            'a:has-text("Vídeos")',
            'a[aria-label*="Videos"]',
            'a[aria-label*="Vídeos"]',
            'div[role="tab"]:has-text("Videos")',
            'div[role="tab"]:has-text("Vídeos")'
        ]
        
        logger.info(f"Probando {len(video_tab_selectors)} selectores para pestaña de videos")
        
        for i, selector in enumerate(video_tab_selectors, 1):
            try:
                logger.info(f"Probando selector {i}/{len(video_tab_selectors)}: {selector}")
                video_tab = page.query_selector(selector)
                if video_tab:
                    logger.info(f"Elemento encontrado con selector: {selector}")
                    
                    # Verificar si el elemento es visible y clickeable
                    is_visible = video_tab.is_visible()
                    logger.info(f"Elemento visible: {is_visible}")
                    
                    if is_visible:
                        video_tab.click()
                        page.wait_for_timeout(3000)
                        print(f"[green]Navegado a pestaña de videos con selector: {selector}[/]")
                        logger.info(f"Navegación exitosa a pestaña de videos con selector: {selector}")
                        return True
                    else:
                        logger.warning(f"Elemento encontrado pero no visible: {selector}")
                else:
                    logger.debug(f"Selector no encontrado: {selector}")
            except Exception as e:
                logger.warning(f"Error con selector {selector}: {e}")
                continue
        
        # Si no se encuentra con selectores, intentar buscar por texto
        logger.info("Intentando búsqueda por texto en la página")
        try:
            page_content = page.content()
            if "videos" in page_content.lower() or "vídeos" in page_content.lower():
                logger.info("Texto 'videos' o 'vídeos' encontrado en la página")
                # Intentar hacer clic en cualquier enlace que contenga "videos"
                video_links = page.query_selector_all('a')
                for link in video_links:
                    try:
                        href = link.get_attribute('href') or ''
                        text = link.inner_text().lower()
                        if 'videos' in href.lower() or 'videos' in text or 'vídeos' in text:
                            logger.info(f"Encontrado enlace de videos: {href} - {text}")
                            link.click()
                            page.wait_for_timeout(3000)
                            print(f"[green]Navegado a pestaña de videos por enlace: {href}[/]")
                            return True
                    except:
                        continue
        except Exception as e:
            logger.error(f"Error en búsqueda por texto: {e}")
        
        print("[yellow]No se pudo encontrar la pestaña de videos[/]")
        logger.warning("No se pudo encontrar la pestaña de videos con ningún método")
        return False
        
    except Exception as e:
        logger.error(f"Error navegando a la pestaña de videos: {str(e)}")
        return False

def get_high_resolution_url(url):
    """Convierte URL de imagen de Facebook a alta resolución con logging global."""
    try:
        base_url = url.split('?')[0]
        logging.debug(f"URL original: {url} -> URL alta resolución: {base_url}")
        return base_url
    except Exception as e:
        logging.warning(f"Error procesando URL de alta resolución {url}: {e}")
        return url

def get_photo_id_from_url(url):
    """Genera un ID único y sanitizado para fotos basado en la URL con logging global."""
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        fbid = query_params.get('fbid', ['unknown'])[0]
        set_param = query_params.get('set', ['unknown'])[0]
        photo_id = f"photo_{fbid}_{set_param}"
        sanitized_id = sanitize_filename(photo_id)
        logging.debug(f"ID de foto generado: {photo_id} -> {sanitized_id}")
        return sanitized_id
    except Exception as e:
        logging.warning(f"Error generando ID de foto para {url}: {e}")
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        fallback_id = f"photo_{url_hash}"
        logging.info(f"Usando ID de fallback para foto: {fallback_id}")
        return fallback_id

def get_video_id_from_url(url):
    """Genera un ID único y sanitizado para videos basado en la URL con logging global."""
    try:
        parsed = urlparse(url)
        path_segments = [seg for seg in parsed.path.split('/') if seg]
        if path_segments:
            video_id = path_segments[-1]
        else:
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            video_id = f"video_{url_hash}"
        sanitized_id = sanitize_filename(video_id)
        logging.debug(f"ID de video generado: {video_id} -> {sanitized_id}")
        return sanitized_id
    except Exception as e:
        logging.warning(f"Error generando ID de video para {url}: {e}")
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        fallback_id = f"video_{url_hash}"
        logging.info(f"Usando ID de fallback para video: {fallback_id}")
        return fallback_id

if __name__ == "__main__":
    app() 

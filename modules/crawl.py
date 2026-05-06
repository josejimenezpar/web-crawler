"""
modules/crawl.py
================
Fase 3.1 — Rastreo del sitio web (crawling).

Responsabilidades
-----------------
- Navegar el sitio usando un browser Chromium headless (Playwright) para
  obtener el DOM completamente renderizado, incluyendo contenido generado
  por JavaScript.
- Aplicar una estrategia BFS (Breadth-First Search) por niveles de profundidad,
  respetando el límite ``max_depth`` definido en ``Config``.
- Filtrar URLs por dominio, patrones de exclusión y visitas previas.
- Normalizar URLs (eliminar fragmentos ``#``) para evitar duplicados.
- Controlar la concurrencia con un semáforo (máximo 3 tabs simultáneas) y
  respetar el ``delay_seconds`` entre peticiones para no sobrecargar el servidor.

Resultado
---------
Lista de ``PageRecord`` con la URL, profundidad, página origen, snapshot HTML
completo y código de estado HTTP de cada página accesible rastreada.
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser

from modules.config import Config


# ---------------------------------------------------------------------------
# Estructura de datos principal
# ---------------------------------------------------------------------------

@dataclass
class PageRecord:
    """
    Representa una página rastreada y su metadatos asociados.

    Attributes
    ----------
    url : str
        URL normalizada (sin fragmento) de la página.
    depth : int
        Nivel de profundidad desde la URL raíz (0 = página raíz).
    source_url : str
        URL de la página desde la que se descubrió este enlace. Vacío
        para la página raíz.
    html_snapshot : str
        HTML completo del DOM tal como lo devuelve Playwright tras la
        renderización de JavaScript. Se usa en fases posteriores para
        clasificar y validar.
    status_code : int
        Código de respuesta HTTP. Solo se incluyen páginas con 2xx/3xx.
    functional_types : list[str]
        Categorías funcionales asignadas por ``classify.py``.
        Posibles valores: ``home``, ``form``, ``navigation``, ``dynamic``,
        ``informational``. Una página puede tener varios (no excluyente).
    selection_mode : str or None
        Modo de selección asignado por ``selector.py`` o ``validator.py``.
        Valores posibles: ``"directed"``, ``"random"``, o ``None`` si la
        página no ha sido seleccionada aún.
    """

    url: str
    depth: int
    source_url: str
    html_snapshot: str
    status_code: int
    functional_types: List[str] = field(default_factory=list)
    selection_mode: Optional[str] = None


# ---------------------------------------------------------------------------
# Utilidades de URL
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """
    Elimina el fragmento (``#anchor``) de una URL para evitar contar la misma
    página varias veces por diferencias de ancla.

    Los fragmentos son procesados íntegramente por el navegador del cliente y
    no representan páginas distintas en el servidor.
    """
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="")
    return urlunparse(normalized)


def is_same_domain(url: str, root_url: str) -> bool:
    """
    Comprueba que ``url`` pertenece al mismo dominio (netloc) que ``root_url``.

    Esto restringe el rastreo al sitio objetivo e impide seguir enlaces
    externos que no forman parte de la muestra evaluable.
    """
    return urlparse(url).netloc == urlparse(root_url).netloc


def is_excluded(url: str, patterns: List[str]) -> bool:
    """
    Devuelve ``True`` si la URL contiene alguno de los patrones de exclusión.

    La comparación es case-insensitive para cubrir extensiones en mayúsculas
    (.PDF, .JPG, etc.) y variantes de parámetros.
    """
    url_lower = url.lower()
    return any(p.lower() in url_lower for p in patterns)


def extract_links(html: str, base_url: str) -> List[str]:
    """
    Extrae y normaliza todos los hrefs encontrados en las etiquetas ``<a>``
    del HTML proporcionado.

    Los hrefs relativos se resuelven contra ``base_url`` antes de normalizar,
    lo que garantiza que ``../pagina`` o ``/ruta`` se conviertan en URLs
    absolutas correctas.

    Parameters
    ----------
    html : str
        HTML completo de la página de origen.
    base_url : str
        URL absoluta de la página de origen, usada para resolver hrefs relativos.

    Returns
    -------
    list[str]
        Lista de URLs absolutas y normalizadas (sin fragmentos).
    """
    soup = BeautifulSoup(html, "lxml")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        links.append(normalize_url(full_url))
    return links


# ---------------------------------------------------------------------------
# Obtención de página individual
# ---------------------------------------------------------------------------

async def _fetch_page(page: Page, url: str, timeout_ms: int) -> tuple[str, int]:
    """
    Navega a ``url`` con Playwright y devuelve el HTML renderizado y el código
    de estado HTTP.

    Se espera hasta el evento ``domcontentloaded`` (el DOM está construido,
    aunque recursos adicionales como imágenes puedan seguir cargándose). Esto
    es suficiente para obtener el contenido relevante de páginas con JS.

    Si la navegación falla por timeout, error de red o cualquier otra
    excepción, devuelve una cadena vacía y código 0 para que el llamador
    descarte la URL sin interrumpir el proceso.

    Parameters
    ----------
    page : playwright.async_api.Page
        Tab de Playwright abierta y lista para navegar.
    url : str
        URL a cargar.
    timeout_ms : int
        Tiempo máximo de espera en milisegundos (``Config.page_timeout_ms``).

    Returns
    -------
    tuple[str, int]
        ``(html_completo, codigo_http)``
    """
    try:
        response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        status = response.status if response else 0
        html = await page.content()
        return html, status
    except Exception:
        # Fallos silenciosos: timeout, certificado inválido, DNS, etc.
        # Se registran implícitamente al descartar el registro en el llamador.
        return "", 0


# ---------------------------------------------------------------------------
# Función principal de rastreo
# ---------------------------------------------------------------------------

async def crawl(config: Config) -> List[PageRecord]:
    """
    Rastrea el sitio definido en ``config`` y devuelve todos los registros
    de páginas accesibles encontradas.

    Estrategia
    ----------
    Se usa BFS por niveles: todas las URLs del nivel N se procesan antes de
    pasar al nivel N+1. Dentro de cada nivel, las páginas se descargan en
    paralelo (hasta 3 simultáneas, controladas por un semáforo) para
    optimizar el tiempo total de rastreo sin sobrecargar el servidor.

    El delay ``config.delay_seconds`` se aplica después de procesar cada
    página (no entre lotes), funcionando como cortesía mínima hacia el servidor.

    Filtros aplicados antes de encolar una URL
    ------------------------------------------
    1. No visitada previamente (evita ciclos y duplicados).
    2. Mismo dominio que ``config.root_url``.
    3. No coincide con ningún patrón de ``config.exclude_patterns``.
    4. Profundidad dentro del límite ``config.max_depth``.

    Solo se añaden a ``records`` las respuestas con código HTTP 2xx o 3xx
    y contenido HTML no vacío.

    Parameters
    ----------
    config : Config
        Parámetros de ejecución.

    Returns
    -------
    list[PageRecord]
        Registros de todas las páginas rastreadas exitosamente, ordenadas
        aproximadamente por nivel de profundidad (orden BFS).
    """
    visited: set[str] = set()
    records: List[PageRecord] = []

    # Cola BFS: cada elemento es (url, profundidad, url_origen)
    queue: List[tuple[str, int, str]] = [(config.root_url, 0, "")]

    # Semáforo para limitar la concurrencia: evita abrir demasiadas tabs
    # simultáneas y respetar los recursos del servidor y del cliente.
    semaphore = asyncio.Semaphore(3)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)

        # User-agent estándar de Chrome para reducir rechazos por bot-detection
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        async def process_url(url: str, depth: int, source: str) -> tuple[str, int]:
            """Abre una tab, descarga la página y la cierra bajo el semáforo."""
            async with semaphore:
                page = await context.new_page()
                try:
                    html, status = await _fetch_page(page, url, config.page_timeout_ms)
                finally:
                    # Cerrar la tab siempre, incluso si hubo error, para no
                    # agotar los recursos del contexto de Playwright.
                    await page.close()
                return html, status

        while queue:
            # Separar las URLs que están dentro del límite de profundidad.
            # Las que lo superan se mantienen en cola pero nunca se procesan
            # (situación que no debería ocurrir con la lógica de encolado,
            # pero se defiende por robustez).
            current_level = [(u, d, s) for u, d, s in queue if d <= config.max_depth]
            queue = [(u, d, s) for u, d, s in queue if d > config.max_depth]

            if not current_level:
                break

            # Aplicar filtros y marcar como visitadas antes de lanzar las tareas
            # para evitar que el mismo nivel encole la misma URL dos veces.
            tasks = []
            for url, depth, source in current_level:
                if url in visited:
                    continue
                if not is_same_domain(url, config.root_url):
                    continue
                if is_excluded(url, config.exclude_patterns):
                    continue
                visited.add(url)
                tasks.append((url, depth, source))

            if not tasks:
                break

            # Descargar todas las páginas del nivel actual en paralelo.
            # ``return_exceptions=True`` evita que un fallo individual cancele el lote.
            results = await asyncio.gather(
                *[process_url(url, depth, source) for url, depth, source in tasks],
                return_exceptions=True,
            )

            next_queue: List[tuple[str, int, str]] = []
            for (url, depth, source), result in zip(tasks, results):
                if isinstance(result, Exception):
                    # Error no capturado dentro de process_url; se descarta.
                    continue

                html, status = result

                # Descartar páginas vacías o con errores HTTP (4xx, 5xx).
                if not html or status not in range(200, 400):
                    continue

                record = PageRecord(
                    url=url,
                    depth=depth,
                    source_url=source,
                    html_snapshot=html,
                    status_code=status,
                )
                records.append(record)

                # Solo extraer enlaces si aún hay profundidad disponible.
                if depth < config.max_depth:
                    for link in extract_links(html, url):
                        if link not in visited:
                            next_queue.append((link, depth + 1, url))

                # Cortesía hacia el servidor: pausa entre páginas procesadas.
                await asyncio.sleep(config.delay_seconds)

            queue.extend(next_queue)

        await context.close()
        await browser.close()

    return records

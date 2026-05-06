"""
src/core/crawler.py
===================
Fase 3.1 — Rastreo del sitio web (crawling) usando Playwright.

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
import logging
from typing import List

from playwright.async_api import async_playwright, Page, Browser

from src.models import Config, PageRecord, QueueItem
from src.utils import is_same_domain, is_under_path, is_excluded, extract_links

logger = logging.getLogger(__name__)


async def _fetch_page(page: Page, url: str, timeout_ms: int) -> tuple[str, int]:
    """Navega a URL y devuelve HTML renderizado y código de estado."""
    try:
        response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        status = response.status if response else 0
        html = await page.content()
        return html, status
    except Exception as exc:
        logger.debug("Error al cargar %s: %s", url, exc)
        return "", 0


async def crawl(config: Config) -> List[PageRecord]:
    """
    Rastrea el sitio definido en ``config`` usando BFS y devuelve
    todos los registros de páginas accesibles encontradas.

    Estrategia: BFS por niveles con hasta 3 tabs paralelas por nivel.
    Las respuestas 2xx/3xx con HTML no vacío se incluyen en el resultado.
    """
    visited: set[str] = set()
    records: List[PageRecord] = []
    queue: List[QueueItem] = [QueueItem(config.root_url, 0, "")]
    semaphore = asyncio.Semaphore(3)
    scope_check = is_under_path if config.confine_to_path else is_same_domain

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        async def process_url(item: QueueItem) -> tuple[str, int]:
            async with semaphore:
                page = await context.new_page()
                try:
                    html, status = await _fetch_page(page, item.url, config.page_timeout_ms)
                finally:
                    await page.close()
                return html, status

        while queue:
            current_level = [item for item in queue if item.depth <= config.max_depth]
            queue = [item for item in queue if item.depth > config.max_depth]

            if not current_level:
                break

            tasks: List[QueueItem] = []
            for item in current_level:
                if len(records) + len(tasks) >= config.max_crawled:
                    logger.info("Límite max_crawled=%d alcanzado, deteniendo crawl.", config.max_crawled)
                    break
                if item.url in visited:
                    continue
                if not scope_check(item.url, config.root_url):
                    logger.debug("Fuera de scope, ignorada: %s", item.url)
                    continue
                if is_excluded(item.url, config.exclude_patterns):
                    logger.debug("Excluida por patrón: %s", item.url)
                    continue
                visited.add(item.url)
                tasks.append(item)

            if not tasks:
                break

            logger.debug("Nivel %d: procesando %d URLs.", tasks[0].depth if tasks else 0, len(tasks))

            results = await asyncio.gather(
                *[process_url(item) for item in tasks],
                return_exceptions=True,
            )

            next_queue: List[QueueItem] = []
            for item, result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.warning("Excepción al procesar %s: %s", item.url, result)
                    continue

                html, status = result

                if not html or status not in range(200, 400):
                    logger.debug("Descartada %s (status=%d, html=%s)", item.url, status, bool(html))
                    continue

                logger.info("[%d] %s (status=%d)", item.depth, item.url, status)
                record = PageRecord(
                    url=item.url,
                    depth=item.depth,
                    source_url=item.source_url,
                    html_snapshot=html,
                    status_code=status,
                )
                records.append(record)

                if item.depth < config.max_depth:
                    for link in extract_links(html, item.url):
                        if link not in visited:
                            next_queue.append(QueueItem(link, item.depth + 1, item.url))

                await asyncio.sleep(config.delay_seconds)

            queue.extend(next_queue)

        await context.close()
        await browser.close()

    logger.info("Crawl completado: %d páginas válidas de %d visitadas.", len(records), len(visited))
    return records

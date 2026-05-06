"""
src/core/crawler.py
===================
Fase 3.1 — Rastreo del sitio web (crawling) usando Playwright.
"""

import asyncio
from typing import List

from playwright.async_api import async_playwright, Page, Browser

from src.models import Config, PageRecord
from src.utils import normalize_url, is_same_domain, is_excluded, extract_links


async def _fetch_page(page: Page, url: str, timeout_ms: int) -> tuple[str, int]:
    """Navega a URL y devuelve HTML renderizado y código de estado."""
    try:
        response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        status = response.status if response else 0
        html = await page.content()
        return html, status
    except Exception:
        return "", 0


async def crawl(config: Config) -> List[PageRecord]:
    """
    Rastrea el sitio definido en ``config`` usando BFS y devuelve
    todos los registros de páginas accesibles encontradas.

    Estrategia: BFS por niveles con hasta 3 tabs paralelas por nivel.
    Las respuestas 2xx/3xx con HTML no vacío se incluyen en el resultado.

    Parameters
    ----------
    config : Config
        Parámetros de ejecución.

    Returns
    -------
    list[PageRecord]
        Registros de páginas rastreadas, ordenados aproximadamente por profundidad.
    """
    visited: set[str] = set()
    records: List[PageRecord] = []
    queue: List[tuple[str, int, str]] = [(config.root_url, 0, "")]
    semaphore = asyncio.Semaphore(3)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        async def process_url(url: str, depth: int, source: str) -> tuple[str, int]:
            """Abre tab, descarga página, la cierra."""
            async with semaphore:
                page = await context.new_page()
                try:
                    html, status = await _fetch_page(page, url, config.page_timeout_ms)
                finally:
                    await page.close()
                return html, status

        while queue:
            current_level = [(u, d, s) for u, d, s in queue if d <= config.max_depth]
            queue = [(u, d, s) for u, d, s in queue if d > config.max_depth]

            if not current_level:
                break

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

            results = await asyncio.gather(
                *[process_url(url, depth, source) for url, depth, source in tasks],
                return_exceptions=True,
            )

            next_queue: List[tuple[str, int, str]] = []
            for (url, depth, source), result in zip(tasks, results):
                if isinstance(result, Exception):
                    continue

                html, status = result

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

                if depth < config.max_depth:
                    for link in extract_links(html, url):
                        if link not in visited:
                            next_queue.append((link, depth + 1, url))

                await asyncio.sleep(config.delay_seconds)

            queue.extend(next_queue)

        await context.close()
        await browser.close()

    return records

"""
src/core/crawler.py
===================
Fase 3.1 — Rastreo BFS del sitio usando Playwright Chromium headless.
"""

import asyncio
import logging
from typing import List

from playwright.async_api import async_playwright, BrowserContext, TimeoutError as PlaywrightTimeoutError

from src.models import Config, PageRecord, QueueItem, CrawlResult
from src.utils import is_same_domain, is_under_path, is_excluded, extract_links

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def crawl(config: Config) -> CrawlResult:
    """BFS crawl: devuelve CrawlResult con páginas válidas y estadísticas."""
    visited: set[str] = set()
    records: List[PageRecord] = []
    queue: List[QueueItem] = [QueueItem(config.root_url, 0, "")]
    semaphore = asyncio.Semaphore(config.max_concurrency)
    in_scope = is_under_path if config.confine_to_path else is_same_domain
    stats = {"timeouts": 0, "errors": 0, "http_errors": 0}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=_USER_AGENT)
        try:
            while queue and len(records) < config.max_crawled:
                current = [i for i in queue if i.depth <= config.max_depth]
                queue   = [i for i in queue if i.depth > config.max_depth]
                if not current:
                    break

                tasks: List[QueueItem] = []
                for item in current:
                    if len(records) + len(tasks) >= config.max_crawled:
                        break
                    if item.url in visited or not in_scope(item.url, config.root_url):
                        continue
                    if is_excluded(item.url, config.exclude_patterns):
                        continue
                    visited.add(item.url)
                    tasks.append(item)

                if not tasks:
                    continue

                results = await asyncio.gather(
                    *[_fetch_url(item, context, semaphore, config) for item in tasks],
                    return_exceptions=True,
                )

                for item, result in zip(tasks, results):
                    if isinstance(result, (asyncio.TimeoutError, PlaywrightTimeoutError)):
                        stats["timeouts"] += 1
                        continue
                    if isinstance(result, Exception):
                        stats["errors"] += 1
                        continue
                    html, status = result
                    if not html or status not in range(200, 400):
                        if status and status not in range(200, 400):
                            stats["http_errors"] += 1
                        continue
                    records.append(PageRecord(
                        url=item.url,
                        depth=item.depth,
                        source_url=item.source_url,
                        html_snapshot=html,
                        status_code=status,
                    ))
                    if item.depth < config.max_depth:
                        for link in extract_links(html, item.url):
                            if link not in visited:
                                queue.append(QueueItem(link, item.depth + 1, item.url))

        finally:
            await context.close()
            await browser.close()

    logger.info("Crawl completado: %d páginas válidas de %d visitadas.", len(records), len(visited))
    return CrawlResult(
        pages=records,
        visited=len(visited),
        timeouts=stats["timeouts"],
        errors=stats["errors"],
        http_errors=stats["http_errors"],
    )


async def _fetch_url(
    item: QueueItem,
    context: BrowserContext,
    semaphore: asyncio.Semaphore,
    config: Config,
) -> tuple[str, int]:
    """Abre un tab, navega a item.url y devuelve (html, status)."""
    async with semaphore:
        page = None
        try:
            page = await context.new_page()
            async with asyncio.timeout(config.page_timeout_ms / 1000):
                response = await page.goto(item.url, timeout=config.page_timeout_ms, wait_until="domcontentloaded")
                status = response.status if response else 0
                html = await page.content()
            if html and status in range(200, 400):
                logger.info("[%d] %s (status=%d)", item.depth, item.url, status)
            return html, status
        except (asyncio.TimeoutError, PlaywrightTimeoutError):
            logger.warning("Timeout (%dms) — saltada: %s", config.page_timeout_ms, item.url)
            raise
        except Exception as exc:
            if "TargetClosedError" in type(exc).__name__:
                return "", 0  # Browser cerrado durante shutdown, no es un error de crawl
            logger.warning("Error [%s] — saltada: %s — %s", type(exc).__name__, item.url, exc)
            raise
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await asyncio.sleep(config.delay_seconds)

"""
src/main.py
===========
Punto de entrada principal del crawler IRA.
"""

import argparse
import asyncio
import dataclasses
import logging
import time

from src.models import Config
from src.core import crawl, classify_pages, select_pages, validate_and_adjust
from src.io import export

_D = {f.name: f.default for f in dataclasses.fields(Config) if f.default is not dataclasses.MISSING}

logger = logging.getLogger(__name__)


def build_config(args: argparse.Namespace) -> Config:
    """Construye Config desde argumentos de CLI."""
    extra_exclude = args.exclude or []
    return Config(
        root_url=args.url,
        max_depth=args.depth,
        max_crawled=args.max_crawled,
        min_pages=args.min_pages,
        random_pct=args.random_pct,
        max_concurrency=args.max_concurrency,
        exclude_patterns=set(args.exclude) if args.exclude else set(),
    )


def parse_args() -> argparse.Namespace:
    """Parsea argumentos de CLI."""
    parser = argparse.ArgumentParser(
        description="Web crawler para generación de muestra IRA de accesibilidad.",
    )
    parser.add_argument("--url", required=True, help="URL raíz del sitio web")
    parser.add_argument("--depth", type=int, default=_D["max_depth"], metavar="N", help=f"Profundidad máxima (default: {_D['max_depth']})")
    parser.add_argument("--max-crawled", type=int, default=_D["max_crawled"], dest="max_crawled", metavar="N", help=f"Máximo de páginas a rastrear (default: {_D['max_crawled']})")
    parser.add_argument("--min-pages", type=int, default=_D["min_pages"], dest="min_pages", metavar="N", help=f"Páginas mínimas (default: {_D['min_pages']})")
    parser.add_argument("--random-pct", type=float, default=_D["random_pct"], dest="random_pct", metavar="PCT", help=f"Porcentaje aleatorio (default: {_D['random_pct']})")
    parser.add_argument("--concurrency", type=int, default=_D["max_concurrency"], dest="max_concurrency", metavar="N", help=f"Tabs paralelas del navegador (default: {_D['max_concurrency']})")
    parser.add_argument("--exclude", nargs="*", metavar="PATTERN", help="Patrones de exclusión")
    return parser.parse_args()


async def main_async(config: Config) -> None:
    """Pipeline principal de ejecución."""
    start = time.perf_counter()
    logger.info("Rastreando %s (max_depth=%d, max_crawled=%d)",
                config.root_url, config.max_depth, config.max_crawled)

    result = await crawl(config)
    logger.info("%d páginas rastreadas.", len(result.pages))

    logger.info("Clasificando páginas ...")
    all_pages = classify_pages(result.pages)

    logger.info("Seleccionando muestra ...")
    selected = select_pages(all_pages, config)

    logger.info("Validando muestra ...")
    selected, warnings = validate_and_adjust(selected, all_pages, config)

    logger.info("Muestra final: %d páginas.", len(selected))

    elapsed = time.perf_counter() - start
    export(selected, warnings, config, result, elapsed)

    m, s = divmod(int(elapsed), 60)
    logger.info("Tiempo total: %s | %d páginas rastreadas | muestra final: %d.",
                f"{m}m {s}s" if m else f"{elapsed:.1f}s", len(result.pages), len(selected))


def main() -> None:
    """Punto de entrada."""
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    config = build_config(args)
    asyncio.run(main_async(config))


if __name__ == "__main__":
    main()

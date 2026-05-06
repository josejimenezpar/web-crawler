"""
src/main.py
===========
Punto de entrada principal del crawler IRA.
"""

import argparse
import asyncio
import dataclasses
import logging

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
        confine_to_path=args.confine_to_path,
        random_pct=args.random_pct,
        exclude_patterns=extra_exclude,
        delay_seconds=args.delay,
        page_timeout_ms=args.timeout,
        output_dir=args.output_dir,
    )


def parse_args() -> argparse.Namespace:
    """Parsea argumentos de CLI."""
    parser = argparse.ArgumentParser(
        description="Web crawler para generación de muestra IRA de accesibilidad.",
    )
    parser.add_argument("--url", required=True, help="URL raíz del sitio web")
    parser.add_argument("--depth", type=int, default=_D["max_depth"], metavar="N", help=f"Profundidad máxima (default: {_D['max_depth']})")
    parser.add_argument("--max-crawled", type=int, default=_D["max_crawled"], dest="max_crawled", metavar="N", help=f"Máximo de páginas a rastrear (default: {_D['max_crawled']})")
    parser.add_argument("--no-confine", action="store_false", dest="confine_to_path", help="Rastrear todo el dominio, no solo el path raíz")
    parser.add_argument("--min-pages", type=int, default=_D["min_pages"], dest="min_pages", metavar="N", help=f"Páginas mínimas (default: {_D['min_pages']})")
    parser.add_argument("--random-pct", type=float, default=_D["random_pct"], dest="random_pct", metavar="PCT", help=f"Porcentaje aleatorio (default: {_D['random_pct']})")
    parser.add_argument("--exclude", nargs="*", metavar="PATTERN", help="Patrones de exclusión")
    parser.add_argument("--delay", type=float, default=_D["delay_seconds"], metavar="SEC", help=f"Delay entre peticiones (default: {_D['delay_seconds']})")
    parser.add_argument("--timeout", type=int, default=_D["page_timeout_ms"], metavar="MS", help=f"Timeout por página (default: {_D['page_timeout_ms']})")
    parser.add_argument("--output-dir", default=_D["output_dir"], dest="output_dir", metavar="DIR", help=f"Directorio de salida (default: {_D['output_dir']})")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"], dest="log_level", help="Nivel de log (default: INFO)")
    return parser.parse_args()


async def main_async(config: Config) -> None:
    """Pipeline principal de ejecución."""
    scope = "path" if config.confine_to_path else "dominio completo"
    logger.info("Rastreando %s (scope=%s, max_depth=%d, max_crawled=%d)",
                config.root_url, scope, config.max_depth, config.max_crawled)

    all_pages = await crawl(config)
    logger.info("%d páginas rastreadas.", len(all_pages))

    logger.info("Clasificando páginas ...")
    all_pages = classify_pages(all_pages)

    logger.info("Seleccionando muestra ...")
    selected = select_pages(all_pages, config)

    logger.info("Validando muestra ...")
    selected, warnings = validate_and_adjust(selected, all_pages, config)

    logger.info("Muestra final: %d páginas.", len(selected))
    export(selected, warnings, config, total_crawled=len(all_pages))


def main() -> None:
    """Punto de entrada."""
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    config = build_config(args)
    asyncio.run(main_async(config))


if __name__ == "__main__":
    main()

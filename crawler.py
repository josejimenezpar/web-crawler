import argparse
import asyncio

from modules.config import Config
from modules.crawl import crawl
from modules.classify import classify_pages
from modules.selector import select_pages
from modules.validator import validate_and_adjust
from modules.output import export


def build_config(args: argparse.Namespace) -> Config:
    extra_exclude = args.exclude or []
    return Config(
        root_url=args.url,
        max_depth=args.depth,
        min_pages=args.min_pages,
        random_pct=args.random_pct,
        exclude_patterns=extra_exclude,
        delay_seconds=args.delay,
        page_timeout_ms=args.timeout,
        output_dir=args.output_dir,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Web crawler para generación de muestra IRA de accesibilidad.",
    )
    parser.add_argument("--url", required=True, help="URL raíz del sitio web")
    parser.add_argument("--depth", type=int, default=3, metavar="N", help="Profundidad máxima (default: 3)")
    parser.add_argument("--min-pages", type=int, default=15, dest="min_pages", metavar="N", help="Páginas mínimas a seleccionar (default: 15)")
    parser.add_argument("--random-pct", type=float, default=10.0, dest="random_pct", metavar="PCT", help="Porcentaje mínimo de páginas aleatorias (default: 10.0)")
    parser.add_argument("--exclude", nargs="*", metavar="PATTERN", help="Patrones adicionales de URL a excluir")
    parser.add_argument("--delay", type=float, default=1.0, metavar="SEC", help="Delay entre peticiones en segundos (default: 1.0)")
    parser.add_argument("--timeout", type=int, default=15000, metavar="MS", help="Timeout por página en ms (default: 15000)")
    parser.add_argument("--output-dir", default="./output", dest="output_dir", metavar="DIR", help="Directorio de salida (default: ./output)")
    return parser.parse_args()


async def main_async(config: Config) -> None:
    print(f"[crawl]    Rastreando {config.root_url} (max_depth={config.max_depth}) ...")
    all_pages = await crawl(config)
    print(f"[crawl]    {len(all_pages)} páginas rastreadas.")

    print("[classify] Clasificando páginas ...")
    all_pages = classify_pages(all_pages)

    print("[select]   Seleccionando muestra ...")
    selected = select_pages(all_pages, config)

    print("[validate] Validando muestra ...")
    selected, warnings = validate_and_adjust(selected, all_pages, config)

    print(f"[validate] Muestra final: {len(selected)} páginas.")
    export(selected, warnings, config)


def main() -> None:
    args = parse_args()
    config = build_config(args)
    asyncio.run(main_async(config))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path

from .api import crawl_and_select, export_csv, export_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawler IRA para selección de muestra web")
    parser.add_argument("root_url", help="URL raíz del sitio")
    parser.add_argument("--max-depth", type=int, default=3, help="Profundidad máxima de rastreo")
    parser.add_argument("--min-pages", type=int, default=15, help="Mínimo de páginas a seleccionar")
    parser.add_argument("--random-percent", type=int, default=10, help="Porcentaje aleatorio mínimo")
    parser.add_argument(
        "--exclude-pattern",
        action="append",
        default=[],
        help="Regex de exclusión (puede repetirse)",
    )
    parser.add_argument("--timeout-seconds", type=int, default=10, help="Timeout HTTP por petición")
    parser.add_argument("--output-dir", default="outputs", help="Carpeta de salida")
    parser.add_argument("--output-prefix", default="muestra_ira", help="Prefijo de archivos de salida")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = crawl_and_select(
        root_url=args.root_url,
        max_depth=args.max_depth,
        min_pages=args.min_pages,
        random_percent=args.random_percent,
        exclusion_patterns=args.exclude_pattern,
        timeout_seconds=args.timeout_seconds,
    )

    output_dir = Path(args.output_dir)
    json_path = output_dir / f"{args.output_prefix}.json"
    csv_path = output_dir / f"{args.output_prefix}.csv"

    export_json(result, json_path)
    export_csv(result, csv_path)

    print(f"Total candidatas: {result.candidate_count}")
    print(f"Total seleccionadas: {len(result.selected_pages)}")
    print(f"Porcentaje aleatorio real: {result.random_percentage_real:.2f}%")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print("Logs:")
    for line in result.logs:
        print(f"- {line}")

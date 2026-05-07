"""
src/io/exporter.py
==================
Fase 4 — Exportación de resultados (JSON + Log).
"""

import json
import logging
import os
from datetime import datetime
from typing import List

from src.models import Config, PageRecord, CrawlResult

logger = logging.getLogger(__name__)


def export(
    pages: List[PageRecord],
    warnings: List[str],
    config: Config,
    result: CrawlResult,
    elapsed_seconds: float = 0.0,
) -> None:
    """Genera JSON de muestra y log de ejecución en output_dir."""
    os.makedirs(config.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    n_random = sum(1 for p in pages if p.selection_mode == "random")
    random_pct = round(n_random / len(pages) * 100, 1) if pages else 0.0

    _write_json(pages, config, result, timestamp, n_random, random_pct)
    _write_log(pages, warnings, config, result, timestamp, n_random, random_pct, elapsed_seconds)


def _write_json(
    pages: List[PageRecord],
    config: Config,
    result: CrawlResult,
    ts: str,
    n_random: int,
    random_pct: float,
) -> None:
    """Serializa muestra en JSON."""
    payload = {
        "metadata": {
            "root_url": config.root_url,
            "generated_at": datetime.now().isoformat(),
            "visited_pages": result.visited,
            "crawled_pages": len(result.pages),
            "selected_pages": len(pages),
            "random_count": n_random,
            "random_pct": random_pct,
        },
        "pages": [
            {
                "url": p.url,
                "functional_types": p.functional_types,
                "depth": p.depth,
                "selection_mode": p.selection_mode,
                "status_code": p.status_code,
            }
            for p in pages
        ],
    }

    path = os.path.join(config.output_dir, f"sample_{ts}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    logger.info("JSON guardado → %s", path)


def _write_log(
    pages: List[PageRecord],
    warnings: List[str],
    config: Config,
    result: CrawlResult,
    ts: str,
    n_random: int,
    random_pct: float,
    elapsed_seconds: float,
) -> None:
    """Genera log de ejecución en texto plano."""
    path = os.path.join(config.output_dir, f"crawler_{ts}.log")

    all_types: set[str] = set()
    for p in pages:
        all_types.update(p.functional_types)

    m, s = divmod(int(elapsed_seconds), 60)
    elapsed_str = f"{m}m {s}s" if m else f"{elapsed_seconds:.1f}s"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    skipped_summary = (
        f"{result.timeouts} timeouts · "
        f"{result.errors} errores de red · "
        f"{result.http_errors} HTTP errors"
    )

    lines = [
        "=== Crawler IRA — Execution Log ===",
        f"Generated at : {generated_at}",
        f"Elapsed time : {elapsed_str}",
        f"Root URL     : {config.root_url}",
        "",
        "--- Configuration ---",
        f"Max depth    : {config.max_depth}",
        f"Max crawled  : {config.max_crawled}",
        f"Min pages    : {config.min_pages}",
        "",
        "--- Crawl ---",
        f"Visited      : {result.visited}",
        f"Valid (2xx)  : {len(result.pages)}",
        f"Skipped      : {skipped_summary}",
        "",
        "--- Sample ---",
        f"Total        : {len(pages)}  (directed: {len(pages) - n_random} · random: {n_random} · {random_pct}%)",
        f"Types covered: {', '.join(sorted(all_types))}",
        "",
        "--- Selected pages ---",
    ]

    for i, p in enumerate(pages, 1):
        types_str = ", ".join(p.functional_types)
        lines.append(
            f"  {i:>3}. [{p.selection_mode:>8}] [{types_str:<30}] depth={p.depth}  {p.url}"
        )

    lines += ["", "--- Warnings ---"]
    if warnings:
        for w in warnings:
            lines.append(f"  ! {w}")
            logger.warning(w)
    else:
        lines.append("  (none)")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Log guardado → %s", path)

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

from src.models import Config, PageRecord

logger = logging.getLogger(__name__)


def export(pages: List[PageRecord], warnings: List[str], config: Config, total_crawled: int = 0) -> None:
    """
    Genera JSON de muestra y log de ejecución en output_dir.
    Ambos archivos comparten el mismo timestamp.
    """
    os.makedirs(config.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    n_random = sum(1 for p in pages if p.selection_mode == "random")
    random_pct_real = round(n_random / len(pages) * 100, 1) if pages else 0.0

    _write_json(pages, config, timestamp, n_random, random_pct_real, total_crawled)
    _write_log(pages, warnings, config, timestamp, n_random, random_pct_real, total_crawled)


def _write_json(
    pages: List[PageRecord],
    config: Config,
    ts: str,
    n_random: int,
    random_pct_real: float,
    total_crawled: int = 0,
) -> None:
    """Serializa muestra en JSON."""
    payload = {
        "metadata": {
            "root_url": config.root_url,
            "generated_at": datetime.now().isoformat(),
            "crawled_pages": total_crawled,
            "selected_pages": len(pages),
            "random_count": n_random,
            "random_pct": random_pct_real,
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
    ts: str,
    n_random: int,
    random_pct_real: float,
    total_crawled: int = 0,
) -> None:
    """Genera log de ejecución en texto plano."""
    path = os.path.join(config.output_dir, f"crawler_{ts}.log")

    all_types: set[str] = set()
    for p in pages:
        all_types.update(p.functional_types)

    lines = [
        "=== Crawler IRA — Execution Log ===",
        f"Generated at : {datetime.now().isoformat()}",
        f"Root URL     : {config.root_url}",
        f"Max depth    : {config.max_depth}",
        f"Min pages    : {config.min_pages}",
        "",
        "--- Results ---",
        f"Total pages crawled  : {total_crawled}",
        f"Total pages selected : {len(pages)}",
        f"Directed             : {len(pages) - n_random}",
        f"Random               : {n_random} ({random_pct_real}%)",
        f"Functional types     : {', '.join(sorted(all_types))}",
        "",
        "--- Selected pages ---",
    ]

    for i, p in enumerate(pages, 1):
        lines.append(
            f"  {i:>3}. [{p.selection_mode:>8}] [{', '.join(p.functional_types):<30}] "
            f"depth={p.depth}  {p.url}"
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

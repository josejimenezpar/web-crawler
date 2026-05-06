"""
src/io/exporter.py
==================
Fase 4 — Exportación de resultados (JSON + Log).
"""

import json
import os
from datetime import datetime
from typing import List

from src.models import Config, PageRecord


def export(pages: List[PageRecord], warnings: List[str], config: Config) -> None:
    """
    Genera JSON de muestra y log de ejecución en output_dir.
    Ambos archivos comparten el mismo timestamp.
    """
    os.makedirs(config.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _write_json(pages, config, timestamp)
    _write_log(pages, warnings, config, timestamp)


def _write_json(pages: List[PageRecord], config: Config, ts: str) -> None:
    """Serializa muestra en JSON."""
    n_random = sum(1 for p in pages if p.selection_mode == "random")
    random_pct_real = round(n_random / len(pages) * 100, 1) if pages else 0.0

    payload = {
        "metadata": {
            "root_url": config.root_url,
            "generated_at": datetime.now().isoformat(),
            "total_pages": len(pages),
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
    print(f"[output] JSON saved → {path}")


def _write_log(
    pages: List[PageRecord],
    warnings: List[str],
    config: Config,
    ts: str,
) -> None:
    """Genera log de ejecución en texto plano."""
    path = os.path.join(config.output_dir, f"crawler_{ts}.log")

    n_random = sum(1 for p in pages if p.selection_mode == "random")
    random_pct_real = round(n_random / len(pages) * 100, 1) if pages else 0.0

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

    if warnings:
        lines += ["", "--- Warnings ---"]
        for w in warnings:
            lines.append(f"  ! {w}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[output] Log  saved → {path}")

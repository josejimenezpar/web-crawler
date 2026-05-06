"""
modules/output.py
=================
Fase 4 — Generación de salidas del crawler.

Responsabilidades
-----------------
Serializa la muestra final validada en dos archivos guardados en
``config.output_dir``:

1. **JSON de muestra** (``sample_YYYYMMDD_HHMMSS.json``)
   Contiene los metadatos de la ejecución y la lista completa de páginas
   seleccionadas con sus tipos funcionales, nivel de profundidad y modo de
   selección. Este archivo está pensado para ser consumido por herramientas
   de evaluación de accesibilidad o para importarse en el IRA.

2. **Log de ejecución** (``crawler_YYYYMMDD_HHMMSS.log``)
   Resumen legible por humanos con las estadísticas finales, la lista
   detallada de páginas y todas las advertencias emitidas por el validador.
   Sirve como registro de auditoría para justificar la muestra ante revisores.

Ambos archivos llevan el mismo timestamp en el nombre para facilitar
la correlación entre ejecuciones.
"""

import json
import os
from datetime import datetime
from typing import List

from modules.config import Config
from modules.crawl import PageRecord


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def export(pages: List[PageRecord], warnings: List[str], config: Config) -> None:
    """
    Punto de entrada de la fase de salida. Crea el directorio si no existe
    y genera los dos archivos de salida con el mismo timestamp.

    Parameters
    ----------
    pages : list[PageRecord]
        Muestra final validada producida por ``validator.validate_and_adjust()``.
    warnings : list[str]
        Advertencias acumuladas durante la validación, escritas en el log.
    config : Config
        Parámetros de ejecución (``output_dir``, ``root_url``, etc.).
    """
    os.makedirs(config.output_dir, exist_ok=True)

    # Un único timestamp compartido por ambos archivos facilita correlacionarlos.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _write_json(pages, config, timestamp)
    _write_log(pages, warnings, config, timestamp)


# ---------------------------------------------------------------------------
# Generación del JSON
# ---------------------------------------------------------------------------

def _write_json(pages: List[PageRecord], config: Config, ts: str) -> None:
    """
    Serializa la muestra en formato JSON.

    Estructura del archivo
    ----------------------
    .. code-block:: json

        {
          "metadata": {
            "root_url": "https://...",
            "generated_at": "2026-05-05T12:00:00",
            "total_pages": 15,
            "random_count": 2,
            "random_pct": 13.3
          },
          "pages": [
            {
              "url": "https://...",
              "functional_types": ["form", "navigation"],
              "depth": 2,
              "selection_mode": "directed",
              "status_code": 200
            }
          ]
        }

    El campo ``random_pct`` en ``metadata`` refleja el porcentaje real
    obtenido, que puede diferir del configurado si el validador tuvo que
    hacer ajustes.

    Parameters
    ----------
    pages : list[PageRecord]
        Muestra final.
    config : Config
        Parámetros de ejecución.
    ts : str
        Timestamp formateado (``YYYYMMDD_HHMMSS``) para el nombre de archivo.
    """
    n_random = sum(1 for p in pages if p.selection_mode == "random")
    random_pct_real = round(n_random / len(pages) * 100, 1) if pages else 0.0

    payload = {
        "metadata": {
            "root_url": config.root_url,
            "generated_at": datetime.now().isoformat(),
            "total_pages": len(pages),
            "random_count": n_random,
            # Porcentaje real conseguido (puede diferir del configurado)
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
        # ensure_ascii=False para preservar caracteres especiales del español
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[output] JSON saved → {path}")


# ---------------------------------------------------------------------------
# Generación del log
# ---------------------------------------------------------------------------

def _write_log(
    pages: List[PageRecord],
    warnings: List[str],
    config: Config,
    ts: str,
) -> None:
    """
    Genera el log de ejecución en texto plano.

    El log incluye:
    - Cabecera con parámetros de la ejecución.
    - Resumen estadístico (total, dirigidas, aleatorias, tipos cubiertos).
    - Tabla de páginas seleccionadas con modo, tipos funcionales, profundidad y URL.
    - Sección de advertencias si el validador realizó ajustes automáticos.

    El formato tabular está pensado para ser legible a simple vista en un
    editor de texto o en la salida de un pipeline CI.

    Parameters
    ----------
    pages : list[PageRecord]
        Muestra final.
    warnings : list[str]
        Advertencias del validador.
    config : Config
        Parámetros de ejecución.
    ts : str
        Timestamp para el nombre de archivo.
    """
    path = os.path.join(config.output_dir, f"crawler_{ts}.log")

    n_random = sum(1 for p in pages if p.selection_mode == "random")
    random_pct_real = round(n_random / len(pages) * 100, 1) if pages else 0.0

    # Recopilar todos los tipos funcionales presentes en la muestra final
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
        # Formato columnar: índice | modo | tipos | profundidad | URL
        lines.append(
            f"  {i:>3}. [{p.selection_mode:>8}] [{', '.join(p.functional_types):<30}] "
            f"depth={p.depth}  {p.url}"
        )

    # La sección de advertencias solo aparece si hubo ajustes automáticos,
    # para mantener el log limpio en ejecuciones sin incidencias.
    if warnings:
        lines += ["", "--- Warnings ---"]
        for w in warnings:
            lines.append(f"  ! {w}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[output] Log  saved → {path}")

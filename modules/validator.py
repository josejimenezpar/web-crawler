"""
modules/validator.py
====================
Fase 3.5 — Validación y auto-ajuste de la muestra.

Responsabilidades
-----------------
Recibe la muestra producida por ``selector.py`` y comprueba que cumple todos
los requisitos IRA. Cuando detecta incumplimientos intenta corregirlos
automáticamente tomando páginas adicionales del pool de páginas rastreadas no
seleccionadas. Cada ajuste automático se registra como advertencia en el log
para que la muestra sea auditable y trazable.

Comprobaciones en orden
-----------------------
1. **Deduplicación**: elimina URLs duplicadas que pudieran aparecer si el
   selector las eligió en más de una pasada.
2. **Cobertura funcional**: verifica que todos los tipos obligatorios
   (``_REQUIRED_TYPES``) estén representados. Añade páginas si faltan.
3. **Mínimo de páginas**: garantiza que la muestra tiene al menos
   ``config.min_pages`` entradas.
4. **Porcentaje aleatorio**: verifica que la proporción de páginas aleatorias
   alcanza el mínimo requerido. Añade páginas aleatorias si es necesario.
"""

import math
import random
from typing import List, Tuple

from modules.config import Config
from modules.crawl import PageRecord


# Tipos funcionales que DEBEN estar presentes en la muestra final.
# Si alguno falta, el validador intenta añadir una página que lo cubra.
_REQUIRED_TYPES = {"home", "form", "navigation"}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def validate_and_adjust(
    selected: List[PageRecord],
    all_pages: List[PageRecord],
    config: Config,
) -> Tuple[List[PageRecord], List[str]]:
    """
    Valida la muestra y aplica correcciones automáticas si es necesario.

    Trabaja con dos conjuntos:
    - ``selected``: muestra actual producida por el selector.
    - ``pool``: páginas rastreadas que no están en la muestra y pueden usarse
      para completarla si hay incumplimientos.

    Todas las modificaciones quedan registradas en la lista de advertencias
    que se escribe en el log de ejecución, garantizando trazabilidad ante
    una auditoría IRA.

    Parameters
    ----------
    selected : list[PageRecord]
        Muestra inicial producida por ``selector.select_pages()``.
    all_pages : list[PageRecord]
        Todos los registros rastreados (fuente de páginas de reserva).
    config : Config
        Parámetros de ejecución con los umbrales de validación.

    Returns
    -------
    tuple[list[PageRecord], list[str]]
        - Lista final de páginas (ajustada si fue necesario).
        - Lista de mensajes de advertencia para el log.
    """
    warnings: List[str] = []

    # Construir el pool de reserva: páginas rastreadas con éxito que no
    # están ya en la muestra seleccionada.
    used = {p.url for p in selected}
    pool = [
        p for p in all_pages
        if p.url not in used and p.status_code in range(200, 300)
    ]

    # -- Comprobación 1: deduplicar la muestra --
    seen: set[str] = set()
    deduped: List[PageRecord] = []
    for p in selected:
        if p.url not in seen:
            seen.add(p.url)
            deduped.append(p)
        else:
            # Registrar duplicado para que el auditor lo conozca.
            warnings.append(f"Duplicate removed: {p.url}")
    selected = deduped

    # -- Comprobación 2: cobertura de tipos funcionales obligatorios --
    # Se calcula el conjunto de tipos presentes en la muestra actual.
    covered = {t for p in selected for t in p.functional_types}
    missing = _REQUIRED_TYPES - covered

    for type_ in missing:
        # Buscar en el pool una página que cubra el tipo ausente.
        candidates = [p for p in pool if type_ in p.functional_types]
        if candidates:
            pick = candidates[0]
            pick.selection_mode = "directed"
            selected.append(pick)
            pool.remove(pick)
            used.add(pick.url)
            warnings.append(
                f"Auto-added '{type_}' page to meet functional coverage: {pick.url}"
            )
        else:
            # El tipo no existe en ninguna página rastreada: advertencia crítica.
            warnings.append(
                f"WARNING: No '{type_}' page found in crawled pool. "
                f"The sample may not meet IRA requirements."
            )

    # -- Comprobación 3: número mínimo de páginas --
    while len(selected) < config.min_pages and pool:
        pick = pool.pop(0)
        pick.selection_mode = "directed"
        selected.append(pick)
        used.add(pick.url)
        warnings.append(
            f"Auto-added page to meet min_pages ({config.min_pages}): {pick.url}"
        )

    if len(selected) < config.min_pages:
        # El sitio tiene menos páginas accesibles que el mínimo requerido.
        warnings.append(
            f"WARNING: Only {len(selected)} pages available; "
            f"could not reach minimum of {config.min_pages}."
        )

    # -- Comprobación 4: porcentaje mínimo de páginas aleatorias --
    n_random = sum(1 for p in selected if p.selection_mode == "random")
    # El cálculo usa ceiling para cumplir "al menos el X %" aunque no sea
    # divisible exactamente (p. ej. 10 % de 15 = 1.5 → 2 páginas aleatorias).
    n_required_random = math.ceil(len(selected) * config.random_pct / 100)

    if n_random < n_required_random:
        deficit = n_required_random - n_random
        # Tomar aleatoriamente del pool restante sin repetir.
        picks = random.sample(pool, min(deficit, len(pool)))
        for p in picks:
            p.selection_mode = "random"
            selected.append(p)
            pool.remove(p)

        if picks:
            warnings.append(
                f"Auto-added {len(picks)} random page(s) to meet "
                f"random_pct ({config.random_pct}%)."
            )

        # Si aun así no se alcanza el porcentaje, registrar advertencia.
        if len(picks) < deficit:
            achieved = n_random + len(picks)
            warnings.append(
                f"WARNING: Could not reach required random percentage. "
                f"Got {achieved}/{len(selected)} random pages "
                f"({round(achieved / len(selected) * 100, 1)}%)."
            )

    return selected, warnings

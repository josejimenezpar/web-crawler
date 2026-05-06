"""
src/core/validator.py
=====================
Fase 3.5 — Validación y auto-ajuste de la muestra según IRA.
"""

import math
import random
from typing import List, Tuple

from src.models import Config, PageRecord, MANDATORY_TYPES


def validate_and_adjust(
    selected: List[PageRecord],
    all_pages: List[PageRecord],
    config: Config,
) -> Tuple[List[PageRecord], List[str]]:
    """
    Valida muestra y aplica correcciones automáticas.

    Comprobaciones:
    1. Deduplicación
    2. Cobertura funcional obligatoria
    3. Número mínimo de páginas
    4. Porcentaje mínimo de selección aleatoria
    """
    warnings: List[str] = []

    used = {p.url for p in selected}
    pool = [p for p in all_pages if p.url not in used and p.is_success]

    # 1. Deduplicación
    seen: set[str] = set()
    deduped: List[PageRecord] = []
    for p in selected:
        if p.url not in seen:
            seen.add(p.url)
            deduped.append(p)
        else:
            warnings.append(f"Duplicate removed: {p.url}")
    selected = deduped

    # 2. Cobertura funcional
    covered = {t for p in selected for t in p.functional_types}
    missing = MANDATORY_TYPES - covered

    for type_ in missing:
        candidates = [p for p in pool if type_ in p.functional_types]
        if candidates:
            pick = candidates[0]
            pick.selection_mode = "directed"
            selected.append(pick)
            pool.remove(pick)
            warnings.append(f"Auto-added '{type_}' page: {pick.url}")
        else:
            warnings.append(f"WARNING: No '{type_}' page found in crawled pool.")

    # 3. Mínimo de páginas
    while len(selected) < config.min_pages and pool:
        pick = pool.pop(0)
        pick.selection_mode = "directed"
        selected.append(pick)
        warnings.append(f"Auto-added page to meet min_pages ({config.min_pages}): {pick.url}")

    if len(selected) < config.min_pages:
        warnings.append(f"WARNING: Only {len(selected)} pages available; needed {config.min_pages}.")

    # 4. Porcentaje aleatorio
    n_random = sum(1 for p in selected if p.selection_mode == "random")
    n_required_random = math.ceil(len(selected) * config.random_pct / 100)

    if n_random < n_required_random:
        deficit = n_required_random - n_random
        picks = random.sample(pool, min(deficit, len(pool)))
        for p in picks:
            p.selection_mode = "random"
            selected.append(p)
            pool.remove(p)

        if picks:
            warnings.append(f"Auto-added {len(picks)} random page(s) to meet random_pct ({config.random_pct}%).")

        if len(picks) < deficit:
            achieved = n_random + len(picks)
            pct = round(achieved / len(selected) * 100, 1) if selected else 0
            warnings.append(f"WARNING: Could not reach required random percentage. Got {achieved}/{len(selected)} ({pct}%).")

    return selected, warnings

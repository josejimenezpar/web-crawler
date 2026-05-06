"""
src/core/selector.py
====================
Fase 3.3 + 3.4 — Selección de la muestra de páginas según criterios IRA.
"""

import math
import random
from typing import List, Optional

from src.models import Config, PageRecord, MANDATORY_TYPES


def select_pages(pages: List[PageRecord], config: Config) -> List[PageRecord]:
    """
    Construye muestra respetando proporciones IRA:
    - Tipos funcionales obligatorios (home, form, navigation)
    - ≥2 niveles de profundidad
    - Relleno con páginas complejas (más tipos)
    - Selección aleatoria del pool restante
    """
    n_total = config.min_pages
    n_random = math.ceil(n_total * config.random_pct / 100)
    n_directed = n_total - n_random

    valid = [p for p in pages if p.is_success]
    used: set[str] = set()
    directed: List[PageRecord] = []

    # Paso 1: Tipos obligatorios
    for type_ in MANDATORY_TYPES:
        pick = _pick_one(valid, type_, used)
        if pick:
            pick.selection_mode = "directed"
            directed.append(pick)
            used.add(pick.url)

    # Paso 2: Diversidad de profundidad
    depths_covered = {p.depth for p in directed}
    if len(depths_covered) < 2:
        for p in sorted(valid, key=lambda x: x.depth, reverse=True):
            if p.url not in used and p.depth not in depths_covered:
                p.selection_mode = "directed"
                directed.append(p)
                used.add(p.url)
                depths_covered.add(p.depth)
                break

    # Paso 3: Relleno con páginas complejas
    remaining = [p for p in valid if p.url not in used]
    remaining_sorted = sorted(remaining, key=lambda p: len(p.functional_types), reverse=True)
    for p in remaining_sorted:
        if len(directed) >= n_directed:
            break
        p.selection_mode = "directed"
        directed.append(p)
        used.add(p.url)

    # Paso 4: Selección aleatoria
    random_pool = [p for p in valid if p.url not in used]
    n_pick = min(n_random, len(random_pool))
    random_sample = random.sample(random_pool, n_pick) if n_pick > 0 else []
    for p in random_sample:
        p.selection_mode = "random"
        used.add(p.url)

    return directed + random_sample


def _pick_one(pool: List[PageRecord], type_: str, used: set) -> Optional[PageRecord]:
    """Devuelve primera página que tenga type_ y no esté en used."""
    candidates = [p for p in pool if type_ in p.functional_types and p.url not in used]
    return candidates[0] if candidates else None

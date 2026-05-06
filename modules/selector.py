"""
modules/selector.py
===================
Fase 3.3 + 3.4 — Selección de la muestra de páginas.

Responsabilidades
-----------------
A partir del conjunto total de páginas rastreadas y clasificadas, construye
la muestra final de ``config.min_pages`` páginas siguiendo el reparto
establecido por el IRA:

- **Selección dirigida** (≥ 90 % del total, p. ej. 13 de 15):
  Garantiza representatividad funcional. Se eligen primero los tipos
  obligatorios y luego se rellena con páginas de mayor complejidad
  estructural.

- **Selección aleatoria** (≥ 10 % del total, p. ej. 2 de 15):
  Reduce el sesgo humano. Se toman aleatoriamente del pool de páginas
  no usadas en la selección dirigida.

Criterios obligatorios de selección dirigida (IRA)
---------------------------------------------------
1. Al menos 1 página de tipo ``home``.
2. Al menos 1 página de tipo ``form`` (formulario sustantivo).
3. Al menos 1 página de tipo ``navigation`` (listado navegable).
4. Representación en ≥ 2 niveles de profundidad distintos.
5. Relleno con páginas de mayor número de tipos funcionales (más complejas).
"""

import math
import random
from typing import List, Optional

from modules.config import Config
from modules.crawl import PageRecord


# Tipos que DEBEN estar representados en la selección dirigida.
# Una muestra sin alguno de estos tipos no sería válida para el IRA.
_MANDATORY_TYPES = ["home", "form", "navigation"]


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def select_pages(pages: List[PageRecord], config: Config) -> List[PageRecord]:
    """
    Construye la muestra de páginas respetando las proporciones IRA.

    El proceso sigue cuatro pasos ordenados por prioridad:

    1. **Garantías obligatorias**: se elige exactamente una página por cada
       tipo de ``_MANDATORY_TYPES``. Si un tipo no está disponible en el pool
       se omite aquí y el validador lo detectará después.

    2. **Diversidad de profundidad**: si todas las páginas seleccionadas hasta
       ahora comparten el mismo nivel, se busca activamente una página en un
       nivel distinto para cumplir el criterio de representación estructural.

    3. **Relleno dirigido**: se completa hasta ``n_directed`` con las páginas
       más complejas del pool (más tipos funcionales = más riqueza estructural
       para la auditoría), priorizando diversidad sobre uniformidad.

    4. **Selección aleatoria**: del pool restante (no usado en dirigida) se
       toman ``n_random`` páginas con ``random.sample`` para garantizar
       imparcialidad y cumplir el porcentaje IRA.

    Parameters
    ----------
    pages : list[PageRecord]
        Todos los registros rastreados y clasificados.
    config : Config
        Parámetros de ejecución (``min_pages``, ``random_pct``).

    Returns
    -------
    list[PageRecord]
        Muestra combinada: páginas dirigidas seguidas de páginas aleatorias,
        con ``selection_mode`` asignado en cada una.
    """
    n_total = config.min_pages
    # Calcular cuántas páginas aleatorias se necesitan (ceiling para cumplir
    # el requisito aunque el porcentaje no sea divisible exactamente).
    n_random = math.ceil(n_total * config.random_pct / 100)
    n_directed = n_total - n_random

    # Trabajar solo con páginas con respuesta HTTP exitosa (2xx).
    valid = [p for p in pages if p.status_code in range(200, 300)]
    used: set[str] = set()          # URLs ya incluidas en la muestra
    directed: List[PageRecord] = [] # Páginas de selección dirigida

    # -- Paso 1: garantizar un representante de cada tipo obligatorio --
    for type_ in _MANDATORY_TYPES:
        pick = _pick_one(valid, type_, used)
        if pick:
            pick.selection_mode = "directed"
            directed.append(pick)
            used.add(pick.url)

    # -- Paso 2: garantizar al menos 2 niveles de profundidad distintos --
    depths_covered = {p.depth for p in directed}
    if len(depths_covered) < 2:
        # Buscar la página más profunda no usada que aporte un nivel nuevo.
        for p in sorted(valid, key=lambda x: x.depth, reverse=True):
            if p.url not in used and p.depth not in depths_covered:
                p.selection_mode = "directed"
                directed.append(p)
                used.add(p.url)
                depths_covered.add(p.depth)
                break  # Un solo nivel nuevo es suficiente

    # -- Paso 3: rellenar hasta n_directed con páginas más complejas --
    # "Más compleja" = más tipos funcionales detectados. Una página con
    # [form, navigation, dynamic] ofrece más superficie de evaluación que
    # una con solo [informational].
    remaining = [p for p in valid if p.url not in used]
    remaining_sorted = sorted(remaining, key=lambda p: len(p.functional_types), reverse=True)
    for p in remaining_sorted:
        if len(directed) >= n_directed:
            break
        p.selection_mode = "directed"
        directed.append(p)
        used.add(p.url)

    # -- Paso 4: selección aleatoria del pool no usado --
    random_pool = [p for p in valid if p.url not in used]
    n_pick = min(n_random, len(random_pool))  # No pedir más de lo disponible
    random_sample = random.sample(random_pool, n_pick)
    for p in random_sample:
        p.selection_mode = "random"
        used.add(p.url)

    return directed + random_sample


# ---------------------------------------------------------------------------
# Utilidad interna
# ---------------------------------------------------------------------------

def _pick_one(
    pool: List[PageRecord],
    type_: str,
    used: set,
) -> Optional[PageRecord]:
    """
    Devuelve la primera página del pool que tenga ``type_`` entre sus tipos
    funcionales y no haya sido seleccionada aún.

    Devuelve ``None`` si no hay candidatos, lo que indica al selector que
    ese tipo no existe en el sitio rastreado (se registrará como advertencia
    en el validador).

    Parameters
    ----------
    pool : list[PageRecord]
        Conjunto de páginas candidatas.
    type_ : str
        Tipo funcional requerido (p. ej. ``"form"``).
    used : set
        Conjunto de URLs ya elegidas; se usa para evitar duplicados.

    Returns
    -------
    PageRecord or None
    """
    candidates = [p for p in pool if type_ in p.functional_types and p.url not in used]
    return candidates[0] if candidates else None

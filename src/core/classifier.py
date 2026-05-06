"""
src/core/classifier.py
======================
Fase 3.2 — Clasificación funcional de páginas.

Responsabilidades
-----------------
Para cada ``PageRecord`` rastreado, analiza el DOM renderizado (``html_snapshot``)
y asigna uno o varios tipos funcionales a ``functional_types``.

La clasificación es NO excluyente: una misma página puede pertenecer a
varios tipos simultáneamente (p. ej., una página de trámite que tiene
formulario Y es un listado de pasos será ``form`` + ``navigation``).

Tipos funcionales disponibles
------------------------------
- ``home``          — Página raíz del sitio.
- ``form``          — Contiene un formulario sustantivo (≥2 campos + submit).
- ``navigation``    — Su contenido principal es un listado navegable
                    (lista de enlaces, tarjetas, tabla de filas con links).
- ``dynamic``       — Usa un framework JS moderno (React, Angular, Vue, etc.)
                    o contiene elementos multimedia interactivos.
- ``informational`` — Fallback para páginas de contenido textual que no
                    encajan en ninguna categoría anterior.

Criterio de diseño
------------------
Se basa exclusivamente en la estructura del DOM renderizado,
no en patrones de URL. Esto es más preferente frente a sitios con 
rutas no semánticas y portales institucionales con URLs generadas por CMS.
"""

import copy
import re
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from src.models import PageRecord


# ---------------------------------------------------------------------------
# Constantes de clasificación
# ---------------------------------------------------------------------------

# Regex para identificar la página raíz por su path.
# Cubre los patrones habituales de webs institucionales españolas.
_HOME_PATH = re.compile(r"^/?$|^/index(\.\w+)?$|^/inicio$|^/home$", re.IGNORECASE)

# Tipos de <input> que NO cuentan como campos interactivos para la detección
# de formularios sustantivos. Excluimos también "search" para que una barra
# de búsqueda simple (1 campo) no clasifique la página como "form".
_EXCLUDED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image", "search"}

# Cadenas que identifican frameworks JS modernos en el HTML raw.
# Se buscan en minúsculas sobre el HTML completo en lugar de en el DOM
# parseado porque algunos atributos (p. ej. data-reactroot) y variables
# globales de JS (p. ej. __NEXT_DATA__) pueden aparecer en <script> inline
# o en atributos que BeautifulSoup normaliza de formas distintas.
_FRAMEWORK_SIGNATURES = [
    # React (CRA) y Next.js
    "data-reactroot", "__next_data__", "_next/static",
    # Angular (2+): ng-version en el elemento raíz; ng-app para AngularJS
    "ng-version", "ng-app", "ng-controller",
    # Vue.js y Nuxt.js
    "data-v-", "__vue_app__", "__nuxt__",
    # Patrones genéricos de hidratación de estado en SPAs
    "window.__initial_state__", "window.__state__",
]
_NAV_MIN_ITEMS = 3


def classify_pages(pages: List[PageRecord]) -> List[PageRecord]:
    """Clasifica funcionalidad de todas las páginas in-place."""
    for record in pages:
        record.functional_types = _classify(record)
    return pages


def _classify(record: PageRecord) -> List[str]:
    """Determina tipos funcionales de una página."""
    soup = BeautifulSoup(record.html_snapshot, "lxml")
    types: List[str] = []

    if _is_home(record):
        types.append("home")
    if _has_substantive_form(soup):
        types.append("form")
    if _is_navigation(soup):
        types.append("navigation")
    if _is_dynamic(soup, record.html_snapshot):
        types.append("dynamic")

    if not types or types == ["home"]:
        types.append("informational")

    return types


def _is_home(record: PageRecord) -> bool:
    """Detecta página raíz."""
    path = urlparse(record.url).path
    return record.depth == 0 or bool(_HOME_PATH.match(path))


def _has_substantive_form(soup: BeautifulSoup) -> bool:
    """Detecta formularios sustantivos (≥2 campos + submit)."""
    for form in soup.find_all("form"):
        interactive_fields = [
            el for el in form.find_all(["input", "select", "textarea"])
            if not (el.name == "input" and el.get("type", "text").lower() in _EXCLUDED_INPUT_TYPES)
        ]
        has_submit = bool(
            form.find("input", attrs={"type": "submit"})
            or form.find("button", attrs={"type": "submit"})
            or form.find("button", attrs=lambda a: a is None or "type" not in a)
        )
        if len(interactive_fields) >= 2 and has_submit:
            return True
    return False


def _is_navigation(soup: BeautifulSoup) -> bool:
    """Detecta contenido de navegación (listas/bloques/tablas enlazadas)."""
    scope = _get_content_scope(soup)
    if scope is None:
        return False

    for list_tag in scope.find_all(["ul", "ol"]):
        linked_items = [li for li in list_tag.find_all("li", recursive=False) if li.find("a")]
        if len(linked_items) >= _NAV_MIN_ITEMS:
            return True

    blocks_with_links = [el for el in scope.find_all(["article", "section"]) if el.find("a")]
    if len(blocks_with_links) >= _NAV_MIN_ITEMS:
        return True

    for table in scope.find_all("table"):
        tbody = table.find("tbody") or table
        linked_rows = [tr for tr in tbody.find_all("tr") if tr.find("a")]
        if len(linked_rows) >= _NAV_MIN_ITEMS:
            return True

    return False


def _is_dynamic(soup: BeautifulSoup, raw_html: str) -> bool:
    """Detecta frameworks JS o elementos multimedia."""
    raw_lower = raw_html.lower()
    if any(sig in raw_lower for sig in _FRAMEWORK_SIGNATURES):
        return True
    if soup.find(["video", "canvas"]):
        return True
    return False


def _get_content_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """Extrae el contenido principal, excluyendo header/footer."""
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main:
        return main

    body = soup.find("body")
    if not body:
        return None

    body_clone = copy.copy(body)
    for tag in body_clone.find_all(["header", "footer"]):
        tag.decompose()

    return body_clone

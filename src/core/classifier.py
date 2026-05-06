"""
src/core/classifier.py
======================
Fase 3.2 — Clasificación funcional de páginas.
"""

import copy
import re
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from src.models import PageRecord


_HOME_PATH = re.compile(r"^/?$|^/index(\.\w+)?$|^/inicio$|^/home$", re.IGNORECASE)
_EXCLUDED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image", "search"}
_FRAMEWORK_SIGNATURES = [
    "data-reactroot", "__next_data__", "_next/static",
    "ng-version", "ng-app", "ng-controller",
    "data-v-", "__vue_app__", "__nuxt__",
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

"""
src/utils/url.py
================
Utilidades para normalización y filtrado de URLs.
"""

from typing import List, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    """
    Elimina el fragmento (#anchor) y el query string (?a=1&b=2) de una URL.

    Los fragmentos no representan páginas distintas en el servidor.
    Los query strings generan duplicados funcionales: la estructura HTML
    evaluable en accesibilidad es la misma independientemente de los parámetros.
    """
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="", query="")
    return urlunparse(normalized)


def is_same_domain(url: str, root_url: str) -> bool:
    return urlparse(url).netloc == urlparse(root_url).netloc


def is_under_path(url: str, root_url: str) -> bool:
    """Comprueba que url está bajo el mismo path que root_url."""
    root_path = urlparse(root_url).path.rstrip("/")
    candidate_path = urlparse(url).path
    return is_same_domain(url, root_url) and candidate_path.startswith(root_path)


def is_excluded(url: str, patterns: Set[str]) -> bool:
    """
    Devuelve ``True`` si la URL contiene alguno de los patrones de exclusión.

    La comparación es case-insensitive.
    """
    url_lower = url.lower()
    return any(p.lower() in url_lower for p in patterns)


def extract_links(html: str, base_url: str) -> List[str]:
    """
    Extrae y normaliza todos los hrefs encontrados en ``<a>`` tags.

    Los hrefs relativos se resuelven contra ``base_url`` antes de normalizar.
    """
    soup = BeautifulSoup(html, "lxml")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        links.append(normalize_url(full_url))
    return links

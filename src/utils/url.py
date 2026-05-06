"""
src/utils/url.py
================
Utilidades para normalización y filtrado de URLs.
"""

from typing import List
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    """
    Elimina el fragmento (``#anchor``) de una URL para evitar duplicados.

    Los fragmentos son procesados por el navegador del cliente y no
    representan páginas distintas en el servidor.
    """
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="")
    return urlunparse(normalized)


def is_same_domain(url: str, root_url: str) -> bool:
    """
    Comprueba que ``url`` pertenece al mismo dominio que ``root_url``.
    """
    return urlparse(url).netloc == urlparse(root_url).netloc


def is_excluded(url: str, patterns: List[str]) -> bool:
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

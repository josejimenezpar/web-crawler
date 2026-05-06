"""Módulo de rastreo de sitio para auditoría WCAG.

Este módulo recorre internamente un sitio web, filtra enlaces irrelevantes
como archivos estáticos o rutas externas, y construye una lista de páginas
candidatas que serán analizadas en el resto del pipeline.
"""

from collections import deque
from typing import Dict, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .audit_log import AuditJournal


class SiteScanner:
    """Explora el sitio y devuelve URLs internas válidas para auditoría."""

    def __init__(self, root_url: str, max_depth: int = 3, logger: AuditJournal = None):
        self.root_url = root_url
        self.max_depth = max_depth
        self.logger = logger or AuditJournal()

        parsed = urlparse(root_url)
        self.base_domain = f"{parsed.scheme}://{parsed.netloc}"

        self.queue: List[Tuple[str, int]] = [(root_url, 0)]
        self.visited: set[str] = set()
        self.discovered: List[Dict] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.logger.record(f"Iniciando escaneo desde: {root_url}")
        self.logger.record(f"Dominio base: {self.base_domain}")
        self.logger.record(f"Profundidad máxima: {max_depth}")

    def _normalize_url(self, url: str) -> str:
        """Normaliza una URL eliminando fragmentos y parámetros de seguimiento."""
        parsed = urlparse(url)
        params = parsed.query.split('&') if parsed.query else []

        # Filtrar parámetros de seguimiento que no afectan al contenido real.
        clean_params = [p for p in params if not any(
            p.startswith(prefix) for prefix in ['utm_', 'gclid', 'fbclid', 'msclkid', 'session', 'js']
        )]
        clean_query = '&'.join(clean_params)

        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip('/'),
            parsed.params,
            clean_query,
            ''
        ))
        return normalized

    def _is_valid_html_url(self, url: str) -> bool:
        """Comprueba si la URL apunta a contenido HTML relevante para auditoría."""
        parsed = urlparse(url)
        blocked_ext = [
            '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg',
            '.pdf', '.zip', '.doc', '.docx', '.xlsx', '.mp4', '.mp3',
            '.wav', '.woff', '.ttf', '.eot', '.ico'
        ]

        # Ignorar enlaces a recursos estáticos y archivos que no son páginas HTML.
        if any(parsed.path.lower().endswith(ext) for ext in blocked_ext):
            return False

        # Ignorar rutas de administración, API o servicios que no son útiles para auditoría de páginas.
        blocked_patterns = ['logout', '/admin/', '/api/', '/ws/']
        if any(pattern in parsed.path.lower() for pattern in blocked_patterns):
            return False

        return True

    def _is_same_site(self, url: str) -> bool:
        """Verifica que la URL permanezca dentro del dominio raíz del sitio."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}" == self.base_domain

    def scan(self) -> List[Dict]:
        """Recorre el sitio y devuelve la lista de URLs descubiertas."""
        self.logger.record("Fase 1: RASTREO")

        while self.queue:
            current_url, depth = self.queue.pop(0)
            normalized = self._normalize_url(current_url)

            # Evita volver a procesar la misma página dos veces.
            if normalized in self.visited:
                continue

            # Si la URL excede la profundidad permitida, se descarta.
            if depth > self.max_depth:
                self.logger.record(f"Ignorado por profundidad: {current_url} (nivel {depth})")
                continue

            self.visited.add(normalized)
            self.logger.record(f"Rastreando [{depth}]: {current_url}")

            try:
                response = self.session.get(current_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Guardar la página actual como candidata descubierta.
                self.discovered.append({
                    'url': current_url,
                    'normalized': normalized,
                    'depth': depth,
                    'discovered_from': current_url
                })

                # Explorar enlaces internos encontrados en la página.
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    absolute = urljoin(current_url, href)
                    normalized_link = self._normalize_url(absolute)

                    if not self._is_valid_html_url(absolute):
                        continue
                    if not self._is_same_site(absolute):
                        continue
                    if normalized_link in self.visited:
                        continue

                    self.queue.append((absolute, depth + 1))

            except requests.RequestException as exc:
                self.logger.record(f"Error rastreando {current_url}: {str(exc)[:80]}")
                continue

        self.logger.record(f"Rastreo completado: {len(self.discovered)} URLs descubiertas")
        return self.discovered

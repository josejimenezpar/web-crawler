"""Módulo de rastreo de sitio para auditoría WCAG.

Este módulo es responsable de explorar un sitio web siguiendo enlaces,
descubriendo todas las páginas internas hasta una profundidad máxima.
Filtra enlaces que no son relevantes (archivos, APIs, rutas externas) y
garantiza que solo se rastrean páginas HTML del mismo dominio.

NUEVO: Implementa concurrencia (Multithreading) para descargar páginas 
simultáneamente y acelerar el rastreo drásticamente.
"""

import concurrent.futures
from typing import Dict, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .audit_log import AuditJournal


class SiteScanner:
    """Explora el sitio y devuelve URLs internas válidas para auditoría."""

    def __init__(self, root_url: str, max_depth: int = 3, max_urls: int = 150, logger: AuditJournal = None):
        self.root_url = root_url
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.logger = logger or AuditJournal()
        self.max_workers = 10  # NUEVO: Número de páginas que descargaremos a la vez

        parsed = urlparse(root_url)
        self.base_domain = f"{parsed.scheme}://{parsed.netloc}"
        self.base_path = parsed.path.strip('/') 

        self.visited: set[str] = set()
        self.discovered: List[Dict] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.logger.record(f"Iniciando escaneo desde: {root_url}")
        self.logger.record(f"Ruta base restringida: /{self.base_path}")
        self.logger.record(f"Hilos concurrentes: {self.max_workers}")

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        params = parsed.query.split('&') if parsed.query else []

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
        parsed = urlparse(url)
        blocked_ext = [
            '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg',
            '.pdf', '.zip', '.doc', '.docx', '.xlsx',
            '.mp4', '.mp3', '.wav',
            '.woff', '.ttf', '.eot', '.ico'
        ]

        if any(parsed.path.lower().endswith(ext) for ext in blocked_ext):
            return False

        blocked_patterns = ['logout', '/admin/', '/api/', '/ws/']
        if any(pattern in parsed.path.lower() for pattern in blocked_patterns):
            return False

        return True

    def _is_same_site(self, url: str) -> bool:
        parsed = urlparse(url)
        url_domain = f"{parsed.scheme}://{parsed.netloc}"
        is_same_domain = (url_domain == self.base_domain)
        path_clean = parsed.path.strip('/')
        is_in_subsite = path_clean.startswith(self.base_path)

        return is_same_domain and is_in_subsite

    def _fetch_and_parse(self, url: str, depth: int, normalized: str) -> Tuple[Dict, List[str]]:
        """Descarga y parsea una URL de forma aislada. Pensado para ejecutarse en un hilo."""
        try:
            # Timeout corto para no atascar el hilo con webs caídas
            response = self.session.get(url, timeout=8)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                return None, []

            html_text = response.text
            soup = BeautifulSoup(html_text, 'html.parser')

            page_data = {
                'url': url,
                'normalized': normalized,
                'depth': depth,
                'discovered_from': url,
                'html': html_text
            }

            new_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                absolute = urljoin(url, href)
                if self._is_valid_html_url(absolute) and self._is_same_site(absolute):
                    new_links.append(absolute)

            return page_data, new_links

        except requests.RequestException:
            return None, []

    def scan(self) -> List[Dict]:
        self.logger.record("Fase 1: RASTREO (Concurrente)")
        pbar = tqdm(total=self.max_urls, desc="Rastreando URLs", unit="pág")

        # Empezamos procesando el nivel 0 (solo la URL raíz)
        current_level_urls = [(self.root_url, 0)]

        # Procesamos por niveles de profundidad para mantener el BFS (Breadth-First Search)
        while current_level_urls and len(self.discovered) < self.max_urls:
            next_level_urls = []

            # Lanzamos múltiples hilos para descargar el nivel actual de golpe
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures_map = {}

                for url, depth in current_level_urls:
                    # Freno de seguridad para no mandar miles de tareas si ya casi terminamos
                    if len(self.discovered) + len(futures_map) >= self.max_urls + 20:
                        break

                    normalized = self._normalize_url(url)
                    if normalized in self.visited:
                        continue
                    if depth > self.max_depth:
                        continue

                    self.visited.add(normalized)
                    
                    # Mandamos al trabajador a descargar esta URL
                    future = executor.submit(self._fetch_and_parse, url, depth, normalized)
                    futures_map[future] = (url, depth)

                # Vamos recogiendo los resultados según van terminando los trabajadores
                for future in concurrent.futures.as_completed(futures_map):
                    if len(self.discovered) >= self.max_urls:
                        break  # Cortamos si ya tenemos las que necesitamos

                    url, depth = futures_map[future]
                    try:
                        page_data, new_links = future.result()
                        if page_data:
                            self.discovered.append(page_data)
                            pbar.update(1)
                            self.logger.record(f"Descargada [{depth}]: {url}")
                            
                            # Preparamos los enlaces válidos para que se rastreen en la siguiente vuelta
                            for link in new_links:
                                next_level_urls.append((link, depth + 1))
                    except Exception as e:
                        self.logger.record(f"Error procesando hilo para {url}: {e}")

            # Subimos un nivel de profundidad con los enlaces nuevos que hemos encontrado
            current_level_urls = next_level_urls

        pbar.close()
        self.logger.record(f"Rastreo completado: {len(self.discovered)} URLs descubiertas")
        return self.discovered
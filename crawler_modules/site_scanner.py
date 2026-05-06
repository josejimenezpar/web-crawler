"""Módulo de rastreo de sitio para auditoría WCAG.

Este módulo es responsable de explorar un sitio web siguiendo enlaces,
descubriendo todas las páginas internas hasta una profundidad máxima.
Filtra enlaces que no son relevantes (archivos, APIs, rutas externas) y
garantiza que solo se rastrean páginas HTML del mismo dominio.
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
        """Inicializa el rastreador con la URL inicial y configuración.
        
        Args:
            root_url: la página desde la que empezamos a rastrear (ej: https://www.ejemplo.com)
            max_depth: cuántos niveles de profundidad podemos seguir (3 = hasta 3 clicks de distancia)
            logger: objeto para registrar todo lo que hace (si no se pasa, crea uno nuevo)
        """
        self.root_url = root_url
        self.max_depth = max_depth
        self.logger = logger or AuditJournal()

        # Extrae el dominio base (ej: de https://www.ejemplo.com/pagina → https://www.ejemplo.com)
        # Solo rastrearemos URLs que comiencen con esto para no salir del sitio.
        parsed = urlparse(root_url)
        self.base_domain = f"{parsed.scheme}://{parsed.netloc}"

        # Cola (queue) de URLs por visitar: cada elemento es (URL, profundidad)
        # Empezamos con la URL raíz a profundidad 0
        self.queue: List[Tuple[str, int]] = [(root_url, 0)]
        # Conjunto de URLs ya visitadas para no procesar la misma URL dos veces
        self.visited: set[str] = set()
        # Lista final con todas las URLs que encontramos
        self.discovered: List[Dict] = []
        # Sesión HTTP reutilizable para hacer peticiones eficientemente
        self.session = requests.Session()
        # User-Agent para que los servidores nos reconozcan como navegador legítimo
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Registra en el log que estamos iniciando
        self.logger.record(f"Iniciando escaneo desde: {root_url}")
        self.logger.record(f"Dominio base: {self.base_domain}")
        self.logger.record(f"Profundidad máxima: {max_depth}")

    def _normalize_url(self, url: str) -> str:
        """Normaliza una URL para detectar duplicados.
        
        A veces la misma página se puede acceder de diferentes formas:
        - https://ejemplo.com/pagina?utm_source=google&utm_medium=search
        - https://ejemplo.com/pagina?utm_source=facebook&utm_medium=social
        Ambas apuntan a la MISMA página, solo que con parámetros de seguimiento diferentes.
        Este método las normaliza para que se vea que son idénticas.
        """
        parsed = urlparse(url)
        params = parsed.query.split('&') if parsed.query else []

        # Elimina parámetros que no afectan el contenido real (solo siguen al usuario):
        # utm_* = Google Analytics
        # gclid = Google Ads
        # fbclid = Facebook Ads
        # etc
        clean_params = [p for p in params if not any(
            p.startswith(prefix) for prefix in ['utm_', 'gclid', 'fbclid', 'msclkid', 'session', 'js']
        )]
        clean_query = '&'.join(clean_params)

        # Construye la URL normalizada sin fragmento (#) y con dominio en minúsculas
        normalized = urlunparse((
            parsed.scheme,  # http o https
            parsed.netloc.lower(),  # dominio en minúsculas
            parsed.path.rstrip('/'),  # ruta sin slash final
            parsed.params,  # parámetros especiales (raro)
            clean_query,  # query limpia (sin tracking)
            ''  # sin fragmento (lo que va después de #)
        ))
        return normalized

    def _is_valid_html_url(self, url: str) -> bool:
        """Determina si una URL probablemente apunta a una página HTML auditable.
        
        Nos interesa rastrear solo páginas HTML. Queremos EVITAR:
        - Descargas de archivos (PDF, ZIP, DOC)
        - Recursos (CSS, JavaScript, imágenes)
        - Rutas de administración (/admin/ no queremos auditar eso)
        - APIs (/api/ no son páginas)
        
        Return: True si vale la pena visitar, False si es basura que ignoramos.
        """
        parsed = urlparse(url)
        # Lista de extensiones de archivo que NO son páginas HTML
        blocked_ext = [
            '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg',  # Recursos web
            '.pdf', '.zip', '.doc', '.docx', '.xlsx',  # Descargas
            '.mp4', '.mp3', '.wav',  # Multimedia
            '.woff', '.ttf', '.eot', '.ico'  # Fuentes e iconos
        ]

        # Si la URL termina en una extensión bloqueada, ignorar
        if any(parsed.path.lower().endswith(ext) for ext in blocked_ext):
            return False

        # Patrones de ruta que no queremos auditar (no son páginas de usuario)
        blocked_patterns = ['logout', '/admin/', '/api/', '/ws/']
        if any(pattern in parsed.path.lower() for pattern in blocked_patterns):
            return False

        # Si pasó todos los filtros, es probablemente una página HTML válida
        return True

    def _is_same_site(self, url: str) -> bool:
        """Verifica que la URL sea interna (del mismo dominio).
        
        Queremos evitar seguir enlaces a sitios externos. Si comenzamos en
        https://ejemplo.com, solo seguimos URLs que comiencen con https://ejemplo.com
        Ignoramos https://google.com, https://otro-sitio.com, etc.
        """
        parsed = urlparse(url)
        # Extrae el dominio completo de la URL: https://subdomain.ejemplo.com/pagina → https://subdomain.ejemplo.com
        url_domain = f"{parsed.scheme}://{parsed.netloc}"
        # Devuelve True si coincide con nuestro dominio base, False si es externo
        return url_domain == self.base_domain

    def scan(self) -> List[Dict]:
        """Ejecuta el rastreo completo del sitio.
        
        Este es el método principal. Usa BFS (búsqueda en amplitud):
        1. Procesa las URLs de la cola una por una
        2. Descarga cada página y extrae sus enlaces
        3. Añade esos enlaces a la cola si cumplen criterios
        4. Repite hasta vaciar la cola
        
        Return: lista de diccionarios con información de cada página encontrada
        """
        self.logger.record("Fase 1: RASTREO")

        # Mientras haya URLs por procesar en la cola...
        while self.queue:
            # Saca la primera URL de la cola (FIFO - First In First Out)
            current_url, depth = self.queue.pop(0)
            # Normaliza para detectar si ya la hemos procesado
            normalized = self._normalize_url(current_url)

            # Si ya visitamos esta URL normalizada, la saltamos (evita duplicados)
            if normalized in self.visited:
                continue

            # Si la profundidad es mayor que el máximo permitido, ignora
            if depth > self.max_depth:
                self.logger.record(f"Ignorado por profundidad: {current_url} (nivel {depth})")
                continue

            # Marca como visitada para no procesarla otra vez
            self.visited.add(normalized)
            self.logger.record(f"Rastreando [{depth}]: {current_url}")

            try:
                # Intenta descargar la página
                response = self.session.get(current_url, timeout=10)
                # Lanza excepción si el servidor respondió con error (404, 500, etc)
                response.raise_for_status()
                # Parsea el HTML con BeautifulSoup para extraer enlaces
                soup = BeautifulSoup(response.text, 'html.parser')

                # Guarda la página actual como descubierta
                self.discovered.append({
                    'url': current_url,
                    'normalized': normalized,
                    'depth': depth,
                    'discovered_from': current_url
                })

                # Busca todos los enlaces <a href="..."> en la página
                for link in soup.find_all('a', href=True):
                    href = link['href']  # El valor del atributo href
                    # Convierte URL relativa a absoluta (ej: /pagina → https://ejemplo.com/pagina)
                    absolute = urljoin(current_url, href)
                    # Normaliza esta nueva URL
                    normalized_link = self._normalize_url(absolute)

                    # Verifica si es una URL válida
                    if not self._is_valid_html_url(absolute):
                        continue  # Salta este enlace (archivo, extensión bloqueada, etc)
                    if not self._is_same_site(absolute):
                        continue  # Salta este enlace (es de otro sitio)
                    if normalized_link in self.visited:
                        continue  # Ya la procesamos

                    # Si pasó todos los filtros, la añade a la cola para procesarla luego
                    self.queue.append((absolute, depth + 1))

            except requests.RequestException as exc:
                # Si hay error de red/servidor, lo registra pero continúa
                self.logger.record(f"Error rastreando {current_url}: {str(exc)[:80]}")
                continue

        # Al terminar, reporta cuántas URLs descubrió
        self.logger.record(f"Rastreo completado: {len(self.discovered)} URLs descubiertas")
        return self.discovered

"""Módulo para clasificar páginas web según su función y complejidad."""

from typing import Dict, List, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class FunctionalClassifier:
    """Determina el tipo funcional y la complejidad de cada página web."""

    def __init__(self, session: requests.Session, root_url: str = ""):
        self.session = session
        # Guardamos la URL raíz para identificarla siempre como página de inicio
        self.root_url = root_url.rstrip('/')

    def analyze(self, url: str, html_content: str = None) -> Dict[str, Any]:
        """Analiza una URL y devuelve las etiquetas funcionales y su nivel de complejidad."""
        categories: List[str] = []
        complexity = "Desconocida"

        try:
            if html_content:
                html_text = html_content
            else:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                html_text = response.text
                
            soup = BeautifulSoup(html_text, 'html.parser')
        except Exception:
            return {'categories': [], 'complexity': complexity}

        parsed = urlparse(url)
        path = parsed.path.lower()
        clean_url = url.rstrip('/')

        # --- 1. CLASIFICACIÓN FUNCIONAL ---
        
        # Inicio: si es la URL raíz o patrones comunes
        if clean_url == self.root_url or path in ['/', '', '/index', '/index.html']:
            categories.append('inicio')

        # Informativo: noticias, blog o etiquetas semánticas
        if any(pattern in path for pattern in ['/noticias', '/blog', '/articulos', '/informacion']):
            categories.append('informativo')
        elif soup.find('article') or soup.find('main'):
            categories.append('informativo')

        # Navegación: listados y menús
        if any(pattern in path for pattern in ['/servicios', '/tramites', '/categorias', '/listado']):
            categories.append('navegacion')
        elif len(soup.find_all('li')) > 5:
            categories.append('navegacion')

        # Formulario
        if soup.find('form'):
            categories.append('formulario')

        # Servicio
        if any(pattern in path for pattern in ['/tramites', '/servicios', '/solicitud', '/proceso']):
            categories.append('servicio')

        # Dinámico
        if soup.find('script') and ('fetch' in html_text or 'axios' in html_text):
            categories.append('dinamico')

        if not categories:
            categories.append('otro')

        # --- 2. CÁLCULO DE COMPLEJIDAD ---
        elementos = soup.find_all(['a', 'button', 'img', 'table', 'form', 'input', 'select', 'iframe', 'video'])
        total_elementos = len(elementos)

        if total_elementos < 40:
            complexity = "Baja"
        elif total_elementos < 100:
            complexity = "Media"
        else:
            complexity = "Alta"

        return {
            'categories': categories,
            'complexity': complexity
        }
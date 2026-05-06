"""Módulo para clasificar páginas web según su función.

Después de descubrir páginas, necesitamos entender qué tipo de página es cada una.
Este módulo analiza cada página y le asigna categorías funcionales como:
- 'inicio': la página principal del sitio
- 'formulario': página que contiene un formulario
- 'servicio': página orientada a trámites o solicitudes
- 'navegacion': página con listados/menús
- 'informativo': página con contenido informativo/noticias
- 'dinamico': usa JavaScript para cargar contenido

Esta información es crucial para seleccionar una muestra equilibrada.
"""

from typing import List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class FunctionalClassifier:
    """Determina el tipo funcional de cada página web."""

    def __init__(self, session: requests.Session):
        self.session = session

    def classify(self, url: str) -> List[str]:
        """Clasifica una URL y devuelve las etiquetas funcionales que se aplican."""
        categories: List[str] = []

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException:
            # Si no se puede obtener la página, no se asignan categorías.
            return []

        parsed = urlparse(url)
        path = parsed.path.lower()

        # Inicio: páginas principales del sitio.
        if path in ['/', '', '/index', '/index.html']:
            categories.append('inicio')

        # Informativo: páginas que contienen noticias, artículos o secciones de información.
        if any(pattern in path for pattern in ['/noticias', '/blog', '/articulos', '/informacion']):
            categories.append('informativo')
        elif soup.find('article') or soup.find('main'):
            categories.append('informativo')

        # Navegación: páginas con listados y menús extensos.
        if any(pattern in path for pattern in ['/servicios', '/tramites', '/categorias', '/listado']):
            categories.append('navegacion')
        elif len(soup.find_all('li')) > 5:
            categories.append('navegacion')

        # Formulario: presencia de formularios en la página.
        if soup.find('form'):
            categories.append('formulario')

        # Servicio: páginas orientadas a trámites o solicitudes.
        if any(pattern in path for pattern in ['/tramites', '/servicios', '/solicitud', '/proceso']):
            categories.append('servicio')

        # Dinámico: página que probablemente usa JavaScript para cargar contenido.
        if soup.find('script') and ('fetch' in response.text or 'axios' in response.text):
            categories.append('dinamico')

        # Si no se detecta ninguna categoría conocida, asignar 'otro'.
        if not categories:
            categories.append('otro')

        return categories

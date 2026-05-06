"""
src
===
Web Crawler para generación de muestras IRA de accesibilidad.

Fases:
  1. crawl()             — Rastreo del sitio web
  2. classify_pages()    — Clasificación funcional
  3. select_pages()      — Selección de muestra
  4. validate_and_adjust()— Validación y ajustes
  5. export()            — Exportación de resultados
"""

__version__ = "0.2.0"

from src.models import Config, PageRecord
from src.core import crawl, classify_pages, select_pages, validate_and_adjust
from src.io import export

__all__ = [
    "Config",
    "PageRecord",
    "crawl",
    "classify_pages",
    "select_pages",
    "validate_and_adjust",
    "export",
]

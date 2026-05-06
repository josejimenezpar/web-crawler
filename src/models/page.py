"""
src/models/page.py
==================
Estructura de datos de página rastreada.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PageRecord:
    """
    Representa una página rastreada y su metadatos asociados.

    Attributes
    ----------
    url : str
        URL normalizada (sin fragmento) de la página.
    depth : int
        Nivel de profundidad desde la URL raíz (0 = página raíz).
    source_url : str
        URL de la página desde la que se descubrió este enlace. Vacío
        para la página raíz.
    html_snapshot : str
        HTML completo del DOM tal como lo devuelve Playwright tras la
        renderización de JavaScript.
    status_code : int
        Código de respuesta HTTP. Solo se incluyen páginas con 2xx/3xx.
    functional_types : list[str]
        Categorías funcionales asignadas por classificador.
        Posibles valores: ``home``, ``form``, ``navigation``, ``dynamic``,
        ``informational``.
    selection_mode : str or None
        Modo de selección: ``"directed"``, ``"random"``, o ``None``.
    """

    url: str
    depth: int
    source_url: str
    html_snapshot: str
    status_code: int
    functional_types: List[str] = field(default_factory=list)
    selection_mode: Optional[str] = None

"""
src/models/config.py
====================
Configuración central del crawler.

Define la dataclass ``Config`` que agrupa todos los parámetros de ejecución
y la lista de patrones de URL excluidos por defecto.
"""

from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Patrones de URL excluidos por defecto
# ---------------------------------------------------------------------------

EXCLUDE_DEFAULTS = [
    # Acciones de sesión: no aportan contenido evaluable
    "logout", "signout", "sign-out",
    # Parámetros de sesión en query string: generan URLs duplicadas funcionalmente
    "sid=", "sessionid=", "token=",
    # Recursos estáticos no HTML: irrelevantes para la muestra de accesibilidad
    ".pdf", ".css", ".js", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf",
    # Archivos binarios y documentos descargables
    ".mp4", ".mp3", ".zip", ".exe", ".xlsx", ".docx",
    # Esquemas no HTTP: no son páginas web navegables
    "mailto:", "tel:", "javascript:",
]


@dataclass
class Config:
    """
    Parámetros de ejecución del crawler.

    Attributes
    ----------
    root_url : str
        URL raíz del sitio a rastrear.
    max_depth : int
        Número máximo de niveles de profundidad (default: 3).
    min_pages : int
        Mínimo de páginas a seleccionar (default: 15).
    random_pct : float
        Porcentaje mínimo de páginas aleatorias (default: 10.0).
    exclude_patterns : list[str]
        Patrones de URL a excluir.
    delay_seconds : float
        Pausa entre peticiones en segundos (default: 1.0).
    page_timeout_ms : int
        Timeout por página en ms (default: 15000).
    output_dir : str
        Directorio de salida (default: ./output).
    """

    root_url: str
    max_depth: int = 3
    min_pages: int = 15
    random_pct: float = 10.0
    exclude_patterns: List[str] = field(default_factory=lambda: list(EXCLUDE_DEFAULTS))
    delay_seconds: float = 1.0
    page_timeout_ms: int = 15000
    output_dir: str = "./output"

    def __post_init__(self) -> None:
        self.root_url = self.root_url.rstrip("/")
        for pattern in EXCLUDE_DEFAULTS:
            if pattern not in self.exclude_patterns:
                self.exclude_patterns.append(pattern)

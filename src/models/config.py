"""
src/models/config.py
====================
Configuración central del crawler.

Define la dataclass ``Config`` que agrupa todos los parámetros de ejecución
y la lista de patrones de URL excluidos por defecto.
"""

from dataclasses import dataclass, field
from typing import Set


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
    exclude_patterns : set[str]
        Patrones de URL a excluir.
    """

    root_url: str
    max_depth: int = 3
    max_crawled: int = 400
    min_pages: int = 15
    random_pct: float = 10.0
    exclude_patterns: Set[str] = field(default_factory=lambda: set(EXCLUDE_DEFAULTS))
    confine_to_path: bool = True
    max_concurrency: int = 10
    delay_seconds: float = 1.0
    page_timeout_ms: int = 15000
    output_dir: str = "./output"

    def __post_init__(self) -> None:
        # Elimina barras diagonales finales de la URL raíz para evitar duplicados
        self.root_url = self.root_url.rstrip("/")
        # Combina patrones personalizados con los patrones por defecto
        self.exclude_patterns.update(EXCLUDE_DEFAULTS)

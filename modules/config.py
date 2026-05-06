"""
modules/config.py
=================
Configuración central del crawler.

Define la dataclass ``Config`` que agrupa todos los parámetros de ejecución
y la lista de patrones de URL excluidos por defecto. Todos los módulos del
proyecto reciben un ``Config`` como única fuente de verdad para evitar
parámetros dispersos entre funciones.
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


# ---------------------------------------------------------------------------
# Dataclass de configuración
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """
    Parámetros de ejecución del crawler.

    Attributes
    ----------
    root_url : str
        URL raíz del sitio a rastrear. El crawler permanece dentro de este
        dominio. El trailing slash se elimina en ``__post_init__``.
    max_depth : int
        Número máximo de niveles de profundidad a explorar desde ``root_url``.
        Nivel 0 es la página raíz; nivel 1 son los enlaces directos de ésta, etc.
    min_pages : int
        Mínimo de páginas que debe contener la muestra final. Si el crawler
        no encuentra suficientes páginas se registra una advertencia en el log.
    random_pct : float
        Porcentaje mínimo de páginas que deben elegirse aleatoriamente sobre
        el total de la muestra. Se redondea al alza (ceiling). Por defecto 10 %,
        lo que equivale a 2 páginas en una muestra de 15.
    exclude_patterns : list[str]
        Subcadenas que, si aparecen en una URL (case-insensitive), hacen que
        dicha URL sea descartada durante el rastreo. Se inicializa con
        ``EXCLUDE_DEFAULTS`` y puede ampliarse desde la CLI con ``--exclude``.
    delay_seconds : float
        Pausa en segundos entre peticiones HTTP. Evita sobrecargar el servidor
        y reduce la probabilidad de ser bloqueado por rate-limiting.
    page_timeout_ms : int
        Tiempo máximo de espera por página en milisegundos. Si Playwright no
        recibe respuesta en este plazo, la URL se descarta silenciosamente.
    output_dir : str
        Directorio donde se guardan el JSON de la muestra y el log de ejecución.
        Se crea automáticamente si no existe.
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
        # Normalizar la URL raíz para que las comparaciones de dominio sean consistentes.
        # Sin esto, "https://example.com" y "https://example.com/" se tratarían distinto.
        self.root_url = self.root_url.rstrip("/")

        # Garantizar que los patrones por defecto siempre estén presentes aunque el
        # usuario haya pasado una lista personalizada desde la CLI. Se añaden solo
        # los que faltan para no duplicar entradas.
        for pattern in EXCLUDE_DEFAULTS:
            if pattern not in self.exclude_patterns:
                self.exclude_patterns.append(pattern)

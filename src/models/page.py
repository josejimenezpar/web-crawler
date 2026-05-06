"""
src/models/page.py
==================
Estructura de datos de página rastreada.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from src.models.constants import FunctionalType, SelectionMode


@dataclass
class PageRecord:
    url: str
    depth: int
    source_url: str
    html_snapshot: str
    status_code: int
    functional_types: List[FunctionalType] = field(default_factory=list)
    selection_mode: Optional[SelectionMode] = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

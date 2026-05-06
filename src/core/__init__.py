"""
src/core
========
Lógica principal del crawler: rastreo, clasificación, selección y validación.
"""

from src.core.crawler import crawl
from src.core.classifier import classify_pages
from src.core.selector import select_pages
from src.core.validator import validate_and_adjust

__all__ = ["crawl", "classify_pages", "select_pages", "validate_and_adjust"]

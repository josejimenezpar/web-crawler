"""
src/utils
=========
Funciones auxiliares del crawler.
"""

from src.utils.url import normalize_url, is_same_domain, is_excluded, extract_links

__all__ = ["normalize_url", "is_same_domain", "is_excluded", "extract_links"]

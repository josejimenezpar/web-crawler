"""
src/models
==========
Estructuras de datos centralizadas del crawler.
"""

from src.models.page import PageRecord
from src.models.config import Config, EXCLUDE_DEFAULTS
from src.models.constants import FunctionalType, SelectionMode, MANDATORY_TYPES
from src.models.queue import QueueItem
from src.models.crawl_result import CrawlResult

__all__ = [
    "PageRecord", "Config", "EXCLUDE_DEFAULTS",
    "FunctionalType", "SelectionMode", "MANDATORY_TYPES",
    "QueueItem", "CrawlResult",
]

"""
src/models/crawl_result.py
==========================
Resultado del rastreo BFS.
"""

from dataclasses import dataclass
from typing import List

from src.models.page import PageRecord


@dataclass
class CrawlResult:
    pages: List[PageRecord]
    visited: int
    timeouts: int = 0
    errors: int = 0
    http_errors: int = 0

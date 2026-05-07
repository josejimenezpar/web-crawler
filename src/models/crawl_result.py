"""
src/models/crawl_result.py
==========================
Resultado del rastreo BFS.
"""

from dataclasses import dataclass, field
from typing import List

from src.models.page import PageRecord


@dataclass
class CrawlResult:
    pages: List[PageRecord]
    visited: int
    timeouts: int = 0
    errors: int = 0
    http_errors: int = 0
    timeout_urls: List[str] = field(default_factory=list)
    error_urls: List[str] = field(default_factory=list)
    http_error_urls: List[str] = field(default_factory=list)

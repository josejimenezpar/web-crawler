from typing import NamedTuple


class QueueItem(NamedTuple):
    url: str
    depth: int
    source_url: str

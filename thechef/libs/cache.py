"""Tiny in-memory TTL cache, to save rate-limited API quota on repeated searches."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float = 3600, max_items: int = 256):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()

    def get(self, key):
        item = self._data.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.monotonic():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key, value) -> None:
        self._data[key] = (time.monotonic() + self.ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)

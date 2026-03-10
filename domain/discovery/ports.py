"""
Discovery context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.discovery.models import DistrictMap, SearchResult


class SearchPort(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[SearchResult]: ...


class ZipLookupPort(ABC):
    @abstractmethod
    def lookup(self, zip_code: str) -> DistrictMap | None: ...

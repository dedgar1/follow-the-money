"""
Comparison context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.comparison.models import ComparisonReport
from domain.identity.models import RepId


class ComparisonRepository(ABC):
    @abstractmethod
    def get_report(self, rep_ids: list[RepId]) -> ComparisonReport | None: ...

    @abstractmethod
    def save_report(self, report: ComparisonReport) -> None: ...

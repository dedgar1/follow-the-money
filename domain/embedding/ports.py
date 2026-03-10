"""
Embedding context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.embedding.models import WidgetConfig, WidgetPayload


class WidgetRenderer(ABC):
    @abstractmethod
    def render(self, config: WidgetConfig) -> WidgetPayload: ...

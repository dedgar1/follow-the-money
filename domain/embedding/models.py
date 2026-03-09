"""
Embedding bounded context — embeddable widgets for third-party sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WidgetType(str, Enum):
    FUNDING_SUMMARY  = "funding_summary"
    TOP_DONORS       = "top_donors"
    ALIGNMENT_SCORE  = "alignment_score"


@dataclass
class WidgetConfig:
    rep_id:      str
    widget_type: WidgetType
    theme:       str = "light"
    max_items:   int = 5


@dataclass
class WidgetPayload:
    config:  WidgetConfig
    data:    dict = field(default_factory=dict)
    html:    str = ""

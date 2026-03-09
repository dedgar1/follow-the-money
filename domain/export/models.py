"""
Export bounded context — public REST endpoints, CSV/JSON exports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExportFormat(str, Enum):
    CSV  = "csv"
    JSON = "json"


class ExportStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETE   = "complete"
    FAILED     = "failed"


@dataclass
class ExportJob:
    id:           str
    rep_id:       str
    format:       ExportFormat
    status:       ExportStatus = ExportStatus.PENDING
    download_url: str | None = None

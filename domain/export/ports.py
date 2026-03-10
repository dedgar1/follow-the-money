"""
Export context output ports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.export.models import ExportJob


class ExportRepository(ABC):
    @abstractmethod
    def get_job(self, job_id: str) -> ExportJob | None: ...

    @abstractmethod
    def save_job(self, job: ExportJob) -> None: ...

"""
ElectionCycle value object — US federal election cycles are 2-year periods
ending on an even-numbered year.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class ElectionCycle:
    year: int  # The even-numbered election year, e.g. 2024

    def __post_init__(self) -> None:
        if self.year % 2 != 0:
            raise ValueError(f"Election cycle year must be even, got {self.year}")
        if self.year < 1974 or self.year > 2100:
            raise ValueError(f"Election cycle year {self.year} is out of range")

    @property
    def start_year(self) -> int:
        return self.year - 1

    @property
    def label(self) -> str:
        return f"{self.start_year}–{self.year}"

    @classmethod
    def current(cls) -> ElectionCycle:
        y = datetime.date.today().year
        return cls(year=y if y % 2 == 0 else y + 1)

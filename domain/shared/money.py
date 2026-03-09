"""
Money value object — immutable, currency-aware.
Stores integer cents to avoid float precision issues.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    cents: int          # always in USD cents
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValueError("Money cannot be negative")
        if len(self.currency) != 3:
            raise ValueError("Currency must be a 3-character ISO code")

    @classmethod
    def from_dollars(cls, dollars: float) -> Money:
        return cls(cents=round(dollars * 100))

    @property
    def dollars(self) -> float:
        return self.cents / 100

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(cents=self.cents + other.cents, currency=self.currency)

    def __repr__(self) -> str:
        return f"${self.dollars:,.2f}"

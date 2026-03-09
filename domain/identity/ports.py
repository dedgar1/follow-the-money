"""
Identity context output ports — abstract interfaces that adapters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.identity.models import CanonicalDonor, CanonicalRep, DonorId, RepId


class IdentityRepository(ABC):
    @abstractmethod
    def get_rep(self, rep_id: RepId) -> CanonicalRep | None: ...

    @abstractmethod
    def save_rep(self, rep: CanonicalRep) -> None: ...

    @abstractmethod
    def get_donor(self, donor_id: DonorId) -> CanonicalDonor | None: ...

    @abstractmethod
    def save_donor(self, donor: CanonicalDonor) -> None: ...

    @abstractmethod
    def find_rep_by_fec_id(self, fec_id: str) -> CanonicalRep | None: ...

    @abstractmethod
    def find_donor_by_fec_id(self, fec_id: str) -> CanonicalDonor | None: ...

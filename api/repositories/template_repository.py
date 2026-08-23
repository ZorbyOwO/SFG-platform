from __future__ import annotations

from abc import ABC, abstractmethod


class TemplateRepository(ABC):
    """Isolation boundary for the unresolved encrypted-template/search design.

    Implementations must never expose a stored template to a browser. The development
    implementation stores only accepted-capture counts, not embeddings or input bytes.
    """

    @abstractmethod
    async def record_development_acceptance(self, subject_id: str, pose: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def revoke_subject(self, subject_id: str) -> None:
        raise NotImplementedError


class CountingTemplateRepository(TemplateRepository):
    def __init__(self) -> None:
        self._positions: dict[str, set[str]] = {}

    async def record_development_acceptance(self, subject_id: str, pose: str) -> int:
        positions = self._positions.setdefault(subject_id, set())
        positions.add(pose)
        return len(positions)

    async def revoke_subject(self, subject_id: str) -> None:
        self._positions.pop(subject_id, None)

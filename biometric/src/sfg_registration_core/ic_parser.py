"""Conservative parsing of unconfirmed Malaysian IC registration candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_IC_PATTERN = re.compile(r"(?<!\d)(\d{6})[- ]?(\d{2})[- ]?(\d{4})(?!\d)")
_NAME_PATTERN = re.compile(r"^(?:NAME|NAMA)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_SAFE_NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z .'-]{1,118}")


@dataclass(frozen=True)
class ICCandidates:
    """Unconfirmed OCR candidates; never authoritative identity data."""

    full_name: str | None
    ic: str | None
    requires_confirmation: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "full_name": self.full_name,
            "ic": self.ic,
            "requires_confirmation": True,
        }


def _unique(values: Iterable[str]) -> str | None:
    distinct = list(dict.fromkeys(values))
    return distinct[0] if len(distinct) == 1 else None


def normalize_malaysian_ic(value: str) -> str | None:
    """Return ######-##-#### only when the complete value is unambiguous."""

    if not isinstance(value, str) or not value.strip():
        return None
    matches = list(_IC_PATTERN.finditer(value))
    if len(matches) != 1:
        return None
    match = matches[0]
    before = value[: match.start()].strip()
    after = value[match.end() :].strip()
    if any(char.isdigit() for char in before + after):
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _normalize_name(value: str) -> str | None:
    candidate = " ".join(value.split()).strip(" .")
    if not _SAFE_NAME_PATTERN.fullmatch(candidate):
        return None
    if not any(char.isalpha() for char in candidate):
        return None
    return candidate.upper()


def extract_ic_candidates(lines: Iterable[str]) -> ICCandidates:
    """Extract unique IC and explicitly labelled name candidates only."""

    normalized_lines = [line.strip() for line in lines if isinstance(line, str) and line.strip()]
    ic_values: list[str] = []
    names: list[str] = []
    for line in normalized_lines:
        matches = list(_IC_PATTERN.finditer(line))
        for match in matches:
            normalized = normalize_malaysian_ic(match.group(0))
            if normalized is not None:
                ic_values.append(normalized)
        name_match = _NAME_PATTERN.fullmatch(line)
        if name_match:
            normalized_name = _normalize_name(name_match.group(1))
            if normalized_name is not None:
                names.append(normalized_name)
    return ICCandidates(full_name=_unique(names), ic=_unique(ic_values))


__all__ = ["ICCandidates", "extract_ic_candidates", "normalize_malaysian_ic"]

"""One-package SFG registration facade with lazy mother loading."""

from __future__ import annotations

from typing import Any


__all__ = ["SFGRegistrationCore", "SafeFaceResult"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .registration_core import SFGRegistrationCore, SafeFaceResult

        return {"SFGRegistrationCore": SFGRegistrationCore, "SafeFaceResult": SafeFaceResult}[name]
    raise AttributeError(name)

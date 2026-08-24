from __future__ import annotations


def test_registration_facade_is_importable() -> None:
    from sfg_registration_core import SFGRegistrationCore

    assert SFGRegistrationCore.__name__ == "SFGRegistrationCore"

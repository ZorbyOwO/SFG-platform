from __future__ import annotations

import pytest

from api.contracts import (
    AuthorizationStatus,
    IdentityConfirmationStatus,
    LivenessStatus,
    MatchStatus,
    PinStatus,
)
from api.services.authorization import authorization_decision


@pytest.mark.parametrize("overrides", [
    {"liveness_status": LivenessStatus.REJECT},
    {"liveness_status": LivenessStatus.UNCERTAIN},
    {"liveness_status": LivenessStatus.ERROR},
    {"match_status": MatchStatus.NO_MATCH},
    {"match_status": MatchStatus.AMBIGUOUS},
    {"match_status": MatchStatus.ERROR},
    {"identity_confirmation_status": IdentityConfirmationStatus.REJECTED, "identity_confirmation_enabled": True},
    {"pin_status": PinStatus.REJECTED},
    {"pin_status": PinStatus.LOCKED},
])
def test_every_negative_gate_fails_closed(overrides) -> None:
    baseline = {
        "liveness_status": LivenessStatus.LIVE,
        "match_status": MatchStatus.CONFIRMED,
        "identity_confirmation_status": None,
        "pin_status": PinStatus.ACCEPTED,
        "identity_confirmation_enabled": False,
        "pin_required": True,
    }
    assert authorization_decision(**(baseline | overrides)) is AuthorizationStatus.DENIED


def test_only_complete_policy_grants() -> None:
    assert authorization_decision(
        liveness_status=LivenessStatus.LIVE,
        match_status=MatchStatus.CONFIRMED,
        identity_confirmation_status=IdentityConfirmationStatus.CONFIRMED,
        pin_status=PinStatus.ACCEPTED,
        identity_confirmation_enabled=True,
        pin_required=True,
    ) is AuthorizationStatus.GRANTED

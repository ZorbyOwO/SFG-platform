from __future__ import annotations

from ..contracts import (
    AuthorizationStatus,
    IdentityConfirmationStatus,
    LivenessStatus,
    MatchStatus,
    PinStatus,
)


def authorization_decision(
    *,
    liveness_status: LivenessStatus | None,
    match_status: MatchStatus | None,
    identity_confirmation_status: IdentityConfirmationStatus | None,
    pin_status: PinStatus | None,
    identity_confirmation_enabled: bool = False,
    pin_required: bool = True,
) -> AuthorizationStatus:
    if liveness_status is not LivenessStatus.LIVE:
        return AuthorizationStatus.DENIED
    if match_status is not MatchStatus.CONFIRMED:
        return AuthorizationStatus.DENIED
    if identity_confirmation_enabled and identity_confirmation_status is not IdentityConfirmationStatus.CONFIRMED:
        return AuthorizationStatus.DENIED
    if pin_required and pin_status is not PinStatus.ACCEPTED:
        return AuthorizationStatus.DENIED
    return AuthorizationStatus.GRANTED

"""Regression guards for the real pinned core running inside this tier.

These are not behaviour-driving tests: the pipeline itself is covered by the
frozen mother's own suite. They exist to catch the two failures that would
silently break every stored template — the core failing to load, and the
compatibility fingerprint drifting away from the validated Core v1 baseline.

They skip when the commit-pinned payloads have not been acquired.
"""

from __future__ import annotations

import numpy as np
import pytest

from api.contracts import CaptureStatus, LivenessStatus
from api.services.biometric_core import CoreCVBiometricEngine, CoreCVUnavailable, default_corecv_root


# The fingerprint recorded by the Core v1 human validation gate. A change here
# means stored templates are no longer comparable and must be re-enrolled.
VALIDATED_FINGERPRINT = "a18bbbd47a57d14d"


@pytest.fixture(scope="module")
def engine() -> CoreCVBiometricEngine:
    try:
        return CoreCVBiometricEngine.from_package(default_corecv_root())
    except CoreCVUnavailable as exc:
        pytest.skip(f"pinned core unavailable: {exc.code}")


def jpeg(image: np.ndarray) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    assert ok
    return buffer.tobytes()


def synthetic_face(size: int = 480) -> np.ndarray:
    """A drawn, non-person face fixture. No real image or dataset is used."""

    import cv2

    frame = np.full((size, size, 3), 235, np.uint8)
    cx, cy = size // 2, size // 2
    cv2.ellipse(frame, (cx, cy), (size // 5, int(size // 3.4)), 0, 0, 360, (172, 190, 214), -1)
    cv2.ellipse(frame, (cx, cy - size // 9), (size // 5, size // 7), 0, 180, 360, (120, 138, 165), -1)
    for dx in (-size // 13, size // 13):
        cv2.ellipse(frame, (cx + dx, cy - size // 22), (size // 30, size // 52), 0, 0, 360, (255, 255, 255), -1)
        cv2.circle(frame, (cx + dx, cy - size // 22), size // 68, (60, 45, 35), -1)
        cv2.ellipse(frame, (cx + dx, cy - size // 15), (size // 26, size // 60), 0, 180, 360, (90, 100, 120), 3)
    cv2.ellipse(frame, (cx, cy + size // 30), (size // 46, size // 22), 0, 0, 180, (140, 158, 184), 2)
    cv2.ellipse(frame, (cx, cy + size // 8), (size // 20, size // 40), 0, 0, 180, (110, 110, 150), -1)
    return cv2.GaussianBlur(frame, (5, 5), 0)


def test_the_loaded_core_matches_the_validated_compatibility_fingerprint(
    engine: CoreCVBiometricEngine,
) -> None:
    assert engine.fingerprint_id == VALIDATED_FINGERPRINT


def test_health_reports_every_pinned_model_as_loaded(engine: CoreCVBiometricEngine) -> None:
    health = engine.health()

    assert health["yunet"] == "loaded"
    assert health["sface"] == "loaded"
    assert health["antispoof"] == "loaded"
    assert health["compatibility_fingerprint"] == VALIDATED_FINGERPRINT


def test_a_blank_frame_reports_no_face_through_the_real_detector(
    engine: CoreCVBiometricEngine,
) -> None:
    verdict = engine.analyse_enrolment(jpeg(np.zeros((480, 640, 3), np.uint8)), "image/jpeg")

    assert verdict.capture_status is CaptureStatus.NO_FACE
    assert verdict.template_generated is False


def test_a_noise_frame_reports_no_face_through_the_real_detector(
    engine: CoreCVBiometricEngine,
) -> None:
    noise = np.random.default_rng(7).integers(0, 255, (480, 640, 3), dtype=np.uint8)

    verdict = engine.analyse_enrolment(jpeg(noise), "image/jpeg")

    assert verdict.capture_status is CaptureStatus.NO_FACE
    assert verdict.template_generated is False


def test_a_flat_drawn_face_is_detected_but_never_passes_liveness(
    engine: CoreCVBiometricEngine,
) -> None:
    """Detection must fire, and passive PAD must refuse to call a flat render live."""

    verdict = engine.analyse_enrolment(jpeg(synthetic_face()), "image/jpeg")

    assert verdict.capture_status is CaptureStatus.READY
    assert verdict.liveness_status is not LivenessStatus.LIVE
    assert verdict.template_generated is False
    assert verdict.accepted is False

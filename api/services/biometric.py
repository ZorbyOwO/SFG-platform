from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..contracts import CaptureStatus, LivenessStatus, MatchStatus
from ..errors import ApiError


@dataclass(frozen=True, slots=True)
class BiometricVerdict:
    capture_status: CaptureStatus
    liveness_status: LivenessStatus | None = None
    match_status: MatchStatus | None = None


class DevelopmentBiometricEngine:
    """Explicit simulator that never computes or stores a biometric template.

    Scenario selection is accepted only while APP_ENV is development/test. Uploaded
    bytes are checked, discarded, and never included in a log, response, or fixture.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def health(self) -> dict[str, str]:
        def state(path: str | None) -> str:
            return "configured_not_loaded" if path else "unavailable"

        return {
            "yunet": state(self.settings.yunet_model_path),
            "sface": state(self.settings.sface_model_path),
            "antispoof": state(self.settings.pad_model_dir),
            "ocr": state(self.settings.paddleocr_model_dir),
            "adapter": "development_simulation",
        }

    def _validate_input(self, image: bytes, content_type: str | None) -> None:
        if content_type not in {"image/jpeg", "image/png"}:
            raise ApiError(415, "invalid_media_type", "Upload a JPEG or PNG image.")
        if not image or len(image) > self.settings.max_upload_bytes:
            raise ApiError(413, "invalid_capture", "The image is empty or exceeds the upload limit.")

    def analyse_enrolment(self, image: bytes, content_type: str | None, scenario: str) -> BiometricVerdict:
        self._validate_input(image, content_type)
        if self.settings.app_env not in {"development", "test"}:
            raise ApiError(503, "models_unavailable", "Biometric models are not available.")
        mapping = {
            "success": BiometricVerdict(CaptureStatus.READY, LivenessStatus.LIVE),
            "no_face": BiometricVerdict(CaptureStatus.NO_FACE),
            "multiple_faces": BiometricVerdict(CaptureStatus.MULTIPLE_FACES),
            "invalid_capture": BiometricVerdict(CaptureStatus.INVALID),
            "camera_error": BiometricVerdict(CaptureStatus.CAMERA_ERROR),
            "pad_reject": BiometricVerdict(CaptureStatus.READY, LivenessStatus.REJECT),
            "pad_uncertain": BiometricVerdict(CaptureStatus.READY, LivenessStatus.UNCERTAIN),
            "pad_error": BiometricVerdict(CaptureStatus.READY, LivenessStatus.ERROR),
        }
        return mapping.get(scenario, mapping["pad_error"])

    def analyse_identification(self, image: bytes, content_type: str | None, scenario: str) -> BiometricVerdict:
        base_scenario = scenario if scenario in {
            "success", "no_face", "multiple_faces", "invalid_capture", "camera_error",
            "pad_reject", "pad_uncertain", "pad_error",
        } else "success"
        enrol = self.analyse_enrolment(image, content_type, base_scenario)
        if enrol.capture_status is not CaptureStatus.READY or enrol.liveness_status is not LivenessStatus.LIVE:
            return enrol
        matches = {
            "success": MatchStatus.CONFIRMED,
            "no_match": MatchStatus.NO_MATCH,
            "ambiguous_match": MatchStatus.AMBIGUOUS,
            "match_error": MatchStatus.ERROR,
        }
        return BiometricVerdict(enrol.capture_status, enrol.liveness_status, matches.get(scenario, MatchStatus.ERROR))

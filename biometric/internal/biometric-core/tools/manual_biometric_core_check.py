"""Human-gated A-J runner for the SFG Shared Biometric Core.

The runner displays a live preview and canonical statuses only. It writes no image,
template, calibration record, or ordinary score unless a future explicitly approved
mode is added; this version has no calibration mode.
"""

from __future__ import annotations

import argparse
import gc
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path


TEST_GUIDANCE = {
    "A": "Place one consenting live participant in normal kiosk position.",
    "B": "Use an empty consent-safe scene with no face visible.",
    "C": "Place two consenting participants visibly in the frame.",
    "D": "Use a consenting participant's transient reference and fresh live captures.",
    "E": "Use a consenting different participant against the protected reference.",
    "F": "Present a consented printed photo under ordinary demo conditions.",
    "G": "Where practical, replay a consented face on a phone or monitor.",
    "H": "Try one poor/invalid capture condition at a time.",
    "I": "Use a human-confirmed unavailable camera index or safely disable the device.",
    "J": "Inspect the workspace, console, logs, and Git state for sensitive leakage.",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SFG human-observation biometric-core check")
    parser.add_argument("--camera-index", type=int, help="Explicit OpenCV camera index for A-I")
    parser.add_argument("--list-cameras", action="store_true", help="Probe camera indices without loading models")
    parser.add_argument("--max-index", type=int, default=5, help="Exclusive upper bound for --list-cameras")
    parser.add_argument("--test", choices=tuple(TEST_GUIDANCE), default="A", help="Locked human matrix item")
    parser.add_argument("--yunet-model-path", type=Path)
    parser.add_argument("--sface-model-path", type=Path)
    parser.add_argument("--pad-model-dir", type=Path)
    parser.add_argument("--no-preview", action="store_true", help="Do not open a preview window")
    parser.add_argument(
        "--protected-calibration",
        action="store_true",
        help="For D/E only: show one transient cosine value; never persist it",
    )
    parser.add_argument(
        "--sface-match-threshold",
        type=float,
        default=0.363,
        help="Sample-derived provisional threshold used only for D/E observation",
    )
    return parser


def _default_paths() -> tuple[Path, Path, Path]:
    root = Path(__file__).resolve().parents[1]
    return (
        root / "models" / "face_detection_yunet_2023mar.onnx",
        root / "models" / "face_recognition_sface_2021dec.onnx",
        root / "models" / "silent_face",
    )


def list_cameras(max_index: int) -> int:
    import cv2

    print("SFG camera probe (no model load; no image saved)")
    found = False
    for index in range(max(0, max_index)):
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        try:
            if not capture.isOpened():
                continue
            found = True
            ok, frame = capture.read()
            if ok and frame is not None and getattr(frame, "ndim", 0) == 3:
                print(f"camera_index={index} status=AVAILABLE frame_geometry={frame.shape[1]}x{frame.shape[0]}")
            else:
                print(f"camera_index={index} status=OPEN_READ_FAILED")
            del frame
        finally:
            capture.release()
    if not found:
        print("camera_probe_status=NO_CAMERA_OBSERVED")
    return 0


def _safe_template_note(template) -> str:
    if template is None:
        return "template_status=NOT_GENERATED"
    return "template_status=GENERATED_TRANSIENTLY shape=(1,128) dtype=float32 bytes=512"


@dataclass(frozen=True, repr=False)
class ComparisonObservation:
    status: str
    protected_similarity: float | None = None

    def __repr__(self) -> str:
        return f"<ComparisonObservation status={self.status!r} similarity=<redacted>>"


class TransientComparison:
    """Hold one manual-test reference in memory until one fresh comparison."""

    def __init__(self) -> None:
        self._reference = None

    @property
    def has_reference(self) -> bool:
        return self._reference is not None

    def capture_reference(self, template) -> str:
        self.clear()
        self._reference = template
        return "REFERENCE_CAPTURED_TRANSIENTLY"

    def compare_fresh(self, fresh, *, compare, threshold: float) -> ComparisonObservation:
        reference = self._reference
        try:
            threshold_value = float(threshold)
            if reference is None or not math.isfinite(threshold_value):
                return ComparisonObservation("MATCH_ERROR")
            score = float(compare(reference, fresh))
            if not math.isfinite(score):
                return ComparisonObservation("MATCH_ERROR")
            status = "MATCH_CONFIRMED" if score >= threshold_value else "NO_MATCH"
            return ComparisonObservation(status, protected_similarity=score)
        except Exception:
            return ComparisonObservation("MATCH_ERROR")
        finally:
            self.clear()

    def clear(self) -> None:
        self._reference = None


def run_data_handling_audit_guidance() -> int:
    print("SFG data-handling audit — HUMAN INSPECTION REQUIRED")
    print("data_handling_audit_status=PENDING_HUMAN_INSPECTION")
    print("inspect=workspace,temp,console,logs,git_status,git_diff")
    print("must_be_absent=frames,crops,templates,PINs,participant_ids,secrets,candidates,scores")
    return 0


def run_test(args: argparse.Namespace) -> int:
    if args.test == "J":
        return run_data_handling_audit_guidance()
    if args.camera_index is None:
        print("activation_error=CAMERA_INDEX_REQUIRED")
        return 2
    if args.protected_calibration and args.test not in {"D", "E"}:
        print("activation_error=PROTECTED_CALIBRATION_ONLY_FOR_D_OR_E")
        return 2
    if args.test in {"D", "E"} and args.no_preview:
        print("activation_error=D_E_REQUIRE_PREVIEW_KEYS_R_AND_F")
        return 2

    import cv2

    from sfg_biometric_core import BiometricCorePipeline
    from sfg_biometric_core.sface import SFaceEngine
    from sfg_biometric_core.silent_face_pad import SilentFacePAD
    from sfg_biometric_core.yunet import YuNetDetector

    default_yunet, default_sface, default_pad = _default_paths()
    yunet_path = args.yunet_model_path or default_yunet
    sface_path = args.sface_model_path or default_sface
    pad_dir = args.pad_model_dir or default_pad

    print("SFG Shared Biometric Core manual check")
    calibration = "protected_transient" if args.protected_calibration else "false"
    print(f"mode=HUMAN_OBSERVATION save_images=false save_templates=false calibration={calibration}")
    print(f"test={args.test} camera_index={args.camera_index}")
    print(f"guidance={TEST_GUIDANCE[args.test]}")
    print("Press q or Escape to stop; only canonical statuses and safe representation metadata are shown.")
    if args.test in {"D", "E"}:
        print("comparison_controls=press_r_for_reference_then_reposition_or_change_person_then_press_f_for_fresh")
        print("comparison_storage=TRANSIENT_MEMORY_ONLY")

    try:
        detector = YuNetDetector.from_model_path(yunet_path)
        pad = SilentFacePAD.from_model_dir(pad_dir)
        sface = SFaceEngine.from_model_path(sface_path)
    except Exception as exc:
        code = getattr(exc, "code", "MODEL_NOT_READY")
        print(f"startup_status=MODEL_ERROR diagnostic_code={code}")
        return 2

    print(f"manifest_fingerprint={sface.fingerprint.fingerprint_id()}")

    capture = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        print("capture_status=CAMERA_ERROR")
        return 2

    core = BiometricCorePipeline(detector=detector, pad=pad, sface=sface)
    comparison = TransientComparison() if args.test in {"D", "E"} else None
    last_status = None
    started = time.perf_counter()
    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("capture_status=CAMERA_ERROR")
                break
            result = core.process_frame(frame)
            status = (result.capture_status, result.liveness_status, result.diagnostic_code, result.template is not None)
            if status != last_status:
                print(
                    f"capture_status={result.capture_status} "
                    f"liveness_status={result.liveness_status or 'NOT_REACHED'} "
                    f"frame_geometry={frame.shape[1]}x{frame.shape[0]} "
                    f"duration_ms={int((time.perf_counter() - started) * 1000)} "
                    f"{_safe_template_note(result.template)}"
                )
                if result.diagnostic_code:
                    print(f"diagnostic_code={result.diagnostic_code}")
                last_status = status
            if not args.no_preview:
                preview = frame.copy()
                cv2.putText(preview, result.capture_status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)
                if result.liveness_status:
                    cv2.putText(preview, result.liveness_status, (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)
                cv2.imshow("SFG Shared Biometric Core - HUMAN OBSERVATION", preview)
                key = cv2.waitKey(1) & 0xFF
                del preview
                if key in (ord("q"), 27):
                    break
                if comparison is not None and key == ord("r"):
                    if result.template is None:
                        print("reference_status=NOT_CAPTURED_REQUIRE_PAD_LIVE_TEMPLATE")
                    else:
                        print(f"reference_status={comparison.capture_reference(result.template)}")
                        print("next_action=change_natural_pose_for_D_or_switch_to_consenting_person_B_for_E_then_press_f")
                if comparison is not None and key == ord("f"):
                    if result.template is None:
                        print("fresh_status=NOT_CAPTURED_REQUIRE_PAD_LIVE_TEMPLATE")
                    else:
                        observation = comparison.compare_fresh(
                            result.template,
                            compare=sface.compare,
                            threshold=args.sface_match_threshold,
                        )
                        print(f"match_status={observation.status}")
                        if args.protected_calibration and observation.protected_similarity is not None:
                            print("protected_calibration_warning=TRANSIENT_DO_NOT_COPY_TO_PUBLIC_LOGS")
                            print(f"protected_similarity={observation.protected_similarity:.8f}")
                        print("comparison_reference_status=CLEARED")
                        del observation
                        break
            del result, frame
            gc.collect()
            time.sleep(0.02)
    finally:
        capture.release()
        if not args.no_preview:
            cv2.destroyAllWindows()
        del core, detector, pad, sface
        if comparison is not None:
            comparison.clear()
            del comparison
        gc.collect()
    print("manual_runner_status=STOPPED_NO_EVIDENCE_CLAIM")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_cameras:
        return list_cameras(args.max_index)
    return run_test(args)


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


RUNNER_PATH = Path(__file__).resolve().parents[1] / "tools" / "manual_biometric_core_check.py"
SPEC = importlib.util.spec_from_file_location("manual_biometric_core_check", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def test_transient_comparison_keeps_reference_only_in_memory_and_classifies_fresh() -> None:
    reference = object()
    fresh = object()
    comparison = RUNNER.TransientComparison()

    assert comparison.capture_reference(reference) == "REFERENCE_CAPTURED_TRANSIENTLY"
    outcome = comparison.compare_fresh(fresh, compare=lambda stored, probe: 0.8, threshold=0.363)

    assert outcome.status == "MATCH_CONFIRMED"
    assert outcome.protected_similarity == 0.8
    assert comparison.has_reference is False
    assert "0.8" not in repr(outcome)


def test_transient_comparison_requires_reference_and_fails_closed_on_bad_score() -> None:
    comparison = RUNNER.TransientComparison()
    missing = comparison.compare_fresh(object(), compare=lambda *_: 0.8, threshold=0.363)
    assert missing.status == "MATCH_ERROR"

    comparison.capture_reference(object())
    failed = comparison.compare_fresh(object(), compare=lambda *_: float("nan"), threshold=0.363)
    assert failed.status == "MATCH_ERROR"
    assert comparison.has_reference is False


def test_j_data_handling_check_does_not_require_camera_or_models(capsys) -> None:
    result = RUNNER.main(["--test", "J"])
    output = capsys.readouterr().out

    assert result == 0
    assert "data_handling_audit_status=PENDING_HUMAN_INSPECTION" in output
    assert "CAMERA_INDEX_REQUIRED" not in output

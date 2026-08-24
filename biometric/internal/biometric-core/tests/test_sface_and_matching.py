from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pytest

from sfg_biometric_core import (
    AMBIGUOUS_MATCH,
    MATCH_CONFIRMED,
    MATCH_ERROR,
    NO_MATCH,
)
from sfg_biometric_core.compatibility import (
    AssetSpec,
    CompatibilityFingerprint,
    ModelManifest,
)
from sfg_biometric_core.sface import (
    MatchOutcome,
    SFaceEngine,
    SFaceLoadError,
    SFaceTemplate,
    TemplateCandidate,
    TemplateError,
    deserialize_protected_template,
    deserialize_template,
    match_1_to_n,
    serialize_protected_template,
    serialize_template,
)
from sfg_biometric_core.yunet import FaceDetection


FP = CompatibilityFingerprint.for_test()


def _face() -> FaceDetection:
    return FaceDetection(
        box=(1.0, 1.0, 6.0, 6.0),
        landmarks=np.asarray(
            [[2.0, 3.0], [6.0, 3.0], [4.0, 4.0], [2.5, 6.0], [5.5, 6.0]],
            dtype=np.float32,
        ),
        confidence=0.99,
    )


def _template(seed: float = 1.0) -> SFaceTemplate:
    values = (np.arange(128, dtype=np.float32) + np.float32(seed)).reshape(1, 128)
    return SFaceTemplate.from_array(values, fingerprint=FP)


class RecognizerStub:
    def __init__(self, output):
        self.output = output
        self.rows: list[np.ndarray] = []

    def alignCrop(self, frame, row):
        self.rows.append(np.asarray(row).copy())
        return np.zeros((112, 112, 3), dtype=np.uint8)

    def feature(self, aligned):
        return self.output

    def match(self, reference, fresh, metric):
        return np.float32(0.88)


def test_sface_align_feature_validates_finite_float32_128_template() -> None:
    recognizer = RecognizerStub(np.arange(128, dtype=np.float32).reshape(1, 128))
    engine = SFaceEngine(recognizer=recognizer, fingerprint=FP)

    template = engine.template_from_detection(np.zeros((8, 8, 3), np.uint8), _face())

    assert template.shape == (1, 128)
    assert template.dtype == np.dtype(np.float32)
    assert template.is_finite
    assert recognizer.rows[0].shape == (15,)


@pytest.mark.parametrize(
    "output",
    [
        np.zeros((128,), dtype=np.float32),
        np.zeros((1, 127), dtype=np.float32),
        np.full((1, 128), np.nan, dtype=np.float32),
        np.zeros((1, 128), dtype=np.float64),
    ],
)
def test_sface_rejects_malformed_feature(output) -> None:
    engine = SFaceEngine(recognizer=RecognizerStub(output), fingerprint=FP)
    expected = "SFACE_TEMPLATE_NONFINITE" if np.isnan(output).any() else "SFACE_TEMPLATE_INVALID"
    with pytest.raises(TemplateError, match=expected):
        engine.template_from_detection(np.zeros((8, 8, 3), np.uint8), _face())


def test_sface_loader_validates_model_before_load(tmp_path: Path) -> None:
    payload = b"sface"
    spec = AssetSpec(
        filename="sface.onnx",
        byte_size=len(payload),
        sha256="954a0b0a5e6f746f1904f4f7d0f1cf6e0c7e07f53a5ec3b6259b0aeb2c9b6d49",
        source_revision="test",
        source_url="https://example.invalid",
    )
    # Use the actual digest so the test isolates the loader exception.
    import hashlib

    spec = AssetSpec("sface.onnx", len(payload), hashlib.sha256(payload).hexdigest(), "test", "https://example.invalid")
    model_path = tmp_path / "sface.onnx"
    model_path.write_bytes(payload)

    class BadCV2:
        class FaceRecognizerSF:
            @staticmethod
            def create(*args):
                raise RuntimeError("loader internals")

        class dnn:
            DNN_BACKEND_OPENCV = 3
            DNN_TARGET_CPU = 0

    manifest = ModelManifest(
        yunet=spec,
        sface=spec,
        pad_models={},
    )
    with pytest.raises(SFaceLoadError, match="SFACE_LOAD_FAILED"):
        SFaceEngine.from_model_path(model_path, manifest=manifest, cv2_module=BadCV2)


def test_template_serialization_is_little_endian_512_bytes_and_round_trips() -> None:
    template = _template()
    payload = serialize_template(template)

    assert isinstance(payload, bytes)
    assert len(payload) == 512
    assert payload == np.asarray(template.to_numpy(), dtype="<f4").tobytes(order="C")
    restored = deserialize_template(payload, fingerprint=FP)
    np.testing.assert_array_equal(restored.to_numpy(), template.to_numpy())


def test_protected_base64_envelope_round_trip_and_corruption_rejection() -> None:
    template = _template(2.0)
    envelope = serialize_protected_template(template)
    assert isinstance(envelope.payload_base64, str)
    assert base64.b64decode(envelope.payload_base64) == serialize_template(template)
    assert "1.0" not in repr(envelope)

    restored = deserialize_protected_template(envelope, expected_fingerprint=FP)
    np.testing.assert_array_equal(restored.to_numpy(), template.to_numpy())

    corrupted = type(envelope)(payload_base64=base64.b64encode(b"bad").decode(), fingerprint=FP)
    with pytest.raises(TemplateError, match="SFACE_TEMPLATE_SERIALIZATION_INVALID"):
        deserialize_protected_template(corrupted, expected_fingerprint=FP)

    with pytest.raises(TemplateError, match="SFACE_TEMPLATE_NONFINITE"):
        deserialize_template(np.full((128,), np.nan, dtype="<f4").tobytes(), fingerprint=FP)


def test_sface_compare_uses_cosine_metric() -> None:
    recognizer = RecognizerStub(np.zeros((1, 128), dtype=np.float32))
    engine = SFaceEngine(recognizer=recognizer, fingerprint=FP)
    assert engine.compare(_template(), _template(2.0)) == pytest.approx(0.88)


@pytest.mark.parametrize(
    ("scores", "status"),
    [
        ([], NO_MATCH),
        ([0.8], MATCH_CONFIRMED),
        ([0.8, 0.9], AMBIGUOUS_MATCH),
    ],
)
def test_safe_linear_match_mapping_hides_candidates_scores_and_counts(scores, status) -> None:
    fresh = _template()
    candidates = [TemplateCandidate(candidate_token=f"candidate-{i}", template=_template(i + 2), fingerprint=FP) for i in range(len(scores))]
    score_iterator = iter(scores)
    result = match_1_to_n(
        fresh,
        candidates,
        threshold=0.363,
        compare=lambda reference, probe: next(score_iterator),
    )

    assert result.status == status
    text = repr(result)
    assert "candidate-" not in text
    assert "0.8" not in text and "0.9" not in text
    assert "count" not in text.lower()


def test_unique_match_retains_opaque_token_only_for_trusted_backend() -> None:
    result = match_1_to_n(
        _template(),
        [TemplateCandidate(candidate_token="private-account-token", template=_template(2.0), fingerprint=FP)],
        threshold=0.363,
        compare=lambda *_: 0.8,
    )

    assert result.status == MATCH_CONFIRMED
    assert result.matched_candidate_token_for_trusted_backend() == "private-account-token"
    safe = result.to_safe_outcome()
    assert safe.status == MATCH_CONFIRMED
    assert safe.matched_candidate_token_for_trusted_backend() is None
    assert "private-account-token" not in repr(result)
    assert "private-account-token" not in repr(safe)
    with pytest.raises(AttributeError):
        result.status = NO_MATCH


def test_match_rejects_compatibility_before_comparison_and_numeric_failures() -> None:
    bad_fingerprint = FP.with_change("metric", "L2")
    candidate = TemplateCandidate(candidate_token="private-id", template=_template(), fingerprint=bad_fingerprint)
    called = False

    def compare(*args):
        nonlocal called
        called = True
        return 1.0

    mismatch = match_1_to_n(_template(), [candidate], threshold=0.363, compare=compare, expected_fingerprint=FP)
    assert mismatch.status == MATCH_ERROR
    assert called is False
    assert "private-id" not in repr(mismatch)

    error = match_1_to_n(
        _template(),
        [TemplateCandidate(candidate_token="private-id", template=_template(), fingerprint=FP)],
        threshold=0.363,
        compare=lambda *_: float("nan"),
    )
    assert error.status == MATCH_ERROR

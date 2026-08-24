from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from sfg_biometric_core import PAD_ERROR, PAD_LIVE, PAD_REJECT, PAD_UNCERTAIN
from sfg_biometric_core.silent_face_pad import (
    ModelLoadError,
    PADResult,
    SilentFacePAD,
    load_allowlisted_state_dict,
)
from sfg_biometric_core.yunet import FaceDetection


def _face() -> FaceDetection:
    return FaceDetection(
        box=(8.0, 8.0, 8.0, 8.0),
        landmarks=np.asarray(
            [[9.0, 10.0], [15.0, 10.0], [12.0, 12.0], [10.0, 15.0], [14.0, 15.0]],
            dtype=np.float32,
        ),
        confidence=0.99,
    )


class LogitModel:
    def __init__(self, logits):
        self.logits = np.asarray(logits, dtype=np.float32)
        self.inputs: list[torch.Tensor] = []

    def __call__(self, tensor):
        self.inputs.append(tensor.detach().cpu())
        return torch.from_numpy(self.logits.copy())


def _pad(model_one, model_two, *, crop_fn=None) -> SilentFacePAD:
    return SilentFacePAD(
        models=(model_one, model_two),
        crop_fn=crop_fn,
    )


def test_pad_live_requires_both_models_and_unique_ensemble_class_one() -> None:
    first = LogitModel([[0.0, 6.0, 0.0]])
    second = LogitModel([[0.0, 5.0, 0.0]])
    frame = np.full((32, 32, 3), 255, dtype=np.uint8)

    result = _pad(first, second).assess(frame, _face())

    assert result.status == PAD_LIVE
    assert first.inputs[0].shape == (1, 3, 80, 80)
    assert first.inputs[0].dtype == torch.float32
    assert float(first.inputs[0].max()) == 255.0


def test_pad_attack_agreement_maps_to_reject() -> None:
    result = _pad(LogitModel([[6.0, 0.0, 0.0]]), LogitModel([[5.0, 0.0, 0.0]])).assess(
        np.zeros((32, 32, 3), np.uint8), _face()
    )
    assert result.status == PAD_REJECT


def test_pad_disagreement_and_tie_map_to_uncertain() -> None:
    disagreement = _pad(LogitModel([[0.0, 6.0, 0.0]]), LogitModel([[6.0, 0.0, 0.0]])).assess(
        np.zeros((32, 32, 3), np.uint8), _face()
    )
    tie = _pad(LogitModel([[6.0, 0.0, 0.0]]), LogitModel([[0.0, 0.0, 6.0]])).assess(
        np.zeros((32, 32, 3), np.uint8), _face()
    )
    assert disagreement.status == PAD_UNCERTAIN
    assert tie.status == PAD_UNCERTAIN


@pytest.mark.parametrize(
    "model_pair",
    [
        (LogitModel([[np.nan, 0.0, 0.0]]), LogitModel([[0.0, 1.0, 0.0]])),
        (LogitModel([[0.0, 1.0]]), LogitModel([[0.0, 1.0, 0.0]])),
    ],
)
def test_pad_invalid_numeric_or_shape_maps_to_error(model_pair) -> None:
    result = _pad(*model_pair).assess(np.zeros((32, 32, 3), np.uint8), _face())
    assert result.status == PAD_ERROR
    assert "nan" not in repr(result).lower()


def test_pad_crop_or_inference_failure_maps_to_error() -> None:
    def failing_crop(*args, **kwargs):
        raise RuntimeError("crop internals")

    crop_error = _pad(LogitModel([[0.0, 1.0, 0.0]]), LogitModel([[0.0, 1.0, 0.0]]), crop_fn=failing_crop).assess(
        np.zeros((32, 32, 3), np.uint8), _face()
    )

    class RaisingModel(LogitModel):
        def __call__(self, tensor):
            raise RuntimeError("inference internals")

    inference_error = _pad(RaisingModel([[0.0, 1.0, 0.0]]), LogitModel([[0.0, 1.0, 0.0]])).assess(
        np.zeros((32, 32, 3), np.uint8), _face()
    )
    assert crop_error.status == PAD_ERROR
    assert inference_error.status == PAD_ERROR


def test_weights_only_loader_never_falls_back_to_unsafe_pickle(tmp_path: Path) -> None:
    calls = []

    class FakeTorch:
        @staticmethod
        def load(*args, **kwargs):
            calls.append((args, kwargs))
            raise TypeError("weights_only unsupported")

    with pytest.raises(ModelLoadError, match="PAD_WEIGHTS_ONLY_UNSUPPORTED"):
        load_allowlisted_state_dict(tmp_path / "allowlisted.pth", torch_module=FakeTorch)

    assert len(calls) == 1
    assert calls[0][1] == {"map_location": "cpu", "weights_only": True}


def test_pad_result_repr_is_safe() -> None:
    result = PADResult(status=PAD_LIVE)
    assert repr(result) == "<PADResult status='PAD_LIVE'>"
    assert "prob" not in repr(result)

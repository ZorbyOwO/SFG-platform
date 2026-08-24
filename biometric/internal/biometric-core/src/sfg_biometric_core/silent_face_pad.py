"""Pinned MiniFASNet Silent Face PAD wrapper.

The network definitions below are a minimal adaptation of Minivision's
``src/model_lib/MiniFASNet.py`` at commit
``b6d5f04ad78778917853b25c778acef6d5626d15``.  The adaptation removes the
upstream detector/file-loop and keeps only the two allowlisted CPU inference
models required by the SFG pipeline.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
import torch.nn.functional as F
from torch.nn import (
    AdaptiveAvgPool2d,
    BatchNorm1d,
    BatchNorm2d,
    Conv2d,
    Dropout,
    Linear,
    Module,
    PReLU,
    ReLU,
    Sequential,
    Sigmoid,
)

from .compatibility import ModelManifest, validate_asset_path
from .yunet import FaceDetection, validate_frame


class _Flatten(Module):
    def forward(self, value):
        return value.view(value.size(0), -1)


class _ConvBlock(Module):
    def __init__(self, in_channels, out_channels, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super().__init__()
        self.conv = Conv2d(
            in_channels,
            out_channels,
            kernel_size=kernel,
            groups=groups,
            stride=stride,
            padding=padding,
            bias=False,
        )
        self.bn = BatchNorm2d(out_channels)
        self.prelu = PReLU(out_channels)

    def forward(self, value):
        return self.prelu(self.bn(self.conv(value)))


class _LinearBlock(Module):
    def __init__(self, in_channels, out_channels, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super().__init__()
        self.conv = Conv2d(
            in_channels,
            out_channels,
            kernel_size=kernel,
            groups=groups,
            stride=stride,
            padding=padding,
            bias=False,
        )
        self.bn = BatchNorm2d(out_channels)

    def forward(self, value):
        return self.bn(self.conv(value))


class _DepthWise(Module):
    def __init__(self, c1, c2, c3, residual=False, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=1):
        super().__init__()
        c1_in, c1_out = c1
        c2_in, c2_out = c2
        c3_in, c3_out = c3
        self.conv = _ConvBlock(c1_in, c1_out, kernel=(1, 1), stride=(1, 1), padding=(0, 0))
        self.conv_dw = _ConvBlock(c2_in, c2_out, groups=c2_in, kernel=kernel, padding=padding, stride=stride)
        self.project = _LinearBlock(c3_in, c3_out, kernel=(1, 1), stride=(1, 1), padding=(0, 0))
        self.residual = residual

    def forward(self, value):
        shortcut = value
        value = self.project(self.conv_dw(self.conv(value)))
        return shortcut + value if self.residual else value


class _Residual(Module):
    def __init__(self, c1, c2, c3, num_block, groups, kernel=(3, 3), stride=(1, 1), padding=(1, 1)):
        super().__init__()
        self.model = Sequential(
            *[
                _DepthWise(
                    c1[index],
                    c2[index],
                    c3[index],
                    residual=True,
                    kernel=kernel,
                    padding=padding,
                    stride=stride,
                    groups=groups,
                )
                for index in range(num_block)
            ]
        )

    def forward(self, value):
        return self.model(value)


class _SEModule(Module):
    def __init__(self, channels, reduction):
        super().__init__()
        self.avg_pool = AdaptiveAvgPool2d(1)
        self.fc1 = Conv2d(channels, channels // reduction, kernel_size=1, padding=0, bias=False)
        self.bn1 = BatchNorm2d(channels // reduction)
        self.relu = ReLU(inplace=True)
        self.fc2 = Conv2d(channels // reduction, channels, kernel_size=1, padding=0, bias=False)
        self.bn2 = BatchNorm2d(channels)
        self.sigmoid = Sigmoid()

    def forward(self, value):
        scale = self.avg_pool(value)
        scale = self.relu(self.bn1(self.fc1(scale)))
        scale = self.sigmoid(self.bn2(self.fc2(scale)))
        return value * scale


class _DepthWiseSE(_DepthWise):
    def __init__(self, c1, c2, c3, residual=False, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=1, se_reduct=8):
        super().__init__(c1, c2, c3, residual, kernel, stride, padding, groups)
        _, c3_out = c3
        self.se_module = _SEModule(c3_out, se_reduct)

    def forward(self, value):
        shortcut = value
        value = self.project(self.conv_dw(self.conv(value)))
        if self.residual:
            value = self.se_module(value)
            return shortcut + value
        return value


class _ResidualSE(Module):
    def __init__(self, c1, c2, c3, num_block, groups, kernel=(3, 3), stride=(1, 1), padding=(1, 1), se_reduct=4):
        super().__init__()
        modules = []
        for index in range(num_block):
            block = _DepthWiseSE if index == num_block - 1 else _DepthWise
            kwargs = {"residual": True, "kernel": kernel, "padding": padding, "stride": stride, "groups": groups}
            if block is _DepthWiseSE:
                kwargs["se_reduct"] = se_reduct
            modules.append(block(c1[index], c2[index], c3[index], **kwargs))
        self.model = Sequential(*modules)

    def forward(self, value):
        return self.model(value)


_KEEP_V1 = [
    32, 32, 103, 103, 64, 13, 13, 64, 26, 26, 64, 13, 13, 64, 52, 52,
    64, 231, 231, 128, 154, 154, 128, 52, 52, 128, 26, 26, 128, 52, 52,
    128, 26, 26, 128, 26, 26, 128, 308, 308, 128, 26, 26, 128, 26, 26,
    128, 512, 512,
]
_KEEP_V2 = [
    32, 32, 103, 103, 64, 13, 13, 64, 13, 13, 64, 13, 13, 64, 13, 13,
    64, 231, 231, 128, 231, 231, 128, 52, 52, 128, 26, 26, 128, 77, 77,
    128, 26, 26, 128, 26, 26, 128, 308, 308, 128, 26, 26, 128, 26, 26,
    128, 512, 512,
]


class _MiniFASNet(Module):
    def __init__(self, keep, embedding_size=128, conv6_kernel=(5, 5), drop_p=0.0, num_classes=3, img_channel=3):
        super().__init__()
        self.embedding_size = embedding_size
        self.conv1 = _ConvBlock(img_channel, keep[0], kernel=(3, 3), stride=(2, 2), padding=(1, 1))
        self.conv2_dw = _ConvBlock(keep[0], keep[1], kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=keep[1])
        self.conv_23 = _DepthWise(
            (keep[1], keep[2]), (keep[2], keep[3]), (keep[3], keep[4]),
            kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=keep[3],
        )
        c1 = [(keep[4], keep[5]), (keep[7], keep[8]), (keep[10], keep[11]), (keep[13], keep[14])]
        c2 = [(keep[5], keep[6]), (keep[8], keep[9]), (keep[11], keep[12]), (keep[14], keep[15])]
        c3 = [(keep[6], keep[7]), (keep[9], keep[10]), (keep[12], keep[13]), (keep[15], keep[16])]
        self.conv_3 = _Residual(c1, c2, c3, 4, keep[4])
        self.conv_34 = _DepthWise(
            (keep[16], keep[17]), (keep[17], keep[18]), (keep[18], keep[19]),
            kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=keep[19],
        )
        c1 = [(keep[19], keep[20]), (keep[22], keep[23]), (keep[25], keep[26]), (keep[28], keep[29]), (keep[31], keep[32]), (keep[34], keep[35])]
        c2 = [(keep[20], keep[21]), (keep[23], keep[24]), (keep[26], keep[27]), (keep[29], keep[30]), (keep[32], keep[33]), (keep[35], keep[36])]
        c3 = [(keep[21], keep[22]), (keep[24], keep[25]), (keep[27], keep[28]), (keep[30], keep[31]), (keep[33], keep[34]), (keep[36], keep[37])]
        self.conv_4 = _Residual(c1, c2, c3, 6, keep[19])
        self.conv_45 = _DepthWise(
            (keep[37], keep[38]), (keep[38], keep[39]), (keep[39], keep[40]),
            kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=keep[40],
        )
        c1 = [(keep[40], keep[41]), (keep[43], keep[44])]
        c2 = [(keep[41], keep[42]), (keep[44], keep[45])]
        c3 = [(keep[42], keep[43]), (keep[45], keep[46])]
        self.conv_5 = _Residual(c1, c2, c3, 2, keep[40])
        self.conv_6_sep = _ConvBlock(keep[46], keep[47], kernel=(1, 1), stride=(1, 1), padding=(0, 0))
        self.conv_6_dw = _LinearBlock(keep[47], keep[48], groups=keep[48], kernel=conv6_kernel, stride=(1, 1), padding=(0, 0))
        self.conv_6_flatten = _Flatten()
        self.linear = Linear(512, embedding_size, bias=False)
        self.bn = BatchNorm1d(embedding_size)
        self.drop = Dropout(p=drop_p)
        self.prob = Linear(embedding_size, num_classes, bias=False)

    def forward(self, value):
        value = self.conv_6_dw(
            self.conv_6_sep(
                self.conv_5(
                    self.conv_45(
                        self.conv_4(
                            self.conv_34(
                                self.conv_3(self.conv_23(self.conv2_dw(self.conv1(value))))
                            )
                        )
                    )
                )
            )
        )
        value = self.conv_6_flatten(value)
        if self.embedding_size != 512:
            value = self.linear(value)
        value = self.bn(value)
        value = self.drop(value)
        return self.prob(value)


class _MiniFASNetSE(_MiniFASNet):
    def __init__(self, keep, embedding_size=128, conv6_kernel=(5, 5), drop_p=0.75, num_classes=3, img_channel=3):
        super().__init__(keep, embedding_size, conv6_kernel, drop_p, num_classes, img_channel)
        c1 = [(keep[4], keep[5]), (keep[7], keep[8]), (keep[10], keep[11]), (keep[13], keep[14])]
        c2 = [(keep[5], keep[6]), (keep[8], keep[9]), (keep[11], keep[12]), (keep[14], keep[15])]
        c3 = [(keep[6], keep[7]), (keep[9], keep[10]), (keep[12], keep[13]), (keep[15], keep[16])]
        self.conv_3 = _ResidualSE(c1, c2, c3, 4, keep[4])
        c1 = [(keep[19], keep[20]), (keep[22], keep[23]), (keep[25], keep[26]), (keep[28], keep[29]), (keep[31], keep[32]), (keep[34], keep[35])]
        c2 = [(keep[20], keep[21]), (keep[23], keep[24]), (keep[26], keep[27]), (keep[29], keep[30]), (keep[32], keep[33]), (keep[35], keep[36])]
        c3 = [(keep[21], keep[22]), (keep[24], keep[25]), (keep[27], keep[28]), (keep[30], keep[31]), (keep[33], keep[34]), (keep[36], keep[37])]
        self.conv_4 = _ResidualSE(c1, c2, c3, 6, keep[19])
        c1 = [(keep[40], keep[41]), (keep[43], keep[44])]
        c2 = [(keep[41], keep[42]), (keep[44], keep[45])]
        c3 = [(keep[42], keep[43]), (keep[45], keep[46])]
        self.conv_5 = _ResidualSE(c1, c2, c3, 2, keep[40])


def _mini_fas_v2():
    return _MiniFASNet(_KEEP_V2, conv6_kernel=(5, 5), drop_p=0.2, num_classes=3)


def _mini_fas_v1_se():
    return _MiniFASNetSE(_KEEP_V1, conv6_kernel=(5, 5), drop_p=0.75, num_classes=3)


class ModelLoadError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def load_allowlisted_state_dict(path: str | Path, *, torch_module: Any = torch) -> Mapping[str, Any]:
    """Load only an allowlisted weights file using PyTorch safe mode."""

    try:
        state_dict = torch_module.load(str(path), map_location="cpu", weights_only=True)
    except TypeError:
        raise ModelLoadError("PAD_WEIGHTS_ONLY_UNSUPPORTED") from None
    except Exception:
        raise ModelLoadError("PAD_WEIGHTS_LOAD_FAILED") from None
    if not isinstance(state_dict, Mapping):
        raise ModelLoadError("PAD_STATE_DICT_INVALID")
    if not state_dict:
        raise ModelLoadError("PAD_STATE_DICT_EMPTY")
    if all(isinstance(key, str) for key in state_dict):
        if all(key.startswith("module.") for key in state_dict):
            return {key[7:]: value for key, value in state_dict.items()}
        if any(key.startswith("module.") for key in state_dict):
            raise ModelLoadError("PAD_STATE_DICT_INVALID")
        return state_dict
    raise ModelLoadError("PAD_STATE_DICT_INVALID")


def _crop_and_resize(frame: np.ndarray, box: tuple[float, float, float, float], scale: float) -> np.ndarray:
    import cv2

    x, y, width, height = box
    center_x = x + width / 2.0
    center_y = y + height / 2.0
    crop_width = max(1.0, width * scale)
    crop_height = max(1.0, height * scale)
    left = max(0, int(math.floor(center_x - crop_width / 2.0)))
    top = max(0, int(math.floor(center_y - crop_height / 2.0)))
    right = min(frame.shape[1], int(math.ceil(center_x + crop_width / 2.0)))
    bottom = min(frame.shape[0], int(math.ceil(center_y + crop_height / 2.0)))
    if right <= left or bottom <= top:
        raise ValueError("PAD_CROP_EMPTY")
    crop = frame[top:bottom, left:right]
    if crop.size == 0:
        raise ValueError("PAD_CROP_EMPTY")
    resized = cv2.resize(crop, (80, 80), interpolation=cv2.INTER_LINEAR)
    if resized.shape != (80, 80, 3) or resized.dtype != np.uint8:
        raise ValueError("PAD_CROP_INVALID")
    return np.ascontiguousarray(resized)


def _scale_from_filename(filename: str) -> float:
    prefix = filename.split("_", 1)[0]
    try:
        scale = float(prefix)
    except ValueError:
        raise ModelLoadError("PAD_SCALE_UNPARSEABLE") from None
    if not np.isfinite(scale) or scale <= 0:
        raise ModelLoadError("PAD_SCALE_INVALID")
    return scale


def _preprocess(crop: np.ndarray, *, torch_module: Any = torch):
    if crop.shape != (80, 80, 3) or crop.dtype != np.uint8:
        raise ValueError("PAD_CROP_INVALID")
    chw = np.ascontiguousarray(crop.transpose(2, 0, 1), dtype=np.float32)
    return torch_module.from_numpy(chw).unsqueeze(0)


@dataclass(frozen=True, repr=False)
class PADResult:
    status: str
    diagnostic_code: str | None = None

    def __repr__(self) -> str:
        return f"<PADResult status={self.status!r}>"


class SilentFacePAD:
    def __init__(
        self,
        *,
        models: tuple[Any, Any],
        crop_fn: Callable[..., np.ndarray] | None = None,
        torch_module: Any = torch,
        scales: tuple[float, float] = (2.7, 4.0),
    ) -> None:
        self._models = models
        self._crop_fn = crop_fn or _crop_and_resize
        self._torch = torch_module
        self._scales = scales
        for model in self._models:
            if hasattr(model, "eval"):
                model.eval()

    @classmethod
    def from_model_dir(
        cls,
        model_dir: str | Path,
        *,
        manifest: ModelManifest | None = None,
        torch_module: Any = torch,
    ) -> "SilentFacePAD":
        selected = manifest or ModelManifest.default()
        model_dir_path = Path(model_dir)
        if not model_dir_path.exists() or not model_dir_path.is_dir():
            raise ModelLoadError("PAD_MODEL_DIR_INVALID")
        names = set(selected.pad_models)
        try:
            files = {entry.name for entry in model_dir_path.iterdir() if entry.is_file()}
        except OSError:
            raise ModelLoadError("PAD_MODEL_DIR_UNREADABLE") from None
        if files != names:
            raise ModelLoadError("PAD_ASSET_ALLOWLIST_MISMATCH")
        for name, spec in selected.pad_models.items():
            validation = validate_asset_path(model_dir_path / name, spec)
            if not validation.ok:
                raise ModelLoadError(validation.code)
        try:
            state_one = load_allowlisted_state_dict(model_dir_path / "2.7_80x80_MiniFASNetV2.pth", torch_module=torch_module)
            state_two = load_allowlisted_state_dict(model_dir_path / "4_0_0_80x80_MiniFASNetV1SE.pth", torch_module=torch_module)
            model_one = _mini_fas_v2()
            model_two = _mini_fas_v1_se()
            model_one.load_state_dict(state_one, strict=True)
            model_two.load_state_dict(state_two, strict=True)
            model_one.eval()
            model_two.eval()
        except ModelLoadError:
            raise
        except Exception:
            raise ModelLoadError("PAD_MODEL_LOAD_FAILED") from None
        scales = (_scale_from_filename("2.7_80x80_MiniFASNetV2.pth"), _scale_from_filename("4_0_0_80x80_MiniFASNetV1SE.pth"))
        return cls(models=(model_one, model_two), torch_module=torch_module, scales=scales)

    def _predict(self, model: Any, tensor: Any) -> np.ndarray:
        with self._torch.no_grad():
            output = model(tensor)
            if not self._torch.is_tensor(output):
                output = self._torch.as_tensor(output)
            if tuple(output.shape) != (1, 3):
                raise ValueError("PAD_OUTPUT_SHAPE")
            if not bool(self._torch.isfinite(output).all().item()):
                raise ValueError("PAD_OUTPUT_NONFINITE")
            probabilities = self._torch.softmax(output, dim=1)
            probabilities = probabilities.detach().cpu().numpy()
        if probabilities.shape != (1, 3) or not np.all(np.isfinite(probabilities)):
            raise ValueError("PAD_OUTPUT_INVALID")
        return probabilities[0].astype(np.float64, copy=False)

    @staticmethod
    def _unique_argmax(probabilities: np.ndarray) -> int | None:
        maximum = float(np.max(probabilities))
        winners = np.flatnonzero(np.isclose(probabilities, maximum, rtol=0.0, atol=1e-6))
        return int(winners[0]) if winners.size == 1 else None

    def assess(self, frame: Any, face: FaceDetection) -> PADResult:
        if not validate_frame(frame).ok:
            return PADResult("PAD_ERROR", "PAD_FRAME_INVALID")
        try:
            crop_one = self._crop_fn(frame, face.box, self._scales[0])
            crop_two = self._crop_fn(frame, face.box, self._scales[1])
            tensor_one = _preprocess(crop_one, torch_module=self._torch)
            tensor_two = _preprocess(crop_two, torch_module=self._torch)
            probabilities_one = self._predict(self._models[0], tensor_one)
            probabilities_two = self._predict(self._models[1], tensor_two)
            ensemble = (probabilities_one + probabilities_two) / 2.0
            if not np.all(np.isfinite(ensemble)):
                raise ValueError("PAD_ENSEMBLE_NONFINITE")
            choice_one = self._unique_argmax(probabilities_one)
            choice_two = self._unique_argmax(probabilities_two)
            choice_ensemble = self._unique_argmax(ensemble)
        except Exception:
            return PADResult("PAD_ERROR", "PAD_INFERENCE_FAILURE")

        if choice_one == choice_two == choice_ensemble == 1:
            return PADResult("PAD_LIVE")
        if choice_one in (0, 2) and choice_two in (0, 2) and choice_ensemble in (0, 2):
            return PADResult("PAD_REJECT")
        return PADResult("PAD_UNCERTAIN")


__all__ = [
    "ModelLoadError",
    "PADResult",
    "SilentFacePAD",
    "load_allowlisted_state_dict",
]

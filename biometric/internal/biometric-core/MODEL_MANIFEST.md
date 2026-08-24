# SFG Shared Biometric Core v1 Model Manifest

This manifest describes the exact pinned payloads used by the neutral core. The
payload files are local acquisition artifacts and are intentionally ignored by the
repository until redistribution review is complete. The manifest, source, tests, and
notices remain reviewable.

## Acquisition record

- Recorded acquisition/verification completion: **23 August 2026, 16:30:40 MYT
  (+08:00)**.
- Host baseline: Windows 11 x64; CPU-first inference. The accepted isolated
  implementation runtime is Python 3.10.6 x64, OpenCV 4.10.0.84, NumPy 2.2.6,
  and CPU PyTorch 2.6.0+cpu. An earlier global host probe observed a CUDA-capable
  2.6.0+cu126 build, but CUDA was not used by the accepted core baseline.
- Model files were fetched from the exact commit-pinned URLs below. OpenCV Zoo Git
  LFS pointer responses (131/133 bytes) were rejected; the actual media payloads
  were fetched from the corresponding GitHub Media URL and then hash-verified.

## OpenCV Zoo assets

### YuNet

- Filename: `face_detection_yunet_2023mar.onnx`
- Role: YuNet face detection, box, and five landmarks; not identity, PAD, or
  authorization.
- Repository revision: `47534e27c9851bb1128ccc0102f1145e27f23f98`
- Upstream directory:
  <https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet>
- Acquisition URL:
  <https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx>
- Exact byte size: `232589`
- SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- Git LFS pointer blob SHA-1: `2d8804a5986e229f1fde3a1994feacc66c91b58b`
- API: `cv2.FaceDetectorYN` with OpenCV DNN backend/CPU target; input size is
  updated to each actual frame width and height; provisional settings are
  confidence `0.9`, NMS `0.3`, and `top_k=5000`.
- License/redistribution: the pinned model directory states MIT License,
  Copyright (c) 2020 Shiqi Yu. Full notice:
  <https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/LICENSE>
  Redistribution of the payload is pending final review.

### SFace

- Filename: `face_recognition_sface_2021dec.onnx`
- Role: OpenCV SFace `alignCrop`, 112x112 feature extraction, and cosine
  comparison; not PAD or authorization.
- Repository revision: `47534e27c9851bb1128ccc0102f1145e27f23f98`
- Upstream directory:
  <https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface>
- Acquisition URL:
  <https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/face_recognition_sface_2021dec.onnx>
- Exact byte size: `38696353`
- SHA-256: `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`
- Git LFS pointer blob SHA-1: `5817e559d509b2c1d5069f3c49a388bc45d4395f`
- API: `cv2.FaceRecognizerSF` on the OpenCV DNN backend/CPU target. The accepted
  feature is finite contiguous float32 `(1,128)` and the comparison metric is
  `FaceRecognizerSF.FR_COSINE`.
- License/redistribution: the pinned model directory states Apache License 2.0.
  Full notice:
  <https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/LICENSE>
  Redistribution of the payload is pending final review.

## Silent Face PAD assets

- Repository: MiniVision `Silent-Face-Anti-Spoofing`
- Exact revision: `b6d5f04ad78778917853b25c778acef6d5626d15`
- Upstream revision:
  <https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/tree/b6d5f04ad78778917853b25c778acef6d5626d15>
- Source license: Apache License 2.0, Copyright 2020 Minivision. The adapted
  network definitions in `src/sfg_biometric_core/silent_face_pad.py` retain pinned
  architecture semantics and carry an adaptation notice. Full upstream license:
  <https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/b6d5f04ad78778917853b25c778acef6d5626d15/LICENSE>
- Attribution/source code path: `src/model_lib/MiniFASNet.py` at the pinned commit.
  The SFG wrapper intentionally does not copy the upstream RetinaFace detector,
  per-frame model reload, or result-image write path.
- Redistribution status for both payloads and adapted source: pending final notice
  review; binaries are ignored and are not committed.

| Filename | Exact bytes | Git blob SHA-1 | SHA-256 | Role/model semantics |
| --- | ---: | --- | --- | --- |
| `2.7_80x80_MiniFASNetV2.pth` | `1849453` | `47c4af2023fb072c0f5b0e0ade4824053a0558e1` | `a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0` | filename scale `2.7`, MiniFASNetV2, three classes |
| `4_0_0_80x80_MiniFASNetV1SE.pth` | `1856130` | `55a25b316ef33ced3925687007a31a5e306990db` | `84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990` | filename scale `4.0`, MiniFASNetV1SE, three classes |

The wrapper supplies YuNet `[x,y,width,height]`, expands/clamps each box by its
filename-derived scale, performs 80x80 linear BGR resize, converts HWC uint8 to
CHW float32 without `/255` or mean/std normalization, loads both allowlisted state
dictionaries once with `torch.load(..., map_location="cpu", weights_only=True)`,
uses `eval()` and `torch.no_grad()`, and applies softmax over class dimension 1.
Class `1` is the upstream live class; classes `0` and `2` are attack classes without
additional semantic labels. SFG maps the two-model result conservatively to
`PAD_LIVE`, `PAD_REJECT`, `PAD_UNCERTAIN`, or `PAD_ERROR`.

`PAD_ACCEPT_THRESHOLD` and `PAD_REJECT_THRESHOLD` are reserved and inactive. No
scalar PAD threshold, certification, universal spoof-resistance, accuracy, FAR, or
FRR claim is made.

## Compatibility fingerprint ingredients

Every template comparison binds and validates:

- both exact model filenames and SHA-256 values above;
- YuNet five-point order: right eye, left eye, nose tip, right mouth corner, left
  mouth corner;
- OpenCV 4.10 runtime identity, CPU DNN backend and CPU target;
- OpenCV `FaceRecognizerSF.alignCrop` five-point similarity transform and 112x112
  `INTER_LINEAR` warp;
- SFace `blobFromImage(scale=1, mean=(0,0,0), swapRB=true, crop=false)` path;
- raw finite float32 shape `(1,128)`, no stored pre-normalization;
- little-endian IEEE-754 float32 C-order binary serialization, exactly 512 bytes;
- OpenCV `FaceRecognizerSF.FR_COSINE` comparison and the Core v1 protected linear
  1:N policy.

The fingerprint is internal compatibility metadata, not an addition to the v1.2
shared-variable or configuration-name contract.

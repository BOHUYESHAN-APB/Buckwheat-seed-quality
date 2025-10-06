# Quickstart — Android

This document provides a short quickstart to run the Buckwheat Android demo.

Key steps:

1. Copy a compatible ONNX model to `app/src/main/assets/models/model.onnx` (opset 14 recommended).
2. Launch the project in Android Studio and build the `app` module.
3. Install the APK on a device running Android 9+ (API 28) and grant camera permission.

Notes:
- Model input: `[1, 3, 800, 800]`.
- Output detection format: `[N, 6]` with `[class, score, x1, y1, x2, y2]` (postprocess required).

See `testing_and_validation.md` and `troubleshooting_and_fixes.md` for deeper guidance.

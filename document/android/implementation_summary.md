<!-- Copied from android-app/IMPLEMENTATION_SUMMARY.md -->

# Implementation Summary

See the original `android-app/IMPLEMENTATION_SUMMARY.md` for a full, detailed implementation summary. Key points:

- Real-time detection implemented with CameraX `ImageAnalysis` and `InferenceEngine`.
- Single-image capture flow saved to `cache/photos/` and processed via `runInference(Bitmap)`.
- Performance monitor captures FPS, CPU and memory snapshots.
- Session rebuild logic attempts to recover from `OrtSession` errors.

Refer to in-repo scripts under `android-app/` for testing and analysis. This file acts as a short index.

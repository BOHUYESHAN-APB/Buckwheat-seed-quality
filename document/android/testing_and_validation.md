# Testing and Validation

This document collects testing, validation checklist and visual verification steps for the Android demo.

Contents:

- Realtime / Single-image test checklist
- Performance targets (FPS, CPU, memory)
- Visual checklist for annotated images
- How to run the existing test scripts in `android-app/`

Summary of steps:

1. Verify camera preview and realtime mode.
2. Run `android-app/onnx_annotate_fixed.py` on sample images and compare `android-app/output/*` annotated images.
3. Confirm detection counts and box positions against reference.
4. Use `adb logcat` and `Android Profiler` to measure FPS and CPU usage.

Expected targets:

- FPS ≥ 15 on mid-range devices
- CPU < 80% sustained
- Memory < 400 MB during realtime

See `quickstart.md` for how to install and run the app locally.

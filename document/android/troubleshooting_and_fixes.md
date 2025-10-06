# Troubleshooting and Fixes

This file summarizes common issues and their fixes discovered during ONNX integration and Android testing.

Key fixes included:

- Coordinate scaling fix: model outputs in 800x800 must be scaled back to original image dimensions using scale factors.
- Session rebuild: detect and rebuild closed ONNX sessions automatically.
- Fallback provider plan: ONNX Runtime attempts Vulkan/NNAPI and falls back to XNNPACK/CPU.

If a fix was a temporary or development-only report, the original repair scripts and reports have been removed from the active Android docs and archived.

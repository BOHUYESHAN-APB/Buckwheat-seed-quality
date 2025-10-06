# Model Assets

Place the exported ONNX model and label file here before building the Android app.

```text
model.onnx           # Copy from exports/best/.../model.onnx
labels.json          # Optional: class labels matching the training dataset
```

The application copies `model.onnx` to the internal storage at runtime. If `labels.json` is missing, detections will display generic labels.

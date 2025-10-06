#!/usr/bin/env python
"""Quick sanity check between Paddle Inference and ONNX Runtime outputs.

This script helps you validate whether a freshly exported ONNX model
behaves the same as the original PaddleDetection checkpoint.

Usage example:

```
python sandbox_scripts/onnx_sanity_check.py \
    --paddle-model-dir output_inference/ppyoloe_plus_crn_l_300e \
    --onnx-model exports/ppyoloe_plus_crn_l_300e.onnx \
    --image demo/test.jpg
```

Requirements:
- paddlepaddle or paddlepaddle-gpu >= 2.6
- onnxruntime >= 1.16
- opencv-python (or Pillow as an alternative image loader)

The script intentionally fails fast with clear error messages when a
required dependency is missing so that it can be used as a checklist in CI.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np

try:  # Prefer OpenCV; fall back to Pillow if unavailable.
    import cv2

    def _imread(path: Path) -> np.ndarray:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Failed to load image: {path}")
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

except ModuleNotFoundError:  # pragma: no cover
    try:
        from PIL import Image

        def _imread(path: Path) -> np.ndarray:
            with Image.open(path) as im:
                return np.asarray(im.convert("RGB"))

    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SystemExit(
            "Neither OpenCV nor Pillow is installed. Please install one of them via\n"
            "  pip install opencv-python\n"
            "or\n"
            "  pip install Pillow"
        ) from exc


try:
    import paddle
    from paddle import inference as paddle_infer
except ModuleNotFoundError as exc:
    paddle = None  # type: ignore[assignment]
    paddle_infer = None  # type: ignore[assignment]
    _paddle_error = exc
else:
    _paddle_error = None

try:
    import onnxruntime as ort
except ModuleNotFoundError as exc:
    ort = None  # type: ignore[assignment]
    _ort_error = exc
else:
    _ort_error = None


@dataclass
class ModelOutput:
    raw_boxes: np.ndarray
    raw_scores: np.ndarray


def _check_dependencies() -> None:
    if _paddle_error is not None:
        raise SystemExit(
            "PaddlePaddle is required but not installed.\n"
            "Install GPU build (recommended) or CPU build, e.g.\n"
            "  pip install paddlepaddle-gpu==3.1.0 --extra-index-url https://www.paddlepaddle.org.cn/whl/mkl\n"
            "or\n"
            "  pip install paddlepaddle==3.1.0"
        ) from _paddle_error
    if _ort_error is not None:
        raise SystemExit(
            "onnxruntime is required but not installed.\n"
            "Install with:\n"
            "  pip install onnxruntime==1.16.3"
        ) from _ort_error


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paddle-model-dir",
        type=Path,
        required=True,
        help="Directory containing Paddle Inference .pdmodel/.pdiparams files",
    )
    parser.add_argument(
        "--paddle-model-name",
        default="model.pdmodel",
        help="Name of Paddle model file inside the directory (default: model.pdmodel)",
    )
    parser.add_argument(
        "--paddle-params-name",
        default="model.pdiparams",
        help="Name of Paddle parameter file inside the directory (default: model.pdiparams)",
    )
    parser.add_argument(
        "--onnx-model",
        type=Path,
        required=True,
        help="Path to the exported ONNX model",
    )
    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Path to a test image (will be resized to 800x800)",
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="Run Paddle inference with GPU if CUDA device is available",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.25,
        help="Confidence threshold when printing detections",
    )
    parser.add_argument(
        "--print-limit",
        type=int,
        default=20,
        help="Maximum number of detections to print per model",
    )
    return parser.parse_args(argv)


def letterbox_resize(image: np.ndarray, size: Tuple[int, int] = (800, 800)) -> Tuple[np.ndarray, Dict[str, float]]:
    """Resize image with letterbox padding to keep aspect ratio."""
    target_w, target_h = size
    h, w = image.shape[:2]
    scale = min(target_w / w, target_h / h)
    resized_w, resized_h = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    pad_x = (target_w - resized_w) // 2
    pad_y = (target_h - resized_h) // 2
    padded[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized

    meta = {
        "scale": float(scale),
        "pad_x": float(pad_x),
        "pad_y": float(pad_y),
        "orig_w": float(w),
        "orig_h": float(h),
    }
    return padded, meta


def preprocess(image_path: Path) -> Tuple[np.ndarray, Dict[str, float]]:
    image = _imread(image_path)
    image, meta = letterbox_resize(image)
    image = image.astype("float32") / 255.0
    image = image.transpose(2, 0, 1)  # HWC -> CHW
    image = np.expand_dims(image, axis=0)
    return image, meta


def paddle_infer_run(args: argparse.Namespace, tensor: np.ndarray) -> ModelOutput:
    model_path = args.paddle_model_dir / args.paddle_model_name
    params_path = args.paddle_model_dir / args.paddle_params_name

    if not model_path.exists() or not params_path.exists():
        raise FileNotFoundError(
            f"Paddle inference files not found: {model_path} / {params_path}.\n"
            "Ensure you exported the model via PaddleDetection's export script."
        )

    config = paddle_infer.Config(str(model_path), str(params_path))
    if args.use_gpu:
        config.enable_use_gpu(2000, 0)
    else:
        config.disable_gpu()
        config.set_cpu_math_library_num_threads(4)
    config.switch_ir_optim(True)
    predictor = paddle_infer.create_predictor(config)

    input_handle = predictor.get_input_handle(predictor.get_input_names()[0])
    input_handle.copy_from_cpu(tensor)
    predictor.run()

    output_names = predictor.get_output_names()
    outputs = [predictor.get_output_handle(name).copy_to_cpu() for name in output_names]
    # PaddleDetection export order: [boxes, scores]
    raw_boxes, raw_scores = outputs
    return ModelOutput(raw_boxes=raw_boxes, raw_scores=raw_scores)


def onnx_infer_run(args: argparse.Namespace, tensor: np.ndarray) -> ModelOutput:
    if not args.onnx_model.exists():
        raise FileNotFoundError(f"ONNX model not found: {args.onnx_model}")

    session = ort.InferenceSession(str(args.onnx_model), providers=["CPUExecutionProvider"])
    feed = {session.get_inputs()[0].name: tensor}
    outputs = session.run(None, feed)
    raw_boxes, raw_scores = outputs[:2]
    return ModelOutput(raw_boxes=raw_boxes, raw_scores=raw_scores)


def summarize(output: ModelOutput, meta: Dict[str, float], threshold: float, limit: int, label: str) -> None:
    scores = output.raw_scores.squeeze(axis=0)
    boxes = output.raw_boxes.squeeze(axis=0)
    keep = scores.max(axis=1) > threshold
    indices = np.where(keep)[0]

    print(f"\n[{label}] Detections above {threshold:.2f} ({len(indices)} found)")
    for idx in indices[:limit]:
        cls = int(scores[idx].argmax())
        conf = float(scores[idx][cls])
        x1, y1, x2, y2 = boxes[idx]
        # map back to original resolution
        x1 = (x1 - meta["pad_x"]) / meta["scale"]
        y1 = (y1 - meta["pad_y"]) / meta["scale"]
        x2 = (x2 - meta["pad_x"]) / meta["scale"]
        y2 = (y2 - meta["pad_y"]) / meta["scale"]
        print(f"  cls={cls:<2d} conf={conf:.3f} bbox=({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f})")


def compare_outputs(paddle_out: ModelOutput, onnx_out: ModelOutput) -> None:
    def _metrics(a: np.ndarray, b: np.ndarray) -> Tuple[float, float]:
        diff = np.abs(a - b)
        return float(diff.max()), float((diff / (np.abs(a) + 1e-6)).max())

    max_abs_boxes, max_rel_boxes = _metrics(paddle_out.raw_boxes, onnx_out.raw_boxes)
    max_abs_scores, max_rel_scores = _metrics(paddle_out.raw_scores, onnx_out.raw_scores)

    print("\n[Diff] Boxes  max_abs={:.4f} max_rel={:.4f}".format(max_abs_boxes, max_rel_boxes))
    print("[Diff] Scores max_abs={:.4f} max_rel={:.4f}".format(max_abs_scores, max_rel_scores))

    if max_abs_boxes > 1e-2 or max_abs_scores > 1e-2:
        print("[Warn] Differences are larger than expected. Revisit export settings.")
    else:
        print("[OK] Outputs match within tolerance.")


def main(argv: Iterable[str]) -> None:
    _check_dependencies()
    args = parse_args(argv)

    tensor, meta = preprocess(args.image)
    paddle_out = paddle_infer_run(args, tensor)
    onnx_out = onnx_infer_run(args, tensor)

    summarize(paddle_out, meta, args.confidence_threshold, args.print_limit, label="Paddle")
    summarize(onnx_out, meta, args.confidence_threshold, args.print_limit, label="ONNX")
    compare_outputs(paddle_out, onnx_out)


if __name__ == "__main__":
    main(sys.argv[1:])

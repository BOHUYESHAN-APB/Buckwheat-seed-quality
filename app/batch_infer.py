"""Batch inference helper that reuses the app's Detector visualization.

Run with:
    python -m app.batch_infer --input-dir path/to/images --output-dir inference_results/showcase
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

# Allow running the file directly (python app/batch_infer.py)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

try:  # pragma: no cover - support running as module or script
    from app.batch_runner import BatchStats, run_batch as run_batch_runner  # type: ignore[attr-defined]  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover
    from batch_runner import BatchStats, run_batch as run_batch_runner  # type: ignore[attr-defined]  # noqa: E402

from app.ui import Detector  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch inference using the app Detector (same visualization as GUI).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model-dir",
        default="inference_model/ppyoloe_plus_crn_m_300e_speed_optimized",
        help="Directory containing model.pdmodel / model.pdiparams. Use 'none' for fallback mode.",
    )
    parser.add_argument(
        "--input-dir",
        default="inference_results/raw",
        help="Directory with images to process.",
    )
    parser.add_argument(
        "--output-dir",
        default="inference_results/showcase",
        help="Directory to save visualized results (keeps relative structure).",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.5,
        help="Detector score threshold.",
    )
    parser.add_argument(
        "--nms-iou",
        type=float,
        default=0.45,
        help="Detector NMS IoU threshold.",
    )
    parser.add_argument(
        "--min-side",
        type=float,
        default=12.0,
        help="Minimum width/height in pixels to keep a detection box.",
    )
    parser.add_argument(
        "--min-area",
        type=float,
        default=144.0,
        help="Minimum area (w*h) in pixels to keep a detection box.",
    )
    parser.add_argument(
        "--max-aspect-ratio",
        type=float,
        default=10.0,
        help="Maximum aspect ratio (longer/shorter) to keep a detection box.",
    )
    parser.add_argument(
        "--max-detections",
        type=int,
        default=120,
        help="Maximum number of boxes per image after filtering (0 for unlimited).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of images to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Enumerate images and print stats without saving outputs.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files even if present in the output directory.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress per-image logs (only show summary).",
    )
    gpu_group = parser.add_mutually_exclusive_group()
    gpu_group.add_argument(
        "--force-gpu",
        action="store_true",
        help="Force using GPU if available; warn and fall back if not.",
    )
    gpu_group.add_argument(
        "--force-cpu",
        action="store_true",
        help="Force using CPU even if GPU is available.",
    )
    return parser


def configure_detector(args: argparse.Namespace) -> Detector:
    model_dir = args.model_dir
    if model_dir and model_dir.lower() == "none":
        model_dir = None
    if model_dir and not os.path.isdir(model_dir):
        print(f"[WARN] model directory '{model_dir}' not found; entering fallback mode.")
        model_dir = None

    use_gpu: Optional[bool]
    if args.force_gpu:
        use_gpu = True
    elif args.force_cpu:
        use_gpu = False
    else:
        use_gpu = None

    detector = Detector(model_dir=model_dir, use_gpu=use_gpu)
    if hasattr(detector, "score_threshold"):
        detector.score_threshold = float(args.score_threshold)
    if hasattr(detector, "nms_iou_threshold"):
        detector.nms_iou_threshold = float(args.nms_iou)
    if hasattr(detector, "min_box_side"):
        detector.min_box_side = float(args.min_side)
    if hasattr(detector, "min_box_area"):
        detector.min_box_area = float(args.min_area)
    if hasattr(detector, "max_box_aspect_ratio"):
        detector.max_box_aspect_ratio = float(args.max_aspect_ratio)
    if hasattr(detector, "max_box_count"):
        detector.max_box_count = None if int(args.max_detections) <= 0 else int(args.max_detections)
    if not detector.is_ready:
        print("[WARN] Detector not ready; fallback visualization will be used.")
    return detector


def run_batch(args: argparse.Namespace) -> None:
    detector = configure_detector(args)
    stats: BatchStats = run_batch_runner(
        detector,
        args.input_dir,
        args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
        dry_run=args.dry_run,
        silent=args.silent,
    )

    if stats.total == 0:
        print("No images found to process.")
        return

    print(
        f"Batch finished in {stats.elapsed:.2f}s — processed: {stats.processed}, skipped: {stats.skipped}, unreadable: {stats.unreadable}, total discovered: {stats.total}."
    )


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_batch(args)


if __name__ == "__main__":
    main()

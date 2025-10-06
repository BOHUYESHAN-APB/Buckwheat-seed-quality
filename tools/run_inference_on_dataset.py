import argparse
import os
import sys

# ensure workspace root is on sys.path so the 'app' package can be imported when running the script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2

from app.ui import Detector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch inference over a directory of images using Detector")
    parser.add_argument(
        "--model-dir",
        default="inference_model/ppyoloe_plus_crn_m_300e_speed_optimized",
        help="Path to Paddle Inference model directory (containing model.pdmodel & model.pdiparams). Use 'none' to run fallback mode.",
    )
    parser.add_argument(
        "--input-dir",
        default="data/raw/train-use/test",
        help="Directory containing images for inference",
    )
    parser.add_argument(
        "--out-dir",
        default="inference_results/showcase",
        help="Directory to save visualized inference results (default: inference_results/showcase)",
    )
    parser.add_argument(
        "--target-size",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        help="Optional resize target (overrides infer_cfg target_size)",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.5,
        help="Score threshold for post-processing",
    )
    parser.add_argument(
        "--nms-iou",
        type=float,
        default=0.45,
        help="NMS IoU threshold",
    )
    parser.add_argument(
        "--min-side",
        type=float,
        default=6.0,
        help="Minimum side (width or height) in pixels to keep a box for visualization",
    )
    parser.add_argument(
        "--min-area",
        type=float,
        default=36.0,
        help="Minimum area (w*h) in pixels to keep a box for visualization",
    )
    parser.add_argument(
        "--max-aspect-ratio",
        type=float,
        default=10.0,
        help="Maximum aspect ratio (longer/shorter) to keep a box for visualization",
    )
    parser.add_argument(
        "--max-detections",
        type=int,
        default=100,
        help="Maximum number of boxes to draw per image after filtering (0 for unlimited)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    model_dir = args.model_dir
    if model_dir and model_dir.lower() == "none":
        model_dir = None
    if model_dir and not os.path.isdir(model_dir):
        print(f"[WARN] model-dir '{model_dir}' not found. Fallback to Detector fallback mode.")
        model_dir = None

    print("Loading model:", model_dir or "<fallback>")
    detector = Detector(model_dir=model_dir)

    if args.target_size is not None:
        detector.target_size = (args.target_size[0], args.target_size[1])

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
        max_detections = int(args.max_detections)
        detector.max_box_count = None if max_detections <= 0 else max_detections

    print(
        "Detector status -> is_ready:", detector.is_ready,
        "target_size:", getattr(detector, "target_size", None),
    )

    input_dir = os.path.abspath(args.input_dir)
    out_dir = os.path.abspath(args.out_dir)
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    os.makedirs(out_dir, exist_ok=True)

    count = 0
    skipped = 0
    for root, _, files in os.walk(input_dir):
        for fname in sorted(files):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")):
                continue
            src_path = os.path.join(root, fname)
            img = cv2.imread(src_path)
            if img is None:
                print("[WARN] skip unreadable", src_path)
                skipped += 1
                continue

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            result_rgb = detector.detect_image(rgb)
            result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
            boxes = getattr(detector, "last_boxes", [])

            rel_path = os.path.relpath(src_path, input_dir)
            dst_path = os.path.join(out_dir, rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            cv2.imwrite(dst_path, result_bgr)
            count += 1
            print(f"saved {rel_path} -> boxes={len(boxes)}")

    print(f"Processed {count} images -> {out_dir}. Skipped {skipped} files.")


if __name__ == "__main__":
    main()
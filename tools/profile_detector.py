"""Utility script to profile the buckwheat detector on a single image."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import cv2

# Ensure the root directory (containing `app`) is on sys.path when the script is executed
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ui import Detector  # noqa: E402  pylint: disable=wrong-import-position


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single forward pass of the detector and report timing stats.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Path to the RGB/BGR image to process.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help="Directory that contains model.pdmodel and model.pdiparams."
             " Defaults to the value of BUCKWHEAT_MODEL_DIR if not provided.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debug_result.jpg"),
        help="Where to write the visualization result (RGB saved as BGR JPEG).",
    )
    parser.add_argument(
        "--disable-profile",
        action="store_true",
        help="Disable profiling collection inside the detector.",
    )
    return parser.parse_args(argv)


def ensure_image(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return path


def resolve_model_dir(cli_model_dir: Optional[Path]) -> Optional[str]:
    if cli_model_dir is not None:
        return str(cli_model_dir)
    env_dir = os.getenv("BUCKWHEAT_MODEL_DIR")
    return env_dir if env_dir else None


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    image_path = ensure_image(args.image)
    model_dir = resolve_model_dir(args.model_dir)

    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise RuntimeError(f"Failed to read image: {image_path}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    detector = Detector(model_dir=model_dir)
    if args.disable_profile:
        detector.profile_enabled = False

    result_rgb = detector.detect_image(img_rgb)

    # Persist visualization
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR))

    if detector.last_error:
        print(f"Detector reported error: {detector.last_error}")
    if detector.last_timing:
        print("Timings (ms):")
        for key, value in detector.last_timing.items():
            print(f"  {key:>14}: {value:8.2f}")
    else:
        print("No timing information collected.")
    print(f"Boxes detected: {len(detector.last_boxes)}")
    if detector.last_boxes:
        first_box = detector.last_boxes[0]
        print("First box:", first_box)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
OpenI / CloudBrain main training entry for Huawei Ascend / MindSpore.

This is the boot_file for OpenI jobs. Only Ascend/NPU is supported.

Usage (key=value style):
    python openi_cloudbrain_train_mindspore.py \
        zip-name=data.zip \
        extract-dir=/cache/dataset/data_extracted \
        checkpoint-dir=/cache/output/model \
        algorithm=colony_seednet_v1 \
        device=npu \
        num-epochs=300
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Minimal arg parsing (key=value, no -- prefix)
# ---------------------------------------------------------------------------


def parse_kv_arguments(raw_items: List[str]) -> Dict[str, str]:
    """Parse key=value style arguments, tolerates --key=value as well."""
    parsed: Dict[str, str] = {}
    for item in raw_items:
        if not item:
            continue
        item = item.lstrip("-")
        if "=" in item:
            key, value = item.split("=", 1)
            parsed[key.strip()] = value.strip()
        else:
            parsed[item.strip()] = ""
    return parsed


def pick_value(values: Dict[str, str], keys: List[str], default: str = "") -> str:
    for k in keys:
        if k in values and values[k]:
            return values[k]
    return default


# ---------------------------------------------------------------------------
# COCO detection helpers (inlined to keep this entry self-contained)
# ---------------------------------------------------------------------------


def detect_coco_layout(dataset_root: str) -> Dict[str, Any]:
    root = Path(dataset_root)
    result: Dict[str, Any] = {
        "valid": False,
        "train_annotation": None,
        "train_images": None,
        "val_annotation": None,
        "val_images": None,
        "layout_type": "unknown",
    }
    if not root.is_dir():
        return result

    train_dir = root / "train"
    val_dir = root / "val"
    if train_dir.is_dir() and val_dir.is_dir():
        for split, ann_key, img_key in [
            ("train", "train_annotation", "train_images"),
            ("val", "val_annotation", "val_images"),
        ]:
            ann_dir = root / split / "annotations"
            img_dir = root / split / "images"
            if ann_dir.is_dir() and img_dir.is_dir():
                ann_files = list(ann_dir.glob("*.json"))
                if ann_files:
                    result[ann_key] = str(ann_files[0])
                    result[img_key] = str(img_dir)
        if result["train_annotation"] and result["val_annotation"]:
            result["valid"] = True
            result["layout_type"] = "nested"
            return result

    flat_ann = root / "annotations"
    flat_train = root / "train2017"
    flat_val = root / "val2017"
    if flat_ann.is_dir():
        for name, key in [
            ("instances_train.json", "train_annotation"),
            ("instances_train2017.json", "train_annotation"),
            ("instances_val.json", "val_annotation"),
            ("instances_val2017.json", "val_annotation"),
        ]:
            p = flat_ann / name
            if p.exists() and result[key] is None:
                result[key] = str(p)
        if result["train_annotation"] and flat_train.is_dir():
            result["train_images"] = str(flat_train)
        if result["val_annotation"] and flat_val.is_dir():
            result["val_images"] = str(flat_val)
        if result["train_annotation"] and result["val_annotation"]:
            result["valid"] = True
            result["layout_type"] = "flat"

    return result


# ---------------------------------------------------------------------------
# Zip helpers (minimal, delegates to openi_prepare_dataset if available)
# ---------------------------------------------------------------------------


def find_and_extract_zip(kv: Dict[str, str], extract_dir: str) -> Optional[str]:
    """Find dataset zip, extract, return zip filename or None."""
    import zipfile

    zip_name = pick_value(kv, ["zip-name", "zip_name", "zip", "dataset-zip"], "")
    search_dir = pick_value(kv, ["search-dir", "search_dir", "data-root"], ".")

    # Collect candidates
    candidates: List[str] = []
    search = Path(search_dir)
    if search.is_dir():
        candidates = sorted(str(p) for p in search.glob("*.zip"))

    selected: Optional[str] = None
    if zip_name and os.path.isfile(zip_name):
        selected = zip_name
    elif candidates:
        # Priority: explicit name match > 'clean' in name > first
        if zip_name:
            for c in candidates:
                if zip_name in Path(c).name:
                    selected = c
                    break
        if not selected:
            for c in candidates:
                if "clean" in Path(c).name.lower():
                    selected = c
                    break
        if not selected:
            selected = candidates[0]

    if selected:
        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)
        layout = detect_coco_layout(str(extract_path))
        if not layout["valid"]:
            print(f"[cloudbrain] Extracting {selected} -> {extract_dir}")
            try:
                with zipfile.ZipFile(selected, "r") as zf:
                    zf.extractall(str(extract_path))
            except zipfile.BadZipFile as exc:
                print(f"[cloudbrain] ERROR: {exc}", file=sys.stderr)
        return Path(selected).name

    return None


# ---------------------------------------------------------------------------
# Device validation
# ---------------------------------------------------------------------------


def normalize_device(device_raw: str) -> str:
    """Only accept npu/ascend, normalize to 'Ascend'. Reject GPU/CUDA."""
    lowered = device_raw.lower().strip()
    if lowered in ("npu", "ascend", "huawei", "ascend_npu"):
        return "Ascend"
    if lowered in ("gpu", "cuda"):
        print(
            "[cloudbrain] ERROR: GPU/CUDA is not supported for Huawei migration target. "
            "Only Ascend/NPU is allowed.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"[cloudbrain] WARNING: unrecognized device '{device_raw}', defaulting to Ascend"
    )
    return "Ascend"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    raw = sys.argv[1:]

    # Support --help
    if any(a in ("--help", "-h", "help") for a in raw):
        print(__doc__)
        print("Key parameters (key=value format):")
        print("  zip-name=<dataset.zip>          Dataset zip filename")
        print("  extract-dir=/cache/dataset/...  Extraction path")
        print("  checkpoint-dir=/cache/output/.. Model output path")
        print("  algorithm=colony_seednet_v1     Algorithm identifier")
        print("  device=npu                      Device target (npu/ascend only)")
        print("  num-epochs=300                  Training epochs")
        print("  batch-size=8                    Batch size")
        print("  learning-rate=0.0005            Base learning rate")
        print("  num-workers=8                   DataLoader workers")
        print("  image-size=384                  Input image size")
        print("  max-steps-per-epoch=0           0=use full epoch")
        print("  stop-after-first-epoch=0        0=run all epochs")
        print("  search-dir=.                    Where to search for zip files")
        return

    kv = parse_kv_arguments(raw)

    # Extract parameters
    extract_dir = pick_value(
        kv, ["extract-dir", "extract_dir", "extract"], "/cache/dataset/data_extracted"
    )
    checkpoint_dir = pick_value(
        kv, ["checkpoint-dir", "checkpoint_dir", "output"], "/cache/output/model"
    )
    algorithm = pick_value(kv, ["algorithm", "algo", "model"], "colony_seednet_v1")
    device_raw = pick_value(kv, ["device", "device-target", "device_target"], "npu")
    num_epochs = pick_value(kv, ["num-epochs", "num_epochs", "epochs"], "300")
    batch_size = pick_value(kv, ["batch-size", "batch_size", "batch"], "8")
    learning_rate = pick_value(kv, ["learning-rate", "learning_rate", "lr"], "0.0005")
    num_workers = pick_value(kv, ["num-workers", "num_workers", "workers"], "8")
    image_size = pick_value(
        kv, ["image-size", "image_size", "img-size", "img_size"], "384"
    )
    max_steps = pick_value(kv, ["max-steps-per-epoch", "max_steps_per_epoch"], "0")
    stop_first = pick_value(
        kv, ["stop-after-first-epoch", "stop_after_first_epoch"], "0"
    )
    dataset_profile = pick_value(kv, ["dataset-profile", "dataset_profile"], "clean")

    # Validate & normalize device
    device_target = normalize_device(device_raw)

    # Ensure checkpoint dir exists
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

    # Find and extract dataset zip
    zip_filename = find_and_extract_zip(kv, extract_dir)
    if not zip_filename:
        print("[cloudbrain] WARNING: no dataset zip found")

    # Detect COCO layout
    layout = detect_coco_layout(extract_dir)

    # Build downstream command
    boot_file = "scripts/openi_cloudbrain_train_mindspore.py"
    train_script = str(Path(__file__).resolve().parent / "mindspore_colony_train.py")

    downstream_cmd = [
        sys.executable,
        train_script,
        f"algorithm={algorithm}",
        f"device-target={device_target}",
        f"extract-dir={extract_dir}",
        f"checkpoint-dir={checkpoint_dir}",
        f"num-epochs={num_epochs}",
        f"batch-size={batch_size}",
        f"learning-rate={learning_rate}",
        f"num-workers={num_workers}",
        f"image-size={image_size}",
        f"max-steps-per-epoch={max_steps}",
        f"stop-after-first-epoch={stop_first}",
        f"dataset-profile={dataset_profile}",
    ]

    # Export environment variables
    os.environ["DEVICE_TARGET"] = device_target
    os.environ["OPENI_DATASET_ZIP"] = zip_filename or ""
    os.environ["COLONY_DATASET_ROOT"] = extract_dir
    os.environ["COLONY_CHECKPOINT_DIR"] = checkpoint_dir
    os.environ["COLONY_EXTRACT_DIR"] = extract_dir

    # Write run summary
    run_summary = {
        "boot_file": boot_file,
        "device_target": device_target,
        "algorithm": algorithm,
        "openi_dataset_zip": zip_filename,
        "colony_dataset_root": extract_dir,
        "colony_checkpoint_dir": checkpoint_dir,
        "coco_layout": layout,
        "parameters": {
            "num_epochs": int(num_epochs),
            "batch_size": int(batch_size),
            "learning_rate": float(learning_rate),
            "num_workers": int(num_workers),
            "image_size": int(image_size),
            "max_steps_per_epoch": int(max_steps),
            "stop_after_first_epoch": int(stop_first),
            "dataset_profile": dataset_profile,
        },
        "downstream_command": downstream_cmd,
    }
    summary_path = os.path.join(checkpoint_dir, "mindspore_run_summary.json")
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2, ensure_ascii=False)

    # Print troubleshooting fields (exactly as required)
    print(f"OPENI_DATASET_ZIP={zip_filename or '<none>'}")
    print(f"COLONY_DATASET_ROOT={extract_dir}")
    print(f"COLONY_CHECKPOINT_DIR={checkpoint_dir}")
    print(f"boot_file={boot_file}")

    # Execute downstream training
    print(f"\n[cloudbrain] Dispatching to: {train_script}")
    try:
        result = subprocess.run(downstream_cmd, check=False)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(
            f"[cloudbrain] ERROR: training script not found: {train_script}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

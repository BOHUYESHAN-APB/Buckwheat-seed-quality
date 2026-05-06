#!/usr/bin/env python3
"""
OpenI dataset preparation for Huawei Ascend / MindSpore migration.

Handles: zip selection, extraction, COCO layout detection, manifest writing.
Uses key=value parameter style (no -- prefix).

Usage:
    python openi_prepare_dataset.py zip-name=data.zip extract-dir=/cache/dataset/data_extracted
"""

import argparse
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_kv_arguments(raw_items: List[str]) -> Dict[str, str]:
    """Parse key=value style arguments, also tolerates --key=value."""
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
    """Return the first matching key value from dict, with fallback."""
    for k in keys:
        if k in values and values[k]:
            return values[k]
    return default


def list_zip_files(root_dir: str) -> List[str]:
    """List all .zip files in the given directory."""
    root = Path(root_dir)
    if not root.is_dir():
        return []
    return sorted(str(p) for p in root.glob("*.zip"))


def select_dataset_zip(
    candidates: List[str], explicit_zip_name: Optional[str] = None
) -> Optional[str]:
    """Select the best dataset zip from candidates.

    Priority:
    1. Explicitly named zip (substring match on filename)
    2. Zip whose name contains 'clean'
    3. First non-merged zip
    4. First available zip
    """
    if not candidates:
        return None

    if explicit_zip_name:
        for c in candidates:
            if explicit_zip_name in Path(c).name:
                return c

    for c in candidates:
        if "clean" in Path(c).name.lower():
            return c

    for c in candidates:
        if "merged" not in Path(c).name.lower():
            return c

    return candidates[0]


def unzip_if_needed(zip_path: str, extract_root: str) -> str:
    """Extract zip if the extract_root doesn't already contain data."""
    extract_path = Path(extract_root)
    extract_path.mkdir(parents=True, exist_ok=True)

    # Check if already extracted (look for annotations or images directories)
    existing = detect_coco_layout(str(extract_path))
    if existing["valid"]:
        print(f"[prepare] COCO layout already present at {extract_root}")
        return str(extract_path)

    if not os.path.isfile(zip_path):
        print(f"[prepare] ERROR: zip file not found: {zip_path}", file=sys.stderr)
        return str(extract_path)

    print(f"[prepare] Extracting {zip_path} -> {extract_root}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(str(extract_path))
    except zipfile.BadZipFile as exc:
        print(f"[prepare] ERROR: bad zip file: {exc}", file=sys.stderr)

    return str(extract_path)


def detect_coco_layout(dataset_root: str) -> Dict[str, Any]:
    """Detect COCO-style dataset layout under dataset_root.

    Expected structure:
        <root>/train/annotations/*.json  (or <root>/annotations/ for train)
        <root>/train/images/
        <root>/val/annotations/*.json
        <root>/val/images/

    Also handles flat layout:
        <root>/annotations/instances_train.json
        <root>/annotations/instances_val.json
        <root>/train2017/
        <root>/val2017/
    """
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

    # Pattern 1: root/train/ and root/val/ with nested annotations/images
    train_dir = root / "train"
    val_dir = root / "val"
    if train_dir.is_dir() and val_dir.is_dir():
        train_ann_dir = train_dir / "annotations"
        train_img_dir = train_dir / "images"
        val_ann_dir = val_dir / "annotations"
        val_img_dir = val_dir / "images"

        if train_ann_dir.is_dir() and train_img_dir.is_dir():
            ann_files = list(train_ann_dir.glob("*.json"))
            if ann_files:
                result["train_annotation"] = str(ann_files[0])
                result["train_images"] = str(train_img_dir)

        if val_ann_dir.is_dir() and val_img_dir.is_dir():
            ann_files = list(val_ann_dir.glob("*.json"))
            if ann_files:
                result["val_annotation"] = str(ann_files[0])
                result["val_images"] = str(val_img_dir)

        if result["train_annotation"] and result["val_annotation"]:
            result["valid"] = True
            result["layout_type"] = "nested"
            return result

    # Pattern 2: root/annotations/ + root/train2017/ + root/val2017/
    flat_ann = root / "annotations"
    flat_train = root / "train2017"
    flat_val = root / "val2017"
    if flat_ann.is_dir():
        train_json = flat_ann / "instances_train.json"
        val_json = flat_ann / "instances_val.json"
        # Also check for instances_train2017.json naming
        if not train_json.exists():
            train_json = flat_ann / "instances_train2017.json"
        if not val_json.exists():
            val_json = flat_ann / "instances_val2017.json"

        if train_json.exists() and flat_train.is_dir():
            result["train_annotation"] = str(train_json)
            result["train_images"] = str(flat_train)
        if val_json.exists() and flat_val.is_dir():
            result["val_annotation"] = str(val_json)
            result["val_images"] = str(flat_val)

        if result["train_annotation"] and result["val_annotation"]:
            result["valid"] = True
            result["layout_type"] = "flat"
            return result

    # Pattern 3: root/annotations/ + root/images/ (single split)
    if flat_ann.is_dir() and (root / "images").is_dir():
        ann_files = list(flat_ann.glob("*.json"))
        if ann_files:
            result["train_annotation"] = str(ann_files[0])
            result["train_images"] = str(root / "images")
            result["val_annotation"] = str(ann_files[0])
            result["val_images"] = str(root / "images")
            result["valid"] = True
            result["layout_type"] = "single"

    return result


def write_manifest(manifest_path: str, data: Dict[str, Any]) -> None:
    """Write JSON manifest to disk."""
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[prepare] Manifest written: {manifest_path}")


def main() -> None:
    raw = sys.argv[1:]
    kv = parse_kv_arguments(raw)

    zip_name = pick_value(
        kv, ["zip-name", "zip_name", "zip", "dataset-zip", "dataset_zip"], ""
    )
    extract_dir = pick_value(
        kv,
        ["extract-dir", "extract_dir", "extract"],
        "./tmp_extract",
    )
    search_dir = pick_value(
        kv, ["search-dir", "search_dir", "data-root", "data_root"], "."
    )

    print("=== OpenI Dataset Preparation ===")

    # Step 1: Find and select zip
    candidates = list_zip_files(search_dir)
    if zip_name and os.path.isfile(zip_name):
        selected_zip = zip_name
    elif candidates:
        selected_zip = select_dataset_zip(
            candidates, explicit_zip_name=zip_name or None
        )
    else:
        selected_zip = None
        print("[prepare] WARNING: no zip files found in search dir")

    if selected_zip:
        print(f"OPENI_DATASET_ZIP={Path(selected_zip).name}")
    else:
        print("OPENI_DATASET_ZIP=<none>")

    # Step 2: Extract
    if selected_zip:
        unzip_if_needed(selected_zip, extract_dir)

    # Step 3: Detect COCO layout
    layout = detect_coco_layout(extract_dir)

    if layout["valid"]:
        print(f"COLONY_DATASET_ROOT={extract_dir}")
    else:
        print(f"COLONY_DATASET_ROOT=<not-found-in:{extract_dir}>")

    # Step 4: Write manifest
    manifest = {
        "selected_zip": Path(selected_zip).name if selected_zip else None,
        "extract_dir": extract_dir,
        "coco_layout": layout,
        "parameters": kv,
    }
    manifest_path = os.path.join(extract_dir, "dataset_manifest.json")
    write_manifest(manifest_path, manifest)

    print("=== Dataset Preparation Complete ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
MindSpore training dispatcher / dry-run planner for Huawei Ascend.

Registry-based dispatcher that supports multiple algorithms and generates
training plans (MindSpore YAML configs, learning-rate schedules, etc.).

Supported algorithms:
    mindyolo_yolov5, mindyolo_yolov8,
    mindcv_ssd, mindcv_deeplabv3,
    colony_seednet_v1

Usage (key=value style):
    python mindspore_colony_train.py algorithm=colony_seednet_v1 device-target=Ascend
"""

import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------


def parse_kv_arguments(raw_items: List[str]) -> Dict[str, str]:
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
# JSON writer
# ---------------------------------------------------------------------------


def write_json(path: str, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[dispatcher] Written: {path}")


# ---------------------------------------------------------------------------
# Learning rate schedule
# ---------------------------------------------------------------------------


def generate_warmup_cosine_schedule(
    total_epochs: int,
    base_lr: float,
    warmup_epochs: int = 5,
    min_lr_ratio: float = 0.01,
) -> List[Dict[str, Any]]:
    """Generate warmup + cosine decay LR schedule."""
    schedule: List[Dict[str, Any]] = []
    for epoch in range(total_epochs):
        if epoch < warmup_epochs:
            # Linear warmup
            lr = base_lr * (epoch + 1) / warmup_epochs
        else:
            # Cosine decay
            progress = (epoch - warmup_epochs) / max(
                total_epochs - warmup_epochs - 1, 1
            )
            lr = min_lr_ratio * base_lr + 0.5 * (base_lr - min_lr_ratio * base_lr) * (
                1 + math.cos(math.pi * progress)
            )
        schedule.append({"epoch": epoch, "lr": round(lr, 8)})
    return schedule


# ---------------------------------------------------------------------------
# Algorithm registry
# ---------------------------------------------------------------------------

ALGORITHM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "mindyolo_yolov5": {
        "framework": "MindYOLO",
        "model": "yolov5",
        "base_detector": "MindYOLO YOLOv5",
        "description": "Standard YOLOv5 from MindYOLO",
    },
    "mindyolo_yolov8": {
        "framework": "MindYOLO",
        "model": "yolov8",
        "base_detector": "MindYOLO YOLOv8",
        "description": "Standard YOLOv8 from MindYOLO",
    },
    "mindcv_ssd": {
        "framework": "MindCV",
        "model": "ssd",
        "base_detector": "MindCV SSD",
        "description": "SSD from MindCV for comparison (Phase 2)",
    },
    "mindcv_deeplabv3": {
        "framework": "MindCV",
        "model": "deeplabv3",
        "base_detector": "MindCV DeepLabV3",
        "description": "DeepLabV3 semantic segmentation (Phase 2 exploration)",
    },
    "colony_seednet_v1": {
        "framework": "Custom",
        "model": "colony_seednet_v1",
        "base_detector": "MindYOLO YOLOv8 + small-object optimization",
        "description": "ColonySeedNet-v1: custom small-object detector for buckwheat seeds",
    },
}


def get_algorithm_info(algorithm: str) -> Dict[str, Any]:
    if algorithm not in ALGORITHM_REGISTRY:
        available = ", ".join(sorted(ALGORITHM_REGISTRY.keys()))
        print(
            f"[dispatcher] ERROR: unknown algorithm '{algorithm}'. "
            f"Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)
    return ALGORITHM_REGISTRY[algorithm]


def generate_colony_seednet_v1_recipe(
    num_epochs: int,
    base_lr: float,
    batch_size: int,
    image_size: int,
    num_workers: int,
) -> Dict[str, Any]:
    """Generate ColonySeedNet-v1 training recipe."""
    return {
        "algorithm": "colony_seednet_v1",
        "base_detector": "MindYOLO YOLOv8",
        "device_target": "Ascend",
        "framework": "MindSpore",
        "training": {
            "epochs": num_epochs,
            "batch_size": batch_size,
            "base_lr": base_lr,
            "num_workers": num_workers,
            "image_size": [image_size, image_size],
            "lr_schedule": {
                "type": "warmup_cosine",
                "warmup_epochs": 5,
                "min_lr_ratio": 0.01,
            },
            "curriculum_augmentation": {
                "enabled": True,
                "stages": [
                    {
                        "name": "basic",
                        "epoch_range": [0, 50],
                        "augmentations": ["random_flip", "random_scale"],
                    },
                    {
                        "name": "intermediate",
                        "epoch_range": [50, 150],
                        "augmentations": [
                            "random_flip",
                            "random_scale",
                            "mosaic",
                            "color_jitter",
                        ],
                    },
                    {
                        "name": "advanced",
                        "epoch_range": [150, num_epochs],
                        "augmentations": [
                            "random_flip",
                            "random_scale",
                            "mosaic",
                            "mixup",
                            "color_jitter",
                            "random_rotation",
                        ],
                    },
                ],
            },
            "loss": {
                "classification": "focal",
                "focal_gamma": 2.5,
                "regression": "ciou",
                "dfl_enabled": True,
                "class_weighting": "inverse_frequency",
            },
        },
        "small_object_inference": {
            "tile_inference": True,
            "tile_size": [192, 192],
            "tile_overlap": 32,
            "nms_merge": True,
        },
        "classes": ["seeda", "seedb", "seedc", "seedd"],
        "num_classes": 4,
    }


# ---------------------------------------------------------------------------
# Recommended downstream commands
# ---------------------------------------------------------------------------


def generate_downstream_command(
    algorithm: str,
    algorithm_info: Dict[str, Any],
    kv: Dict[str, str],
) -> List[str]:
    """Generate the recommended external command to run the algorithm."""
    framework = algorithm_info.get("framework", "")
    device_target = pick_value(
        kv, ["device-target", "device_target", "device"], "Ascend"
    )
    extract_dir = pick_value(
        kv, ["extract-dir", "extract_dir"], "/cache/dataset/data_extracted"
    )
    checkpoint_dir = pick_value(
        kv, ["checkpoint-dir", "checkpoint_dir"], "/cache/output/model"
    )
    num_epochs = pick_value(kv, ["num-epochs", "num_epochs", "epochs"], "300")
    batch_size = pick_value(kv, ["batch-size", "batch_size"], "8")

    if framework == "MindYOLO":
        model = algorithm_info.get("model", "yolov8")
        return [
            "python",
            "-m",
            "mindyolo.tools.train",
            "--config",
            f"configs/{model}/{algorithm}.yaml",
            "--device_target",
            device_target,
            "--data_path",
            extract_dir,
            "--output_path",
            checkpoint_dir,
            "--epochs",
            num_epochs,
            "--batch_size",
            batch_size,
        ]

    if framework == "MindCV":
        model = algorithm_info.get("model", "ssd")
        return [
            "python",
            "-m",
            "mindcv.run_train",
            "--model",
            model,
            "--device_target",
            device_target,
            "--data_dir",
            extract_dir,
            "--ckpt_save_dir",
            checkpoint_dir,
            "--epochs",
            num_epochs,
            "--batch_size",
            batch_size,
        ]

    # ColonySeedNet-v1 or unknown custom: use MindYOLO YOLOv8 as base
    return [
        "python",
        "-m",
        "mindyolo.tools.train",
        "--config",
        "huawei_npu_migration/configs/colony_seednet_v1.yaml",
        "--device_target",
        device_target,
        "--data_path",
        extract_dir,
        "--output_path",
        checkpoint_dir,
        "--epochs",
        num_epochs,
        "--batch_size",
        batch_size,
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    raw = sys.argv[1:]

    if any(a in ("--help", "-h", "help") for a in raw):
        print(__doc__)
        print("Available algorithms:")
        for name, info in sorted(ALGORITHM_REGISTRY.items()):
            print(f"  {name:25s}  {info['description']}")
        print("\nKey parameters (key=value format):")
        print("  algorithm=colony_seednet_v1    Algorithm to use")
        print("  device-target=Ascend           Ascend only")
        print("  extract-dir=...                Dataset path")
        print("  checkpoint-dir=...             Output path")
        print("  num-epochs=300                 Training epochs")
        print("  batch-size=8                   Batch size")
        print("  learning-rate=0.0005           Base learning rate")
        print("  num-workers=8                  DataLoader workers")
        print("  image-size=384                 Input image size")
        print("  max-steps-per-epoch=0          0=full epoch")
        print("  stop-after-first-epoch=0       0=run all")
        print("  execute=0                      0=dry-run (plan only)")
        return

    kv = parse_kv_arguments(raw)

    algorithm = pick_value(kv, ["algorithm", "algo", "model"], "colony_seednet_v1")
    device_target = pick_value(
        kv, ["device-target", "device_target", "device"], "Ascend"
    )
    extract_dir = pick_value(
        kv, ["extract-dir", "extract_dir"], "/cache/dataset/data_extracted"
    )
    checkpoint_dir = pick_value(
        kv, ["checkpoint-dir", "checkpoint_dir"], "/cache/output/model"
    )
    num_epochs = int(pick_value(kv, ["num-epochs", "num_epochs", "epochs"], "300"))
    batch_size = int(pick_value(kv, ["batch-size", "batch_size"], "8"))
    base_lr = float(pick_value(kv, ["learning-rate", "learning_rate", "lr"], "0.0005"))
    num_workers = int(pick_value(kv, ["num-workers", "num_workers"], "8"))
    image_size = int(pick_value(kv, ["image-size", "image_size", "img-size"], "384"))
    max_steps = int(pick_value(kv, ["max-steps-per-epoch", "max_steps_per_epoch"], "0"))
    stop_first = int(
        pick_value(kv, ["stop-after-first-epoch", "stop_after_first_epoch"], "0")
    )
    execute = pick_value(kv, ["execute", "run"], "0") == "1"

    # Validate device
    if device_target.lower() not in ("ascend", "npu"):
        print(
            f"[dispatcher] ERROR: device-target must be 'Ascend', got '{device_target}'",
            file=sys.stderr,
        )
        sys.exit(1)
    device_target = "Ascend"

    # Look up algorithm
    algo_info = get_algorithm_info(algorithm)

    print(f"=== MindSpore Training Dispatcher ===")
    print(f"Algorithm    : {algorithm}")
    print(f"Framework    : {algo_info['framework']}")
    print(f"Base detector: {algo_info['base_detector']}")
    print(f"Device       : {device_target}")
    print(f"Epochs       : {num_epochs}")
    print(f"Batch size   : {batch_size}")
    print(f"LR           : {base_lr}")
    print(f"Image size   : {image_size}")

    # Generate LR schedule
    lr_schedule = generate_warmup_cosine_schedule(
        total_epochs=num_epochs,
        base_lr=base_lr,
        warmup_epochs=5,
        min_lr_ratio=0.01,
    )

    # Algorithm-specific recipe
    recipe: Optional[Dict[str, Any]] = None
    if algorithm == "colony_seednet_v1":
        recipe = generate_colony_seednet_v1_recipe(
            num_epochs=num_epochs,
            base_lr=base_lr,
            batch_size=batch_size,
            image_size=image_size,
            num_workers=num_workers,
        )

    # Downstream command
    downstream = generate_downstream_command(algorithm, algo_info, kv)

    # Training plan
    plan: Dict[str, Any] = {
        "algorithm": algorithm,
        "algorithm_info": algo_info,
        "device_target": device_target,
        "hyperparameters": {
            "num_epochs": num_epochs,
            "batch_size": batch_size,
            "base_lr": base_lr,
            "num_workers": num_workers,
            "image_size": image_size,
            "max_steps_per_epoch": max_steps,
            "stop_after_first_epoch": stop_first,
        },
        "lr_schedule_sample": lr_schedule[: min(10, len(lr_schedule))],
        "lr_schedule_total_epochs": num_epochs,
        "downstream_command": downstream,
        "recipe": recipe,
    }

    # Write training plan
    plan_path = os.path.join(checkpoint_dir, "mindspore_training_plan.json")
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    write_json(plan_path, plan)

    # Write full LR schedule separately
    schedule_path = os.path.join(checkpoint_dir, "lr_schedule.json")
    write_json(schedule_path, lr_schedule)

    # Execute mode
    if execute:
        import subprocess

        print(f"\n[dispatcher] Executing: {' '.join(downstream)}")
        result = subprocess.run(downstream, check=False)
        summary = {
            "algorithm": algorithm,
            "device_target": device_target,
            "exit_code": result.returncode,
            "command": downstream,
        }
        write_json(
            os.path.join(checkpoint_dir, "mindspore_execution_summary.json"), summary
        )
        sys.exit(result.returncode)
    else:
        print(f"\n[dispatcher] Dry-run complete. Plan written to: {plan_path}")
        print(f"[dispatcher] To execute, re-run with execute=1")


if __name__ == "__main__":
    main()

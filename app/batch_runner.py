"""Shared batch inference utilities for GUI and CLI use."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

import cv2

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")


@dataclass
class ImageTask:
    src_path: str
    rel_path: str


@dataclass
class BatchStats:
    processed: int
    skipped: int
    unreadable: int
    total: int
    elapsed: float


ProgressCallback = Callable[[int, int, ImageTask, int, Optional[str]], None]


def discover_images(input_dir: str) -> List[ImageTask]:
    tasks: List[ImageTask] = []
    for root, _, files in os.walk(input_dir):
        for name in sorted(files):
            if not name.lower().endswith(SUPPORTED_EXTENSIONS):
                continue
            abs_path = os.path.join(root, name)
            rel_path = os.path.relpath(abs_path, input_dir)
            tasks.append(ImageTask(src_path=abs_path, rel_path=rel_path))
    return tasks


def ensure_parent_directory(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _save_visualization(detector, task: ImageTask, output_dir: str, overwrite: bool, dry_run: bool) -> Optional[str]:
    dst_path = os.path.join(output_dir, task.rel_path)
    if (not overwrite) and os.path.exists(dst_path) and os.path.getmtime(dst_path) >= os.path.getmtime(task.src_path):
        return None

    bgr = cv2.imread(task.src_path)
    if bgr is None:
        raise FileNotFoundError(task.src_path)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result_rgb = detector.detect_image(rgb)
    result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
    if dry_run:
        return None

    ensure_parent_directory(dst_path)
    cv2.imwrite(dst_path, result_bgr)
    return dst_path


def run_batch(detector,
              input_dir: str,
              output_dir: str,
              *,
              overwrite: bool = True,
              limit: Optional[int] = None,
              dry_run: bool = False,
              silent: bool = False,
              progress_callback: Optional[ProgressCallback] = None) -> BatchStats:
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)

    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    os.makedirs(output_dir, exist_ok=True)

    tasks = discover_images(input_dir)
    if limit is not None:
        tasks = tasks[: max(0, limit)]

    total = len(tasks)
    if total == 0:
        return BatchStats(processed=0, skipped=0, unreadable=0, total=0, elapsed=0.0)

    processed = 0
    skipped = 0
    unreadable = 0
    start_time = time.perf_counter()

    for idx, task in enumerate(tasks, start=1):
        saved_path: Optional[str] = None
        box_count = 0
        try:
            dst_path = os.path.join(output_dir, task.rel_path)
            if (not overwrite) and os.path.exists(dst_path) and os.path.getmtime(dst_path) >= os.path.getmtime(task.src_path):
                skipped += 1
                saved_path = None
                if not silent:
                    print(f"[{idx}/{total}] skip (up-to-date) {task.rel_path}")
            else:
                bgr = cv2.imread(task.src_path)
                if bgr is None:
                    unreadable += 1
                    if not silent:
                        print(f"[{idx}/{total}] unable to read {task.rel_path}")
                    continue

                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                result_rgb = detector.detect_image(rgb)
                box_count = len(getattr(detector, "last_boxes", []))
                if not dry_run:
                    result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
                    ensure_parent_directory(dst_path)
                    cv2.imwrite(dst_path, result_bgr)
                    saved_path = dst_path
                processed += 1
                if not silent:
                    action = "saved" if not dry_run else "dry-run"
                    print(f"[{idx}/{total}] {action} {task.rel_path} boxes={box_count}")
        except Exception as exc:
            unreadable += 1
            saved_path = None
            if not silent:
                print(f"[{idx}/{total}] error processing {task.rel_path}: {exc}")
        finally:
            if progress_callback:
                progress_callback(idx, total, task, box_count, saved_path)

    elapsed = time.perf_counter() - start_time
    return BatchStats(processed=processed, skipped=skipped, unreadable=unreadable, total=total, elapsed=elapsed)

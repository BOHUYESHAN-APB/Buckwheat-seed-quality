import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path


CLASS_NAMES = ["T_AB", "T_C", "K_AB", "K_C", "D"]
VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def dominant_label_from_json(json_path: Path) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    counts = defaultdict(int)
    for shape in data.get("shapes", []):
        label = shape.get("label")
        if label in CLASS_NAMES:
            counts[label] += 1
    if not counts:
        raise ValueError(f"No valid labels found in {json_path}")
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def find_paired_image(images_dir: Path, stem: str) -> Path | None:
    for ext in VALID_IMAGE_EXTS:
        candidate = images_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def stratified_split(groups: dict[str, list[str]], seed: int):
    rng = random.Random(seed)
    splits = {"train": [], "val": [], "test": []}

    for label, stems in sorted(groups.items()):
        items = list(stems)
        rng.shuffle(items)
        n = len(items)

        if n >= 5:
            test_n = max(1, round(n * 0.2))
            val_n = max(1, round(n * 0.15))
        elif n == 4:
            test_n, val_n = 1, 1
        elif n == 3:
            test_n, val_n = 1, 1
        elif n == 2:
            test_n, val_n = 1, 0
        else:
            test_n, val_n = 0, 0

        if test_n + val_n >= n:
            if n >= 2:
                test_n = 1
                val_n = max(0, n - test_n - 1)
            else:
                test_n = 0
                val_n = 0

        train_n = n - test_n - val_n
        if train_n <= 0:
            train_n = 1
            if val_n > 0:
                val_n -= 1
            elif test_n > 0:
                test_n -= 1

        splits["train"].extend(items[:train_n])
        splits["val"].extend(items[train_n:train_n + val_n])
        splits["test"].extend(items[train_n + val_n:train_n + val_n + test_n])

    for split_items in splits.values():
        rng.shuffle(split_items)
    return splits


def copy_split_files(stems, images_src: Path, labels_src: Path, out_root: Path, split_name: str):
    img_out = out_root / "images" / split_name
    lbl_out = out_root / "labels" / split_name
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    for stem in stems:
        image_path = find_paired_image(images_src, stem)
        label_path = labels_src / f"{stem}.txt"
        if image_path is None:
            raise FileNotFoundError(f"Missing image for {stem}")
        if not label_path.exists():
            raise FileNotFoundError(f"Missing label for {stem}")
        shutil.copy2(image_path, img_out / image_path.name)
        shutil.copy2(label_path, lbl_out / label_path.name)


def write_data_yaml(out_root: Path):
    yaml_lines = [
        "path: .",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        f"nc: {len(CLASS_NAMES)}",
        "names:",
    ]
    yaml_lines.extend(f"  {idx}: {name}" for idx, name in enumerate(CLASS_NAMES))
    (out_root / "data.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")


def write_split_manifest(out_root: Path, split_map: dict[str, list[str]], label_map: dict[str, str]):
    lines = []
    for split_name in ("train", "val", "test"):
        lines.append(f"[{split_name}]")
        for stem in split_map[split_name]:
            lines.append(f"{stem},{label_map[stem]}")
        lines.append("")
    (out_root / "split_manifest.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Split YOLO dataset into train/val/test using image-level dominant labels.")
    parser.add_argument("--images", required=True, help="Source images directory")
    parser.add_argument("--json-src", required=True, help="Original X-AnyLabeling json directory")
    parser.add_argument("--labels", required=True, help="Source YOLO label directory")
    parser.add_argument("--out", required=True, help="Output split dataset directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    images_dir = Path(args.images)
    json_dir = Path(args.json_src)
    labels_dir = Path(args.labels)
    out_root = Path(args.out)

    out_root.mkdir(parents=True, exist_ok=True)

    groups = defaultdict(list)
    label_map = {}
    for json_path in sorted(json_dir.glob("*.json")):
        stem = json_path.stem
        label = dominant_label_from_json(json_path)
        groups[label].append(stem)
        label_map[stem] = label

    split_map = stratified_split(groups, args.seed)

    for split_name, stems in split_map.items():
        copy_split_files(stems, images_dir, labels_dir, out_root, split_name)

    write_data_yaml(out_root)
    write_split_manifest(out_root, split_map, label_map)

    for split_name in ("train", "val", "test"):
        print(f"{split_name}_count={len(split_map[split_name])}")
        stats = defaultdict(int)
        for stem in split_map[split_name]:
            stats[label_map[stem]] += 1
        for cls in CLASS_NAMES:
            print(f"{split_name}_{cls}={stats[cls]}")


if __name__ == "__main__":
    main()

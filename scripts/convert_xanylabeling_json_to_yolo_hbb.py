import argparse
import json
from pathlib import Path


CLASS_NAMES = ["T_AB", "T_C", "K_AB", "K_C", "D"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def clamp(value, low, high):
    return max(low, min(high, value))


def points_to_xyxy(shape):
    points = shape.get("points") or []
    if not points:
        raise ValueError("shape has no points")

    shape_type = shape.get("shape_type")
    if shape_type == "rectangle":
        if len(points) < 2:
            raise ValueError("rectangle needs at least 2 points")
        xs = [float(pt[0]) for pt in points]
        ys = [float(pt[1]) for pt in points]
    elif shape_type == "cuboid":
        if len(points) < 4:
            raise ValueError("cuboid needs at least 4 front-face points")
        xs = [float(pt[0]) for pt in points[:4]]
        ys = [float(pt[1]) for pt in points[:4]]
    else:
        raise ValueError(f"unsupported shape_type: {shape_type}")

    x1 = min(xs)
    x2 = max(xs)
    y1 = min(ys)
    y2 = max(ys)
    return x1, y1, x2, y2


def xyxy_to_yolo(x1, y1, x2, y2, width, height):
    x1 = clamp(x1, 0.0, float(width))
    x2 = clamp(x2, 0.0, float(width))
    y1 = clamp(y1, 0.0, float(height))
    y2 = clamp(y2, 0.0, float(height))

    if x2 <= x1 or y2 <= y1:
        return None

    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return cx, cy, bw, bh


def convert_one(json_path: Path, output_dir: Path):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    image_width = int(data["imageWidth"])
    image_height = int(data["imageHeight"])

    lines = []
    warnings = []

    for idx, shape in enumerate(data.get("shapes", []), start=1):
        label = shape.get("label")
        if label not in CLASS_TO_ID:
            warnings.append(f"{json_path.name}: skip shape {idx}, unknown label {label!r}")
            continue

        try:
            x1, y1, x2, y2 = points_to_xyxy(shape)
        except ValueError as exc:
            warnings.append(f"{json_path.name}: skip shape {idx}, {exc}")
            continue

        box = xyxy_to_yolo(x1, y1, x2, y2, image_width, image_height)
        if box is None:
            warnings.append(f"{json_path.name}: skip shape {idx}, invalid clamped box")
            continue

        cx, cy, bw, bh = box
        class_id = CLASS_TO_ID[label]
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{json_path.stem}.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path, warnings, len(lines)


def main():
    parser = argparse.ArgumentParser(description="Convert X-AnyLabeling JSON rectangle labels to YOLO HBB txt labels.")
    parser.add_argument("--src", required=True, help="Directory containing image+json pairs from X-AnyLabeling")
    parser.add_argument("--out", required=True, help="Output directory for YOLO txt labels")
    args = parser.parse_args()

    src_dir = Path(args.src)
    out_dir = Path(args.out)

    if not src_dir.is_dir():
        raise SystemExit(f"Source directory does not exist: {src_dir}")

    json_files = sorted(src_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No json files found in: {src_dir}")

    converted = 0
    total_boxes = 0
    all_warnings = []

    for json_path in json_files:
        image_path = None
        for ext in VALID_IMAGE_EXTS:
            candidate = src_dir / f"{json_path.stem}{ext}"
            if candidate.exists():
                image_path = candidate
                break

        if image_path is None:
            all_warnings.append(f"{json_path.name}: missing paired image file")
            continue

        _, warnings, line_count = convert_one(json_path, out_dir)
        converted += 1
        total_boxes += line_count
        all_warnings.extend(warnings)

    print(f"converted_json_files={converted}")
    print(f"total_boxes={total_boxes}")
    print(f"output_dir={out_dir}")
    if all_warnings:
        print("warnings:")
        for item in all_warnings:
            print(item)


if __name__ == "__main__":
    main()

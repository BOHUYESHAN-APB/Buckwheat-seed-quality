from pathlib import Path
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/export_openi_best_to_onnx.py <best.pt> [imgsz]")

    best_pt = Path(sys.argv[1]).resolve()
    imgsz = int(sys.argv[2]) if len(sys.argv) > 2 else 960
    repo_root = Path(__file__).resolve().parents[1]
    vendor_root = repo_root / "temp" / "openi_code_repo"
    if str(vendor_root) not in sys.path:
        sys.path.insert(0, str(vendor_root))

    from ultralytics import YOLO  # type: ignore

    model = YOLO(str(best_pt))
    exported = Path(model.export(format="onnx", imgsz=imgsz, simplify=True, dynamic=False)).resolve()
    print(exported)


if __name__ == "__main__":
    main()

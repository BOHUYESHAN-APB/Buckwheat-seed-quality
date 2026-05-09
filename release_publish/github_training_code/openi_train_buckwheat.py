import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def parse_value(text):
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"none", "null"}:
        return None
    try:
        if any(ch in text for ch in (".", "e", "E")):
            return float(text)
        return int(text)
    except ValueError:
        return text


def parse_args(argv):
    defaults = {
        "data_url": "",
        "train_url": "",
        "data_yaml": "",
        "model": "yolo26n-p2.yaml",
        "epochs": 120,
        "imgsz": 960,
        "batch": 16,
        "workers": 8,
        "patience": 30,
        "optimizer": "AdamW",
        "lr0": 0.001,
        "lrf": 0.01,
        "degrees": 15.0,
        "translate": 0.08,
        "scale": 0.35,
        "fliplr": 0.5,
        "flipud": 0.0,
        "mosaic": 1.0,
        "mixup": 0.05,
        "close_mosaic": 10,
        "device": "",
        "project": "runs",
        "name": "buckwheat_yolo26n",
        "seed": 42,
        "amp": False,
        "export_onnx": True,
        "export_formats": "onnx",
    }

    parser = argparse.ArgumentParser(add_help=False)
    for key in defaults:
        option_strings = [f"--{key}"]
        hyphen_key = key.replace('_', '-')
        if hyphen_key != key:
            option_strings.insert(0, f"--{hyphen_key}")
        parser.add_argument(*option_strings)

    known, unknown = parser.parse_known_args(argv[1:])
    args = defaults.copy()

    for key, value in vars(known).items():
        if value is not None:
            args[key.replace('-', '_')] = parse_value(str(value))

    pending_key = None
    for raw in unknown:
        if pending_key is not None:
            args[pending_key] = parse_value(raw)
            pending_key = None
            continue

        if raw.startswith("--"):
            pending_key = raw[2:].replace("-", "_")
            continue

        if "=" in raw:
            key, value = raw.split("=", 1)
            args[key.lstrip("-").replace("-", "_")] = parse_value(value)
            continue

    env_key_map = {
        "data_url": ["data_url", "DATA_URL"],
        "train_url": ["train_url", "TRAIN_URL"],
    }
    for key, env_names in env_key_map.items():
        if args.get(key):
            continue
        for env_name in env_names:
            env_value = os.environ.get(env_name, "").strip()
            if env_value:
                args[key] = env_value
                break

    return args


def prepare_openi_context(args):
    context = None
    try:
        from c2net.context import prepare  # type: ignore

        context = prepare()
        code_root = Path(context.code_path) / REPO_ROOT.name.lower()
        dataset_root = Path(context.dataset_path)
        output_root = Path(context.output_path)

        args["data_url"] = args["data_url"] or str(dataset_root)
        args["train_url"] = args["train_url"] or str(output_root)

        print(f"C2NET_CODE_PATH={code_root}")
        print(f"C2NET_DATASET_PATH={dataset_root}")
        print(f"C2NET_OUTPUT_PATH={output_root}")
    except Exception as exc:
        print(f"C2NET_PREPARE_SKIPPED={exc}")
    return context


def resolve_openi_dataset_root(root: Path):
    if (root / "buckweet").exists():
        return root / "buckweet"
    if (root / "buckwheat").exists():
        return root / "buckwheat"
    return root


def resolve_data_yaml(data_url: str, data_yaml: str):
    if data_yaml:
        candidate = Path(data_yaml)
        if candidate.exists():
            return candidate.resolve()
        raise FileNotFoundError(f"data_yaml not found: {data_yaml}")

    if not data_url:
        raise FileNotFoundError("Missing data_url and data_yaml")

    root = resolve_openi_dataset_root(Path(data_url))
    direct = root / "data.yaml"
    if direct.exists():
        return direct.resolve()

    nested = root / "yolo_split" / "data.yaml"
    if nested.exists():
        return nested.resolve()

    found = sorted(root.rglob("data.yaml"))
    if found:
        return found[0].resolve()

    raise FileNotFoundError(f"No data.yaml found under {root}")


def materialize_absolute_data_yaml(data_yaml: Path, runtime_root: Path):
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    dataset_root = data_yaml.parent.resolve()

    abs_data = dict(data)
    abs_data["path"] = str(dataset_root)

    for key in ("train", "val", "test", "minival"):
        value = abs_data.get(key)
        if not value:
            continue
        if isinstance(value, str):
            abs_data[key] = str((dataset_root / value).resolve())
        else:
            abs_data[key] = [str((dataset_root / item).resolve()) for item in value]

    absolute_yaml = runtime_root / "data.absolute.yaml"
    absolute_yaml.write_text(yaml.safe_dump(abs_data, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return absolute_yaml.resolve()


def ensure_dir(path_str: str):
    path = Path(path_str).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_runtime_environment(train_root_str: str):
    train_root = ensure_dir(train_root_str)
    runtime_root = ensure_dir(str(train_root / ".openi_runtime"))
    os.environ["YOLO_CONFIG_DIR"] = str(runtime_root)
    os.environ.setdefault("HF_HOME", str(runtime_root / "hf_home"))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(runtime_root / "hf_cache"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(runtime_root / "transformers_cache"))
    os.environ.setdefault("TORCH_HOME", str(runtime_root / "torch_home"))
    os.environ.setdefault("XDG_CACHE_HOME", str(runtime_root / "xdg_cache"))
    return train_root, runtime_root


def import_yolo():
    package_dir = REPO_ROOT / "ultralytics"
    if not package_dir.exists():
        raise FileNotFoundError(
            f"Local ultralytics package directory is missing: {package_dir}. "
            "The OpenI code repository must include the full ultralytics source tree."
        )

    try:
        from ultralytics import YOLO  # type: ignore

        return YOLO
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Failed to import local ultralytics package. Ensure the full repository was uploaded, not only the entry script."
        ) from exc


def export_best_onnx(best_pt: Path, imgsz: int, yolo_cls):
    model = yolo_cls(str(best_pt))
    return Path(model.export(format="onnx", imgsz=imgsz, simplify=True, dynamic=False))


def parse_export_formats(value):
    if value is None:
        return []
    if isinstance(value, str):
        items = [item.strip().lower() for item in value.split(",") if item.strip()]
        return [item for item in items if item not in {"none", "null", "false", "off"}]
    return []


def export_model_variants(best_pt: Path, imgsz: int, yolo_cls, formats, export_root: Path):
    exported = {}
    if not best_pt.exists() or not formats:
        return exported

    export_root.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        try:
            model = yolo_cls(str(best_pt))
            output = Path(model.export(format=fmt, imgsz=imgsz, simplify=(fmt == "onnx"), dynamic=False)).resolve()
            target = export_root / output.name
            if output != target:
                shutil.copy2(output, target)
            exported[fmt] = str(target.resolve())
            print(f"EXPORT_OK[{fmt}]={target}")
        except Exception as exc:
            print(f"EXPORT_FAILED[{fmt}]={exc}")
    return exported


def collect_handoff_artifacts(save_dir: Path, data_yaml: Path, absolute_data_yaml: Path, args: dict, exported_files: dict):
    handoff_dir = save_dir / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    weights_dir = save_dir / "weights"
    tracked_files = {}

    copy_map = {
        "best_pt": weights_dir / "best.pt",
        "last_pt": weights_dir / "last.pt",
        "results_csv": save_dir / "results.csv",
        "args_yaml": save_dir / "args.yaml",
        "original_data_yaml": data_yaml,
        "absolute_data_yaml": absolute_data_yaml,
        "train_entry": REPO_ROOT / "openi_train_buckwheat.py",
        "training_notes": REPO_ROOT / "OPENI_TRAINING.md",
    }

    model_path = str(args.get("model", "")).strip()
    if model_path.endswith(".yaml"):
        candidate = REPO_ROOT / model_path
        if candidate.exists():
            copy_map["model_yaml"] = candidate

    for key, source in copy_map.items():
        if not source.exists():
            continue
        target = handoff_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        tracked_files[key] = str(target.resolve())

    exports_dir = handoff_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    exported_manifest = {}
    for fmt, src in exported_files.items():
        source = Path(src)
        if not source.exists():
            continue
        target = exports_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        exported_manifest[fmt] = str(target.resolve())

    classes = []
    try:
        raw_data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
        names = raw_data.get("names", {})
        if isinstance(names, dict):
            classes = [names[idx] for idx in sorted(names)]
        elif isinstance(names, list):
            classes = list(names)
    except Exception:
        classes = []

    classes_path = handoff_dir / "class_names.json"
    classes_path.write_text(json.dumps(classes, indent=2, ensure_ascii=False), encoding="utf-8")
    tracked_files["class_names"] = str(classes_path.resolve())

    manifest = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "save_dir": str(save_dir),
        "weights_dir": str(weights_dir),
        "tracked_files": tracked_files,
        "exported_files": exported_manifest,
        "classes": classes,
        "args": args,
    }
    manifest_path = handoff_dir / "handoff_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"HANDOFF_DIR={handoff_dir}")
    print(f"HANDOFF_MANIFEST={manifest_path}")
    return handoff_dir, manifest_path, exported_manifest


def patch_ultralytics_results_reader():
    from ultralytics.engine.trainer import BaseTrainer  # type: ignore
    from ultralytics.engine import trainer as trainer_module  # type: ignore
    from ultralytics.utils import LOGGER  # type: ignore

    def read_results_csv_fallback(self):
        try:
            import polars as pl  # type: ignore

            return pl.read_csv(self.csv, infer_schema_length=None).to_dict(as_series=False)
        except Exception:
            if not Path(self.csv).exists():
                return {}
            try:
                with open(self.csv, "r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                if not rows:
                    return {}
                keys = rows[0].keys()
                return {key: [row.get(key) for row in rows] for key in keys}
            except Exception:
                return {}

    BaseTrainer.read_results_csv = read_results_csv_fallback

    def plot_results_fallback(*args, **kwargs):
        try:
            from ultralytics.utils.plotting import plot_results as original_plot_results  # type: ignore

            return original_plot_results(*args, **kwargs)
        except ModuleNotFoundError as exc:
            if getattr(exc, "name", "") == "polars":
                LOGGER.warning("Skipping results.png plotting because 'polars' is unavailable in this image.")
                return None
            raise

    trainer_module.plot_results = plot_results_fallback


def main(argv=None):
    argv = argv or sys.argv
    args = parse_args(argv)
    c2net_context = prepare_openi_context(args)

    train_root, runtime_root = configure_runtime_environment(str(args["train_url"] or (REPO_ROOT / "outputs")))

    YOLO = import_yolo()
    patch_ultralytics_results_reader()

    data_yaml = resolve_data_yaml(str(args["data_url"]), str(args["data_yaml"]))
    absolute_data_yaml = materialize_absolute_data_yaml(data_yaml, runtime_root)
    project_root = train_root / str(args["project"])
    project_root.mkdir(parents=True, exist_ok=True)

    print(f"OPENI_REPO_ROOT={REPO_ROOT}")
    print(f"OPENI_RUNTIME_ROOT={runtime_root}")
    print(f"OPENI_DATA_ROOT={data_yaml.parent}")
    print(f"OPENI_DATA_YAML={data_yaml}")
    print(f"OPENI_ABS_DATA_YAML={absolute_data_yaml}")
    print(f"OPENI_TRAIN_ROOT={train_root}")
    print("BOOT_FILE=openi_train_buckwheat.py")
    print(f"HF_ENDPOINT={os.environ.get('HF_ENDPOINT', '')}")

    model = YOLO(str(args["model"]))
    default_save_dir = (project_root / str(args["name"])).resolve()
    result = None
    train_exception = None
    try:
        result = model.train(
            data=str(absolute_data_yaml),
            model=str(args["model"]),
            epochs=int(args["epochs"]),
            imgsz=int(args["imgsz"]),
            batch=int(args["batch"]),
            workers=int(args["workers"]),
            patience=int(args["patience"]),
            optimizer=str(args["optimizer"]),
            lr0=float(args["lr0"]),
            lrf=float(args["lrf"]),
            degrees=float(args["degrees"]),
            translate=float(args["translate"]),
            scale=float(args["scale"]),
            fliplr=float(args["fliplr"]),
            flipud=float(args["flipud"]),
            mosaic=float(args["mosaic"]),
            mixup=float(args["mixup"]),
            close_mosaic=int(args["close_mosaic"]),
            seed=int(args["seed"]),
            amp=bool(args["amp"]),
            project=str(project_root),
            name=str(args["name"]),
            exist_ok=True,
            save=True,
            plots=True,
            verbose=True,
            device=(None if str(args["device"]).strip() == "" else str(args["device"])),
        )
    except Exception as exc:
        train_exception = exc
        print(f"TRAIN_EXCEPTION={exc}")

    save_dir = Path(result.save_dir).resolve() if result is not None else default_save_dir
    best_pt = save_dir / "weights" / "best.pt"
    export_formats = parse_export_formats(args.get("export_formats"))
    if bool(args.get("export_onnx")) and "onnx" not in export_formats:
        export_formats.insert(0, "onnx")
    exported_files = export_model_variants(best_pt, int(args["imgsz"]), YOLO, export_formats, save_dir / "exports")
    best_onnx = exported_files.get("onnx", "")

    handoff_dir, handoff_manifest_path, exported_manifest = collect_handoff_artifacts(
        save_dir, data_yaml, absolute_data_yaml, args, exported_files
    )

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(REPO_ROOT),
        "data_yaml": str(data_yaml),
        "absolute_data_yaml": str(absolute_data_yaml),
        "train_root": str(train_root),
        "save_dir": str(save_dir),
        "best_pt": str(best_pt) if best_pt.exists() else "",
        "best_onnx": str(best_onnx) if best_onnx else "",
        "exported_files": exported_manifest,
        "handoff_dir": str(handoff_dir),
        "handoff_manifest": str(handoff_manifest_path),
        "args": args,
        "used_c2net": c2net_context is not None,
    }
    summary_path = save_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"RUN_SUMMARY={summary_path}")

    if c2net_context is not None:
        try:
            from c2net.context import upload_output  # type: ignore

            upload_output()
            print("C2NET_UPLOAD_OUTPUT=OK")
        except Exception as exc:
            print(f"C2NET_UPLOAD_OUTPUT_SKIPPED={exc}")

    if train_exception is not None and not best_pt.exists():
        raise train_exception


if __name__ == "__main__":
    main()

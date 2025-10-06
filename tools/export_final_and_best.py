#!/usr/bin/env python
"""Export both the *final* and *best* checkpoints into inference models.

This script wraps ``PaddleDetection/tools/export_model.py`` so that we can
consistently export the two most常用的模型快照：

* ``model_final.pdparams`` —— 训练完成时的最终权重
* ``best_model.pdparams`` —— 依据验证指标自动保存的 best 模型

默认假定上述文件位于 ``output/`` 目录，可通过命令行参数重写。

Examples
--------
导出到 ``exports/`` 目录，并附带 FP16 与多线程示例参数：

```
python tools/export_final_and_best.py \
    --config PaddleDetection/configs/ppyoloe/ppyoloe_plus_crn_l_300e_coco.yml \
    --paddledet-root PaddleDetection \
    --output-root exports \
    --extra-opts use_gpu=false --extra-opts trt=True
```

必要依赖：
- Python >= 3.8
- PaddleDetection 子模块或目录完整可用
- PaddlePaddle 与 PaddleDetection 导出的运行环境一致
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the PaddleDetection config used during training",
    )
    parser.add_argument(
        "--paddledet-root",
        type=Path,
        default=Path("PaddleDetection"),
        help="Root directory of PaddleDetection (default: ./PaddleDetection)",
    )
    parser.add_argument(
        "--weights-root",
        type=Path,
        default=Path("output"),
        help="Directory containing model_final.pdparams & best_model.pdparams",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("exports"),
        help="Directory to store exported inference models (default: ./exports)",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python interpreter used to call export_model.py",
    )
    parser.add_argument(
        "--extra-opts",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional -o key=value options forwarded to export_model.py (can repeat)",
    )
    parser.add_argument(
        "--skip-final",
        action="store_true",
        help="Only export best_model, skip model_final",
    )
    parser.add_argument(
        "--skip-best",
        action="store_true",
        help="Only export model_final, skip best_model",
    )
    parser.add_argument(
        "--export-onnx",
        action="store_true",
        help="After exporting Paddle inference models, also convert them to ONNX",
    )
    parser.add_argument(
        "--onnx-opset",
        type=int,
        default=13,
        help="ONNX opset version when --export-onnx is enabled (default: 13)",
    )
    parser.add_argument(
        "--onnx-output-name",
        default="model.onnx",
        help="Output filename for the exported ONNX model (default: model.onnx)",
    )
    parser.add_argument(
        "--onnx-extra-args",
        action="append",
        default=[],
        metavar="ARG",
        help="Extra arguments forwarded to paddle2onnx.command (e.g. --onnx-extra-args --enable_onnx_checker False)",
    )
    return parser.parse_args(argv)


def _ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")


def _inject_default_opts(extra_opts: Iterable[str]) -> List[str]:
    """Guarantee essential -o options are present.

    ``export_model.py`` 默认假设 GPU 环境；若用户尚未安装
    paddlepaddle-gpu，则需要显式设置 ``use_gpu=false``。为了减少
    报错，这里在未指定 ``use_gpu`` 时自动追加该选项。
    """

    seen_keys = {opt.split("=", 1)[0].strip() for opt in extra_opts if "=" in opt}
    normalized = list(extra_opts)
    if "use_gpu" not in seen_keys:
        normalized.append("use_gpu=false")
    return normalized


def build_command(
    python_bin: Path,
    export_script: Path,
    config: Path,
    weights: Path,
    output_dir: Path,
    extra_opts: Iterable[str],
) -> List[str]:
    cmd: List[str] = [str(python_bin), str(export_script), "-c", str(config)]
    cmd += ["--output_dir", str(output_dir)]
    option_args = [f"weights={weights}"]
    option_args.extend(_inject_default_opts(extra_opts))
    for kv in option_args:
        cmd += ["-o", kv]
    return cmd


def run_export(tag: str, args: argparse.Namespace, weights: Path) -> Path:
    export_script = args.paddledet_root / "tools" / "export_model.py"
    _ensure_exists(export_script, "export_model.py")

    output_dir = args.output_root / tag
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_command(
        python_bin=args.python,
        export_script=export_script,
        config=args.config,
        weights=weights,
        output_dir=output_dir,
        extra_opts=args.extra_opts,
    )

    print(f"\n[Export] {tag}: executing {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    pdmodel_files = sorted(output_dir.glob("**/*.pdmodel"))
    if not pdmodel_files:
        raise FileNotFoundError(f"No .pdmodel found under {output_dir}")
    return pdmodel_files[0].parent


def run_onnx_export(
    tag: str,
    python_bin: Path,
    model_dir: Path,
    opset_version: int,
    onnx_output_name: str,
    extra_args: Iterable[str],
) -> Path:
    onnx_path = model_dir / onnx_output_name
    cmd: List[str] = [
        str(python_bin),
        "-m",
        "paddle2onnx.command",
        "--model_dir",
        str(model_dir),
        "--model_filename",
        "model.pdmodel",
        "--params_filename",
        "model.pdiparams",
        "--save_file",
        str(onnx_path),
        "--opset_version",
        str(opset_version),
    ]
    if extra_args:
        cmd.extend(extra_args)

    print(f"[ONNX] {tag}: executing {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return onnx_path


def main(argv: Iterable[str]) -> None:
    args = parse_args(argv)

    tasks = []
    if not args.skip_final:
        tasks.append(("final", args.weights_root / "model_final.pdparams"))
    if not args.skip_best:
        tasks.append(("best", args.weights_root / "best_model.pdparams"))

    if not tasks:
        raise SystemExit("Nothing to export: both --skip-final and --skip-best were specified.")

    _ensure_exists(args.config, "Config file")
    _ensure_exists(args.paddledet_root, "PaddleDetection root")
    _ensure_exists(args.weights_root, "Weights root")

    onnx_targets = []
    for tag, weight_path in tasks:
        _ensure_exists(weight_path, f"{tag} weights")
        model_dir = run_export(tag, args, weight_path)
        onnx_targets.append((tag, model_dir))

    if args.export_onnx:
        for tag, model_dir in onnx_targets:
            run_onnx_export(
                tag=tag,
                python_bin=args.python,
                model_dir=model_dir,
                opset_version=args.onnx_opset,
                onnx_output_name=args.onnx_output_name,
                extra_args=args.onnx_extra_args,
            )

    print("\n[Done] Export finished. Inference models stored under:")
    for tag, _ in tasks:
        print(f"  - {args.output_root / tag}")
    if args.export_onnx:
        print("Also generated ONNX models:")
        for tag, model_dir in onnx_targets:
            print(f"  - {model_dir / args.onnx_output_name}")


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])

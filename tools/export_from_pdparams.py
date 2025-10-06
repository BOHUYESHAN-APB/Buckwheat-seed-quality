#!/usr/bin/env python3
"""
tools/export_from_pdparams.py

用途：
- 尝试从训练产物（.pdparams / .pdparams 文件）恢复模型并导出推理模型（model.pdmodel + model.pdiparams），
  or 导出 paddle.jit 可用的静态/动态图模型（根据用户提供的模型类）。

流程：
1. 若仓库中存在 PaddleDetection 导出脚本（含 ppdet/ 或 tools/export_model.py），尝试调用该导出工具。
2. 否则，若用户指定了模型类路径（module:ClassName），脚本会：
   - 动态 import 模型类
   - 实例化模型（需用户在模型类支持无参或可接受配置）
   - 用 paddle.load 加载参数并 set_state_dict（或 model.set_state_dict）
   - 使用 paddle.jit.save 导出可用于推理的模型（注意：需要 PaddlePaddle 环境）
3. 提供清晰的错误提示和建议步骤。

示例：
python tools/export_from_pdparams.py --pdparams output/best_model.pdparams --out_dir inference_model/
python tools/export_from_pdparams.py --pdparams output/best_model.pdparams --model_class "my_model.Net" --out_dir inference_model/
"""

import argparse
import os
import sys
import subprocess
import json
import importlib
from pathlib import Path

def find_paddledetection_root(search_root: Path = Path(".")) -> Path:
    """在工作区搜索包含 ppdet 包或 export 脚本的目录"""
    # 优先查找典型目录名
    candidates = ["PaddleDetection", "paddledetection", "PaddleDetection_package", "PaddleDetection-main"]
    for c in candidates:
        p = search_root / c
        if p.exists():
            # 进一步确认是否含 ppdet 包或 tools/export_model.py
            if (p / "ppdet").exists() or any((p / "tools").glob("*export*")):
                return p
    # 广泛搜索包含 ppdet 文件夹的目录
    for p in search_root.rglob("ppdet"):
        return p.parent
    return None

def try_call_pd_export(pd_root: Path, pdparams: str, out_dir: str) -> bool:
    """
    尝试调用 PaddleDetection 的导出脚本。
    支持多种常见参数名（--weights / --trained_model / --checkpoint）。
    返回 True 表示已尝试并成功返回 0。
    """
    print(f"尝试使用 PaddleDetection 导出工具，根目录: {pd_root}")
    tools_dirs = [pd_root / "tools", pd_root / "deploy", pd_root]
    script_candidates = []
    for d in tools_dirs:
        if d.exists():
            # 常见导出脚本名
            for name in ["export_model.py", "tools/export_model.py", "deploy/export_model.py", "tools/export_model"]:
                p = d / Path(name)
                if p.exists():
                    script_candidates.append(p)
            # 也搜寻包含 export 关键词的脚本
            for p in d.glob("*export*.py"):
                script_candidates.append(p)

    script_candidates = list(dict.fromkeys(script_candidates))  # unique

    if not script_candidates:
        print("未在 PaddleDetection 根目录找到导出脚本。")
        return False

    for script in script_candidates:
        script = script.resolve()
        print(f"尝试调用脚本: {script}")
        # 尝试常见参数组合
        arg_sets = [
            ["--weights", pdparams, "--output_dir", out_dir],
            ["--trained_model", pdparams, "--output_dir", out_dir],
            ["--checkpoint", pdparams, "--output_dir", out_dir],
            ["--weights", pdparams, "--save_dir", out_dir],
        ]
        for args in arg_sets:
            cmd = [sys.executable, str(script)] + args
            print("运行:", " ".join(cmd))
            try:
                res = subprocess.run(cmd, check=True, cwd=str(pd_root))
                if res.returncode == 0:
                    print("导出脚本执行成功。请检查输出目录:", out_dir)
                    return True
            except subprocess.CalledProcessError as e:
                print("脚本返回非零码，继续尝试其它参数/脚本。 错误:", e)
            except Exception as e:
                print("调用脚本失败:", e)
    return False

def export_via_model_class(pdparams: str, model_class: str, out_dir: str, device: str = "cpu"):
    """
    使用用户提供的模型类从 .pdparams 恢复并导出 paddle.jit 保存模型。
    model_class 格式： "module.submodule:ClassName" 或 "module.submodule.ClassName"
    """
    try:
        import paddle
        import paddle.nn as nn
    except Exception as e:
        print("需要安装 PaddlePaddle 才能通过模型类导出，错误：", e)
        return False

    if ":" in model_class:
        mod_path, cls_name = model_class.split(":", 1)
    elif "." in model_class:
        *mods, cls_name = model_class.split(".")
        mod_path = ".".join(mods)
    else:
        raise ValueError("model_class 格式非法，应为 module.ClassName 或 module:ClassName")

    print(f"导入模型类: module={mod_path} class={cls_name}")
    try:
        mod = importlib.import_module(mod_path)
        ModelCls = getattr(mod, cls_name)
    except Exception as e:
        print("导入模型类失败：", e)
        return False

    # 实例化模型（若需要 kwargs，可改造脚本以接收配置文件）
    print("尝试用无参/默认参数实例化模型...")
    try:
        model = ModelCls()
    except Exception as e:
        print("模型实例化失败，请提供可接受的构造参数或在脚本中修改。错误：", e)
        return False

    # 加载参数
    pdparams = Path(pdparams)
    if not pdparams.exists():
        print("找不到 pdparams 文件：", pdparams)
        return False

    try:
        state = paddle.load(str(pdparams))
        # 兼容 state 可能为 dict 或 OrderedDict
        if isinstance(state, dict):
            # 如果是保存了 'state_dict' 的结构
            if "state_dict" in state:
                state = state["state_dict"]
        # set_state_dict 可能在不同模型实例上命名不同
        try:
            model.set_state_dict(state)
        except Exception as e:
            print("model.set_state_dict 失败，尝试 model.load_dict ... 错误：", e)
            try:
                model.load_dict(state)
            except Exception as e2:
                print("加载参数失败：", e2)
                return False

        model.eval()
        # 导出 paddle.jit 保存（静态/动态图皆可）
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        save_path = out_dir / "inference_jit_model"
        print("使用 paddle.jit.save 导出模型到：", save_path)
        try:
            # 包装为示例输入的保存流程（以 NCHW float32 为例）
            import numpy as np
            dummy = np.zeros([1, 3, 640, 640], dtype="float32")
            # 转为 Paddle Tensor
            model_input = paddle.to_tensor(dummy)
            # 若模型是 Layer 子类，直接调用 paddle.jit.save
            paddle.jit.save(layer=model, path=str(save_path))
            print("导出完成（paddle.jit.save）。请在 out_dir 中检查输出文件。")
            return True
        except Exception as e:
            print("paddle.jit.save 导出失败：", e)
            return False

    except Exception as e:
        print("加载 pdparams 失败：", e)
        return False

def main():
    parser = argparse.ArgumentParser(description="从 .pdparams 恢复并导出推理模型的尝试脚本")
    parser.add_argument("--pdparams", required=True, help="训练产物文件路径（.pdparams）")
    parser.add_argument("--out_dir", required=True, help="导出推理模型的输出目录（例如: inference_model/）")
    parser.add_argument("--paddledet_root", default=None, help="PaddleDetection 源码根目录（若已解压）")
    parser.add_argument("--model_class", default=None, help="若不能使用 PaddleDetection 导出脚本，提供模型类路径 module.ClassName 或 module:ClassName")
    parser.add_argument("--device", default="cpu", help="设备: cpu 或 gpu")
    args = parser.parse_args()

    pdparams = args.pdparams
    out_dir = args.out_dir

    # 1) 优先尝试 PaddleDetection 导出工具
    pd_root = None
    if args.paddledet_root:
        pd_root = Path(args.paddledet_root)
    else:
        pd_root = find_paddledetection_root(Path("."))

    if pd_root:
        ok = try_call_pd_export(pd_root, pdparams, out_dir)
        if ok:
            print("已通过 PaddleDetection 导出工具生成推理模型（请检查输出目录）。")
            return 0
        else:
            print("尝试使用 PaddleDetection 导出工具失败，继续尝试模型类导出或手动方式。")

    # 2) 若用户提供了模型类，尝试通过 paddle.load + paddle.jit.save 导出
    if args.model_class:
        ok = export_via_model_class(pdparams, args.model_class, out_dir, device=args.device)
        if ok:
            print("通过模型类导出成功。")
            return 0
        else:
            print("通过模型类导出失败。请按提示修正模型类导入/实例化流程。")
            return 2

    # 3) 若未能自动导出，给出明确的操作建议
    print("\n自动导出失败。建议步骤：")
    print("1) 若您使用 PaddleDetection 训练，请在仓库中使用其导出脚本（tools/export_model.py / deploy/export_model.py）。")
    print("   示例：python tools/export_model.py --weights output/best_model.pdparams --output_dir inference_model/")
    print("2) 若没有 PaddleDetection 源码，请提供模型定义的 Python 模块路径（--model_class），脚本会尝试 load 和 paddle.jit.save。")
    print("3) 确保已安装 PaddlePaddle（pip install paddlepaddle -f https://www.paddlepaddle.org.cn/whl/stable.html），并在合适设备上运行（GPU/CPU）。")
    return 1

if __name__ == "__main__":
    sys.exit(main())
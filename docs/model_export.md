# 模型导出指南

本文档介绍如何在本仓库中快速导出训练产生的 **final** 与 **best** 模型，并将其转换为 PaddleInference/ONNX 可直接部署的形式。

## 目录结构约定

- 训练权重默认存放在 `output/` 目录，其中包含：
  - `model_final.pdparams`：整轮训练结束时的最终权重。
  - `best_model.pdparams`：在验证集上表现最优的权重。
- 导出产物建议放在 `exports/` 目录，按子文件夹区分 `final/`、`best/` 等版本。

## 快捷脚本：`tools/export_final_and_best.py`

脚本封装了 PaddleDetection 官方 `export_model.py`，可一次性导出上述两类权重，默认参数适配 `output/` 路径。若当前环境仅安装了 CPU 版 PaddlePaddle，脚本会自动在内部追加 `use_gpu=false`，避免导出时报出 “Config use_gpu cannot be set as true...” 的错误。

### 基本用法

```powershell
python tools/export_final_and_best.py `
  --config PaddleDetection/configs/ppyoloe/ppyoloe_plus_crn_l_300e_coco.yml `
  --paddledet-root PaddleDetection `
  --weights-root output `
  --output-root exports
```

运行后将生成：

```text
exports/
├── best/
│   ├── inference.pdmodel
│   ├── inference.pdiparams
│   └── deployment.yml
└── final/
    ├── ...
```

### 常见参数

| 参数 | 说明 |
| ---- | ---- |
| `--python` | 调用 `export_model.py` 的 Python 解释器，默认使用当前环境。 |
| `--extra-opts KEY=VALUE` | 向 `export_model.py -o` 追加参数，可重复使用。脚本已默认追加 `use_gpu=false`，如需开启 GPU，请显式传入 `--extra-opts use_gpu=true`。 |
| `--skip-final / --skip-best` | 如果只想导出其中一种模型，可通过这两个开关跳过任务。 |
| `--export-onnx` | 在 Paddle 推理模型导出成功后，同步调用 `paddle2onnx` 生成 `.onnx` 文件。 |
| `--onnx-opset` | ONNX opset 版本，配合 `--export-onnx` 使用，默认 13。 |
| `--onnx-output-name` | 生成 ONNX 文件名，默认 `model.onnx`。 |
| `--onnx-extra-args ARG` | 追加原样传递给 `paddle2onnx.command` 的参数，可重复使用，例如 `--onnx-extra-args --enable_onnx_checker False`。 |

### 常见报错

| 报错 | 排查思路 |
| ---- | -------- |
| `FileNotFoundError: PaddleDetection/tools/export_model.py` | 确认仓库内已同步 PaddleDetection 子模块或目录路径正确。 |
| `FileNotFoundError: ...pdparams` | 检查 `output/` 下是否存在对应权重，或通过 `--weights-root` 指向其他路径。 |
| `ModuleNotFoundError: paddle` | 当前环境未安装 PaddlePaddle，请参照 README 快速开始章节安装。 |

## 导出为 ONNX

1. 安装依赖：

  ```powershell
  C:/Users/BoHuYeShan/AppData/Local/Programs/Python/Python312/python.exe -m pip install paddle2onnx
  ```

  （如已安装可跳过，命令中的 Python 路径以实际环境为准。）

1. 运行脚本并开启 `--export-onnx`：

  ```powershell
  python tools/export_final_and_best.py `
    --config PaddleDetection/configs/ppyoloe/ppyoloe_plus_crn_l_300e_coco.yml `
    --paddledet-root PaddleDetection `
    --weights-root output `
    --output-root exports `
    --export-onnx
  ```

  成功后会在 `exports/final/.../model.onnx` 与 `exports/best/.../model.onnx` 中看到对应的 ONNX 文件。脚本默认使用 opset 13，并自动提示 `multiclass_nms3` 算子仅支持 batch size == 1 的限制。如需调整 opset 或传递额外参数，可分别使用 `--onnx-opset` 和 `--onnx-extra-args`。

1. 若想在导出后做一致性验证，可使用 `sandbox_scripts/onnx_sanity_check.py` 对比 Paddle 与 ONNX 输出。

## 导出后的下一步

1. 可使用 `sandbox_scripts/onnx_sanity_check.py` 对比 PaddleInference 与 ONNX Runtime 的输出差异，确保导出正确。
2. 将导出的推理模型复制/打包到 Android Demo 或服务器部署位置。
3. 若需要其它格式（TensorRT、RKNN 等）：在 CI 中追加相应转换脚本，同样使用 `exports/best`、`exports/final` 目录中的 `model.pdmodel`/`model.pdiparams` 作为输入。

如需在其他权重间切换，只需调整 `--weights-root` 参数即可。建议在每次训练完成后立即运行本脚本，保持推理模型与最新实验同步。

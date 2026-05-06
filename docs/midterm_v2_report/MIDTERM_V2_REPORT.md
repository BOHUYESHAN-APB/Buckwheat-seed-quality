# 荞麦种子检测 V2 中期检查报告

## 1. 结论摘要

本轮 V2 模型已经完成树莓派 5 侧的同平台推理取证，当前可以明确下结论：

1. `YOLO26n-p2 @ 960` 在 Raspberry Pi 5 CPU-only 场景下可以运行，但距离产线实时过线计数目标仍有明显差距。
2. 同一台树莓派、同一批测试图、同一输入尺寸下，`NCNN CPU` 明显快于 `ONNX Runtime CPU`。
3. 当前模型在树莓派 5 上不适合走 `Vulkan GPU` 路线。GPU 栈是通的，但该模型在 `NCNN Vulkan` 下反而极慢。
4. `PT` 当前没有完成树莓派同机对比，不是模型导出失败，而是树莓派现有评测环境里没有安装 `torch` 与 `ultralytics`。因此本报告不混入异构设备 `PT` 数据，避免口径污染。
5. 作为 V1 参考基线，树莓派侧已有 `YOLO11 ONNX 640` 的历史实测结果，均值约 `241.45 ms`，吞吐约 `4.14 img/s`。当前 V2 即使切到 `NCNN CPU`，仍然比这个 V1 参考慢。
6. 结合本轮实测，当前阶段的主要瓶颈应归因为开发板算力上限，而不是模型本身已经失效或不可用。后续如果切换到更强的国产开发板或带 NPU 的平台，当前模型路线仍有继续验证和优化的价值。

## 2. 测试环境

- 设备：Raspberry Pi 5
- 系统：Ubuntu 24.04 LTS
- 内核：`6.8.0-1052-raspi`
- 架构：`aarch64`
- GPU 驱动栈：`V3D 7.1.7.0 / V3DV Mesa 25.2.8`
- 证据文件：`[remote_meta.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/remote_meta.json)`

补充说明：

- `vulkaninfo` 可正常列出 `V3D 7.1.7.0`，说明 Pi 5 的 Vulkan 图形栈已可用。
- 这只能证明 GPU 栈可工作，不代表当前 YOLO26 图在该 GPU 后端上就适合推理。

## 3. 测试对象与口径

### 3.1 V2 主模型

- 模型族：`YOLO26n-p2`
- 输入尺寸：`960 x 960`
- 类别：`T_AB / T_C / K_AB / K_C / D`
- 导出形态：
  - `best.pt`
  - `best.onnx`
  - `best_ncnn_model/model.ncnn.param + model.ncnn.bin`

### 3.2 V1 / 旧版参考

- 参考模型：`YOLO11 ONNX`
- 输入尺寸：`640 x 640`
- 树莓派侧历史基准文件：`[yolo11_bench_result.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/yolo11_bench_result.json)`

### 3.3 本报告的数据口径

- `ONNX`：使用仓库中的 `[pi_eval_onnx.py](/F:/CODE/Buckwheat-seed-quality/scripts/pi_eval_onnx.py)` 在树莓派上对真实测试图和 12fps/3s 合成视频进行测试。
- `NCNN CPU`：使用本次补充的 `[pi_eval_ncnn.py](/F:/CODE/Buckwheat-seed-quality/scripts/pi_eval_ncnn.py)` 在树莓派上对同一批测试图和同一视频口径进行测试。
- `YOLO11 V1`：历史文件是 model-only benchmark，测的是 `session.run()` 本体，不含同样的图像前后处理与真实检测统计，因此只能作为“旧版树莓派速度参考”，不能直接视为同口径精度评估。

## 4. 核心结果

### 4.1 同平台速度对比

来自汇总文件：`[benchmark_summary.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/benchmark_summary.json)`

| 项目 | 输入 | 平均单图延迟 | 视频平均延迟 | 估算 FPS | 备注 |
| --- | --- | ---: | ---: | ---: | --- |
| V1 YOLO11 ONNX 参考 | 640 | 241.45 ms | 未记录 | 4.14 img/s | 历史 model-only benchmark |
| V2 YOLO26n-p2 ONNX CPU | 960 | 561.23 ms | 573.82 ms | 1.74 | 树莓派真实图/视频评测 |
| V2 YOLO26n-p2 NCNN CPU | 960 | 307.00 ms | 310.45 ms | 3.22 | 树莓派真实图/视频评测 |

可以直接得出：

- `NCNN CPU` 相比 `ONNX CPU`，单图加速约 `1.83x`。
- `NCNN CPU` 相比 `ONNX CPU`，视频口径加速约 `1.85x`。
- 但即使切到 `NCNN CPU`，当前 V2 仍约是 V1 `YOLO11 ONNX 640` 的 `1.27x` 延迟。

### 4.2 Vulkan GPU 结果

相关证据：

- `[ncnn_vulkan_probe.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/ncnn_vulkan_probe.json)`

树莓派上对同一份 `NCNN` 模型做短测，得到：

- `NCNN Vulkan` 单图两次耗时约 `6011 ms`、`5811 ms`
- 平均约 `5911 ms`

这说明：

- Vulkan 栈本身是通的。
- 但当前 `YOLO26n-p2 @ 960` 这张图在 Pi 5 的 `V3D` 上完全不适合作为部署主线。
- 当前模型在 GPU 上比 CPU 慢约一个数量级以上，继续投入 Vulkan 优化没有工程性价比。

### 4.3 PT 同机测试状态

相关证据：

- `[pt_env_probe.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/pt_env_probe.json)`

结果：

- `torch` 不存在
- `ultralytics` 不存在
- 现有树莓派评测环境仅具备 `onnxruntime / opencv / numpy`

因此本次报告里：

- `PT` 作为导出产物已存在，但未完成树莓派同机 benchmark。
- 不能把 Windows 或其他机器上的 `PT` 测试拿来和树莓派 `ONNX / NCNN` 混表。

## 5. 证据链解释

### 5.1 为什么可以确认 NCNN 转换是正确的

当前已经完成以下验证：

- 本地成功从 `best.pt` 导出 `best_ncnn_model`。
- 树莓派上可正常加载 `model.ncnn.param` 与 `model.ncnn.bin`。
- `NCNN CPU`、`NCNN Vulkan` 都能输出固定形状 `9 x 76500`。

这说明：

- 模型格式转换没有坏。
- 当前问题不是“没有正确转成 NCNN”。
- 当前问题在于该模型结构和输出头，在 Pi 5 上的后端适配与推理代价。

### 5.2 为什么当前不能直接用 NCNN 的检测数量去做精度结论

当前 `ONNX` 和 `NCNN` 的输出头不是同一种口径：

- `ONNX` 使用的是 YOLO26 end-to-end 导出，输出近似 `(N, 300, 6)`，无需 NMS。
- `NCNN` 根据 Ultralytics 官方文档会自动回退到 one-to-many 头，因此仍是传统 raw head，需要单独做 NMS 与正确的后处理。

官方文档依据：

- `temp/openi_code_repo/ultralytics/docs/en/guides/end2end-detection.md` 明确说明 `NCNN` 导出不支持 end-to-end，会自动 fallback 到 one-to-many head。

因此当前状态是：

- `NCNN` 的速度结论成立。
- 但我现在自写的 `NCNN` 评测脚本只完成了“速度同口径取证”，还没有把其检测后处理完全对齐到 `ONNX`/Ultralytics 官方预测链路。
- 所以报告里把 `NCNN` 的检测数 mismatch 作为“后处理待对齐问题”记录，而不是误写成“NCNN 模型精度不行”。

## 6. 对当前 V2 模型的工程判断

### 6.1 当前版本能否直接作为树莓派产线主模型

不建议直接作为最终主模型，原因如下：

1. `ONNX CPU` 约 `561 ms`/图，视频约 `1.74 FPS`，离过线计数目标差距明显。
2. `NCNN CPU` 虽然提升到约 `307 ms`/图、`3.22 FPS`，但仍偏慢。
3. `NCNN Vulkan` 在 Pi 5 上明显不可用。
4. 当前模型使用 `YOLO26n-p2 @ 960`，本身就是偏重的“小目标强化结构 + 大输入尺寸”组合。

这里需要强调的是，当前问题更偏向“平台上限”而不是“模型完全不行”。本轮测试已经证明模型在树莓派 5 上可运行、可导出、可完成端到端推理，只是受制于 Raspberry Pi 5 当前 CPU/GPU 组合的算力与后端适配能力，无法把该模型稳定推到理想的工业实时速度。

### 6.2 为什么会慢

结合当前证据，最可能的主因排序如下：

1. 输入尺寸 `960` 过大。相对 `640`，像素量扩大为 `2.25x`。
2. `p2` 小目标头会保留更高分辨率特征图，候选数膨胀明显。
3. `YOLO26` 的当前导出图相比 `YOLO11n` 更不适合 Pi 5 这类 ARM CPU + V3D Vulkan 组合。
4. Pi 5 的 GPU 是图形向 GPU，不是推理友好的 NPU。当前模型图在其 Vulkan 路线上没有收益。

## 7. 现阶段建议

### 7.1 模型路线

下一阶段建议不要继续把 `YOLO26n-p2 @ 960` 当作树莓派主线唯一方案，应尽快补以下实验矩阵：

1. `YOLO11n @ 640`
2. `YOLO11n @ 736`
3. `YOLO11n @ 800`
4. `YOLO11n-p2 @ 640`
5. `YOLO11n-p2 @ 736`
6. `YOLO26n-p2 @ 640`

目标不是一次性追满精度，而是先建立“速度可落地”的主线，再看小目标召回是否值得付出 `p2` 和大输入的代价。

### 7.2 后端路线

树莓派 5 当前建议优先级：

1. `NCNN CPU`
2. `ONNX Runtime CPU`
3. 放弃 `NCNN Vulkan` 作为当前主线

### 7.3 PT 对比补项

如果后面一定要补 `PT / ONNX / NCNN` 三格式同机对比，需要先在树莓派上单独准备一套可运行 `torch + ultralytics` 的环境，再用与本报告相同的图像集和重复次数补跑。

## 8. 已落库文件

### 8.1 报告主文件

- `[MIDTERM_V2_REPORT.md](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/MIDTERM_V2_REPORT.md)`
- `[benchmark_summary.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/benchmark_summary.json)`
- `[benchmark_summary.csv](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/benchmark_summary.csv)`

### 8.2 原始证据

- `[buckwheat_onnx_pi_eval_report.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/buckwheat_onnx_pi_eval_report.json)`
- `[buckwheat_onnx_pi_eval_summary.csv](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/buckwheat_onnx_pi_eval_summary.csv)`
- `[buckwheat_ncnn_cpu_pi_eval_report.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/buckwheat_ncnn_cpu_pi_eval_report.json)`
- `[buckwheat_ncnn_cpu_pi_eval_summary.csv](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/buckwheat_ncnn_cpu_pi_eval_summary.csv)`
- `[yolo11_bench_result.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/yolo11_bench_result.json)`
- `[remote_meta.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/remote_meta.json)`
- `[pt_env_probe.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/pt_env_probe.json)`
- `[ncnn_vulkan_probe.json](/F:/CODE/Buckwheat-seed-quality/docs/midterm_v2_report/evidence/ncnn_vulkan_probe.json)`

## 9. 当前可直接用于汇报的话术

可以直接概括为：

> V2 已完成树莓派 5 实机验证。当前 `YOLO26n-p2 @ 960` 在 CPU 上可运行，`ONNX` 平均约 `561 ms`/图，`NCNN` 优化后约 `307 ms`/图；Pi 5 的 Vulkan GPU 路线已验证不适合作为当前模型主线，单图约 `5.9 s`。因此，本阶段的核心瓶颈应判断为开发板算力上限，而不是模型能力本身不足。后续建议切换到更强的国产开发板或带 NPU 的平台继续验证，并保留本次结果作为模型路线与硬件选型的中期依据。

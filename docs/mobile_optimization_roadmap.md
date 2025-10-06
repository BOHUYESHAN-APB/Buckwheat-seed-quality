# 移动端优化路线图

本路线图在现有《Buckwheat Improvement Roadmap》的基础上，聚焦移动端推理体验，划分短期（1~2 周）、中期（2~4 周）与后续扩展方向。目标是在保持检测精度的同时，兼顾高通 NPU 优先、GPU/CPU 回退能力，并为未来适配其他 SoC（联发科、三星等）预留空间。

## 1. 短期（1~2 周）

| 优先级 | 任务 | 交付物 | 备注 |
| ------ | ---- | ------ | ---- |
| P0 | 完成 PP-YOLOE+ L → ONNX 导出与 Sanity Check | `sandbox_scripts/onnx_sanity_check.py` 运行报告 | 确保导出一致性 |
| P0 | 梳理摄像头 Demo 代码、完成 NNAPI 优先的推理管线 | Android Demo MVP | 包含帧同步、坐标映射 |
| P1 | 在目标高通设备上采集性能指标 | `docs/perf_results/YYYYMMDD_device.md` | 对照 `performance_validation_plan.md` |
| P1 | 建立 FP16 导出尝试 | FP16 模型文件 + 误差分析 | 检查 NNAPI / GPU 支持情况 |

> 若 PP-YOLOE+ L 在 NPU 上内存超限，提前准备 PP-YOLOE+ M 作为回退方案。

## 2. 中期（2~4 周）

| 优先级 | 任务 | 交付物 | 备注 |
| ------ | ---- | ------ | ---- |
| P0 | 模型轻量化实验（PP-YOLOE+ M/S, 输入 640×640） | `experiments/lightweight/` 记录 | 对比精度回退与性能增益 |
| P0 | INT8 量化探索 | 量化模型 + 校准数据集说明 | NNAPI 支持取决于驱动版本 |
| P1 | 自动化导出流水线 | CI 任务：Paddle → ONNX → Sanity Check | 确保每次提交都能获得导出产物 |
| P1 | OpenVINO / Intel GPU 跑通验证 | Windows/Linux 验证脚本 | 作为无 NVIDIA 资源下的桌面加速手段 |
| P2 | Android 端推理日志与监控（fps、耗时、provider） | Demo 中的调试面板或日志类 | 便于现场排错 |

## 3. 后续扩展（4 周及后）

- **平台扩展**：
  - 联发科 Dimensity：评估 Paddle Lite NNAdapter 或直接使用 NNAPI/Vulkan 支持情况。
  - 三星 Exynos / 谷歌 Tensor：记录 NNAPI 支持矩阵，若不足可接入 GPU + CPU 双引擎。
  - （暂不考虑）华为麒麟、小米澎湃/玄界、苹果：等后续需求明确再投入。
- **部署形态**：
  - 集成 TensorRT（需要 NVIDIA GPU 环境）用于服务器或边缘网关。
  - 通过 FastDeploy / Paddle Serving 将模型部署为 HTTP/gRPC 服务，供移动端调试对比。
- **算法演进**：
  - 结合路线图中的“小样本分层动态学习率方案”，及时同步最新 checkpoint。若指标提升显著，及时重新导出模型，并更新移动端性能基线。
  - 探索更轻的 backbone（如 PP-YOLOE-Slim、PP-YOLOE-Lite）及多任务头（质量分级 + 缺陷定位）。
- **工具链与 QA**：
  - 为移动端 UI 编写自动化测试（截图比对、FPS 采集）。
  - 与 `logs_analysis/` 脚本打通，自动对比移动端与桌面端检测日志。

## 4. 关键里程碑

| 时间点 | 里程碑 | 完成标准 |
| ------ | ------ | -------- |
| M0 + 2 周 | Android Demo 支持 NNAPI/GPU/CPU 三种模式并通过指标验收 | 满足 `performance_validation_plan` 中的门槛 |
| M0 + 4 周 | 轻量化/量化实验完成，形成最佳实践文档 | 包含精度、性能、资源占用对比 |
| M0 + 6 周 | 多平台验证样板就绪 | 输出《移动端部署兼容性手册》草案 |

> 里程碑完成后，请将结果回写到 `Buckwheat_Improvement_Roadmap.md` 或补充在 `docs/` 下的专题文档中，保持信息同步。

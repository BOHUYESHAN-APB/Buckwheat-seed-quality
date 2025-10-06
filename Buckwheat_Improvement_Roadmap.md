# Buckwheat Seed Quality – Improvement Roadmap

> **来源整合**：本路线图融合此前的“自适应学习率实验设计”笔记与用户提供的《PP-YOLOE+ Buckwheat Optimization Plan》，在统一框架下梳理后续研发迭代的优先级、交付物与评估指标。

## 现状速览（2025-09-21）

- **数据基线**：`dataset/data/coco/instances_train_fixed.json` 共 356 张有效标注图像；训练集采用 Mosaic/MixUp 等增强策略。
- **模型配置**：PP-YOLOE+ (L) + CRN，输入 800×800，现行设定为 EMA + 自适应余弦退火学习率（带阶段性 Restart）。
- **最新指标**：从 `quality_optimized_training_*.log` 解析得到的最佳单点表现为 $AP_{0.5:0.95}=0.167$、$AP_{0.5}=0.204$、$AR_{0.5:0.95}=0.409$，对应 epoch 159，详见 `logs_analysis/training_metrics.csv`。
- **工具链**：
  - `logs_analysis/parse_training_logs.py` 自动汇总损失、学习率、AP/AR 与 GPU 显存。
  - `inference_results/showcase/` 提供桌面 UI 与批量可视化对照。
  - `app/` 下 Tkinter 推理界面支持 GPU 自动探测与 letterbox/拉伸双分支后处理。
- **资源状态（2025-10-03）**：租用训练服务器已到期，部分原始实验输出与检查点未能完整备份，请在后续训练前确认关键文件是否齐全。

## 已完成的关键工作

| 时间 | 项目 | 内容 | 产出 |
| ---- | ---- | ---- | ---- |
| 2025-09-18~21 | 模型收敛与恢复训练 | 基于余弦退火 + EMA 的 300 epoch 续训，并在检测到梯度扰动时触发重启脚本（`train_quality_optimized.sh`） | `quality_optimized_training_*.log`、`training_metrics.csv`、`training_loss.png`、`training_ap.png` |
| 2025-09-19 | 推理 UI 对齐 | 增强 `app/ui.py` 的 letterbox 缩放与 GPU 自动选择、文字大小自适应 | 推理 UI 稳定输出，与原图框一致 |
| 2025-09-20 | 模型打包与部署 | 生成 `ppyoloe_models_package.tar.gz`，同步导出模型与批量推理脚本 | `package/` 目录与批量推理脚本 |

## 迭代规划概览

| 阶段 | 时间窗 | 目标主题 | 关键指标 | 前置条件 |
| ---- | ------ | -------- | -------- | -------- |
| S1 | 1~2 周 | 数据与学习率韧性加固 | 数据漂移占比 < 5%；`AP_{0.5}` ≥ 0.22 | 现有日志分析工具就绪 |
| S2 | 2~4 周 | 架构与损失函数优化 | `AP_{0.5:0.95}` 提升 ≥ 2 个百分点 | S1 中数据与调参流程稳定 |
| S3 | 4~6 周 | 推理性能与可观测性 | UI 帧率 ≥ 8 FPS；推理内存下降 15% | 前两阶段指标达标 |

## 小样本分层动态学习率方案（2025-10-03）

### 1. 设计思路

小样本目标检测的主要矛盾在于：模型容量大（PP-YOLOE+ L 数千万参数）、标注数据仅约 300 张且类别少，但各类外观相近；同时分类头与回归头共享学习率易产生互扰。为此，本方案遵循三项原则：

- **迁移学习优先**：充分利用 COCO 预训练权重，仅微调分类头与部分高层特征。
- **分类/回归分离优化**：给予分类头更精细、更慢的学习率变化以缓解类别混淆。
- **动态学习率抖动响应**：在小样本场景中保持稳定收敛的同时保留跳出局部最优的能力。

### 2. 具体实现

#### 2.1 网络初始化与分层训练

- **Backbone**：使用 PP-YOLOE+ L 在 COCO 上的预训练权重。
- **分类头（Class Head）**：随机初始化或加载 ImageNet 分类权重。
- **回归头（Box Head）**：随机初始化。
- **训练阶段**：
  - **Epoch 1-5（冻结阶段）**：冻结 backbone，仅训练分类头与回归头，先对齐小样本类别分布与框回归。
  - **Epoch 6-15（解冻阶段）**：解冻 backbone 的 stage4、stage5，允许高层语义特征按需微调。

#### 2.2 分层学习率（Layer-wise LR）

- Backbone：$0.1\times$ 基础学习率。
- 回归头：$0.5\times$ 基础学习率。
- 分类头：$1.0\times$ 基础学习率（重点优化对象）。

此设置确保分类头优先适应小样本类别特征，同时降低回归梯度对其的干扰。

#### 2.3 动态学习率调度

| 迭代区间 | 学习率策略 | 目标 |
| --- | --- | --- |
| 0–50 | 基础学习率（示例：0.001） | 快速收敛，不做动态调整 |
| 51–150 | 基础学习率 × 0.3 | 适度降速，抑制早期过拟合 |
| 151–250 | 动态区间（0.0005–0.005，仅作用于分类头） | 检测到 loss 抖动时小幅升高，帮助跳出局部最优 |
| 251–300 | 低学习率（0.0001） | 精细微调，稳定分类与定位 |

- **抖动检测**：连续 3 次迭代 loss 波幅超过最近 10 次均值的 15% 时触发动态调节；仅提升分类头学习率，回归头保持固定。
- **监测实现**：在现有 `logs_analysis/parse_training_logs.py` 基础上，新增 `grad_alert`/`loss_jitter` 字段记录触发时刻（待实现）。

#### 2.4 损失函数与采样

- 分类：采用 Focal Loss（$\gamma=2 \sim 3$），聚焦难分类样本。
- 定位：尝试 CIoU 或 SIoU，以提升定位精度。
- 类别平衡采样：每个 batch 保证各类别样本数尽量均衡，可通过重采样或类条件采样实现。

#### 2.5 数据增强

- Mosaic + MixUp（提升背景多样性）。
- 随机旋转/缩放/翻转（增强姿态变化）。
- 颜色抖动（亮度、对比度、饱和度）。
- CutOut（随机遮挡，增强鲁棒性）。

### 3. 实验验证计划

| 组别 | 配置 | 目的 |
| --- | --- | --- |
| Baseline | 官方默认、固定学习率 | 基准性能 |
| A | 现有动态学习率方案 | 验证原始动态策略有效性 |
| B | 分层学习率（分类头单独调优） | 验证层级策略贡献 |
| C | 分层学习率 + 动态调度（本方案） | 验证组合收益 |
| D | 方案 C + Focal Loss | 检查类别混淆缓解效果 |

- **评估指标**：mAP@0.5:0.95、各类别 AP、Recall、Precision。
- **可视化**：混淆矩阵、loss&lr 曲线、优化前后可视化样例。

### 4. 论文包装建议

- **主题**：Layer-wise Dynamic Learning Rate for Few-shot Object Detection。
- **创新点**：
  - 分层学习率凸显分类头调优需求。
  - 基于 loss 抖动的自适应分类头调节机制。
  - 结合 Focal Loss、类别平衡采样与迁移学习缓解小样本混淆。
- **预期贡献**：在 300 张 / 4 类场景下，mAP 提升 5–10 个百分点，同时保持高召回率并降低类别混淆。

### 5. 预期效果

- 当前成绩：Recall ≈ 70%，mAP ≈ 23%。
- 方案落地后目标：Recall ≥ 72%，mAP ≥ 30%（具体增益受数据质量与标注精度影响）。

> **注**：由于租用服务器到期导致部分训练输出缺失，复现实验前需重新确认 checkpoint、日志与数据备份可用性。

## 工作流拆解

### 1. 自适应学习率与训练韧性（自适应 LR 设计稿）

- **分段余弦退火 + Warm Restart**：继续沿用 150-epoch 周期的余弦衰减，在检测到 `loss` 抖动（标准差 > 0.08）时自动缩短周期并重启 EMA 累积。脚本：`train_quality_optimized.sh`。
- **层级学习率缩放**：保持 backbone lr 比 head 低 0.25×，并在 epoch 180 之后引入 `freeze_bn` 复查，避免显存波动。
- **梯度噪声自检**：针对 `accelerated_training_*.log` 出现的学习率跃迁问题，完善日志钩子捕捉 `loss` 激增并写入 `logs_analysis/training_metrics.csv` 的 `grad_alert` 字段（待实现）。
- **预期指标**：重启后 20 epoch 内 `loss` 稳定下降，`max_mem_reserved` 不超过 23 GB。

### 2. 数据管线与标注质量（Optimization Plan）

- **样本再分层**：将 356 张样本按籽粒尺寸、光照分三档，新增验证集(20%) 用于冷启动对比。
- **自动噪声过滤**：启用 `tools/profile_detector.py` 对 `inference_results/raw/` 做批量推理，剔除误差 > 0.3 的样本。
- **增强策略对照**：按优化方案建议，构建 Mosaic+MixUp、RandomAffine+CutOut、Copy-Paste 三套组合，每套 30 epoch 快速验证，将结果汇总至 `logs_analysis/augmentation_bench.csv`（新建）。
- **数据交付物**：`dataset/README.md` 补充新版切分说明；`bbox.json` 更新标注统计。

### 3. 模型结构与损失改进（综合两份方案）

- **Neck 调整**：评估替换 PAN 为 BiFPN-lite 的可行性（关注参数量 < 70M），并在 `configs/ppyoloe_plus_crn_m_300e_speed_optimized.yml` 新增可切换选项。
- **损失函数**：在 GIoU 基础上试验 SIoU/MPDIoU，保持 DFL 权重 0.5；对比 Focal-EIOU 是否改善小目标 recall。
- **正负样本分配**：引入 Task-aligned Assign + Soft Label (来自 Optimization Plan)，需在 PaddleDetection 自定义 op 中补充实现，输出验证日志 `balanced_restart_training_*.log`。
- **评估要求**：每轮实验需提供 `AP_{0.5:0.95}`、`AP_small`、`AR_small` 与推理延迟 (ms)；若 `AP_small` < -0.01，则回滚配置。

### 4. 推理部署与可视化

- **UI 性能优化**：在 `app/ui.py` 中缓存缩放矩阵、减少重复 tensor->numpy 转换；目标是 Windows 下 1080p 摄像头帧率 ≥ 10 FPS。
- **模型导出矩阵**：扩展 `package/README.md`，列出 FP32/FP16、TensorRT、ONNX Runtime 导出指令，记录推理耗时。
- **可观测性**：引入 Prometheus 简易指标导出（通过 `tools/buckwheat_exporter.py` 新建），追踪每小时推理数量与平均置信度。

## 度量与日志追踪

| 实验策略 | 相关日志 | 关键设置 | 最佳指标 | 备注 |
| -------- | -------- | -------- | -------- | ---- |
| Quality Optimized | `quality_optimized_training_20250919_18xxxx.log` | 300 epoch、CosineAnnealing + EMA、800×800 拉伸 | $AP_{0.5}=0.204$、`loss` ≈ 0.98 @ epoch 159 | `training_metrics.csv` 已解析 |
| Accelerated Restart | `accelerated_training_20250919_175406.log` | 高起始 lr=6.4e-3、快速冷却 | 暂缺完整评估（需补跑 `tools/eval.py`） | 计划在 S1 中补齐 AP/AR 统计 |
| Balanced Restart | `balanced_restart_training_*.log` | 双阶段 lr，Restart 间隔 45 epoch | 尚未解析 | 纳入 logs_analysis 脚本待办 |

> 建议统一通过 `python logs_analysis/parse_training_logs.py` 与 `python tools/eval.py` 生成 CSV/可视化，再将摘要回写至 README。

## 附件与参考

- `logs_analysis/training_metrics.csv` – 每个 epoch 指标、学习率、显存使用。
- `logs_analysis/training_loss.png` / `training_ap.png` – 自动绘制的收敛曲线。
- `inference_results/showcase/` – 最新可视化示例，用于对照小目标召回。
- `PaddleDetection/package/` – 部署包与脚本。

> 后续更新请在每次实验结束后补充“现状速览”与“度量追踪”两节，保持路线图滚动迭代。

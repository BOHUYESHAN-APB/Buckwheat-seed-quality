# ColonySeedNet-v1 — 面向荞麦籽小目标检测的 Ascend/MindSpore 算法

## 概述

ColonySeedNet-v1 是一个基于 **MindYOLO YOLOv8** 的定制化小目标检测算法，专为荞麦籽粒质检任务设计。

## 设计原则

1. **Ascend/MindSpore 兼容**：所有组件基于 MindSpore API，目标设备为 Huawei Ascend NPU。
2. **小目标优先**：荞麦籽粒在高分辨率图像中占比极小，需要针对性的检测策略。
3. **迁移学习基线**：使用 MindYOLO YOLOv8 的 COCO 预训练权重作为初始化。
4. **分阶段课程增强**：渐进式数据增强，避免早期训练不稳定。

## 基础架构

```
ColonySeedNet-v1
├── Backbone:    CSPDarknet (from MindYOLO YOLOv8)
├── Neck:        PAN-FPN
├── Head:        YOLOv8 Decoupled Head
└── Post-process: NMS + Tile Merge
```

## 小目标策略

### Tile Inference

将输入图像切分为小块 (tile) 进行推理，然后合并检测结果：

| 参数 | 值 | 说明 |
|------|-----|------|
| tile_size | 192×192 | 小于默认 384×384 的裁切窗口 |
| tile_overlap | 32 px | 重叠区域保证边界目标不丢失 |
| nms_merge | True | 跨 tile 的 NMS 合并 |

### 分阶段课程增强 (Staged Curriculum Augmentation)

训练过程中逐步增加数据增强强度：

| 阶段 | Epoch 范围 | 增强方式 | 目标 |
|------|-----------|----------|------|
| Basic | 0–50 | random_flip, random_scale | 稳定初始化 |
| Intermediate | 50–150 | + mosaic, color_jitter | 提升多样性 |
| Advanced | 150–300 | + mixup, random_rotation | 强化泛化 |

## 损失函数

| 组件 | 损失函数 | 说明 |
|------|----------|------|
| 分类 | Focal Loss (γ=2.5) | 聚焦难分类样本 |
| 回归 | CIoU Loss | 提升定位精度 |
| 分布焦点 | DFL (Distribution Focal Loss) | 细粒度边界回归 |
| 类别平衡 | Inverse-frequency weighting | 缓解类别不平衡 |

## 学习率方案

采用 **Warmup + Cosine Decay** 作为迁移基线：

- Warmup: 5 epochs 线性升温
- Cosine: 从 base_lr 衰减至 1% base_lr
- 基础学习率: 0.0005

参考项目路线图中的分层动态学习率方案（`Buckwheat_Improvement_Roadmap.md:53`），后续可引入分层 LR 和抖动响应。

## 类别定义

| ID | 名称 | 描述 |
|----|------|------|
| 1 | seeda | 饱满籽粒 A 型 |
| 2 | seedb | 饱满籽粒 B 型 |
| 3 | seedc | 杂质/不饱满 |
| 4 | seedd | 其他/背景 |

## 与原 Paddle 版本的对应关系

| Paddle/PP-YOLOE+ | ColonySeedNet-v1 (MindSpore) |
|------------------|------------------------------|
| PP-YOLOE+ L | YOLOv8 M |
| Focal Loss (γ=2~3) | Focal Loss (γ=2.5) |
| CIoU / SIoU | CIoU + DFL |
| Mosaic + MixUp | Staged Curriculum Augmentation |
| Layer-wise LR | Warmup + Cosine (Phase 1); Layer-wise (Phase 2) |

## 实现状态

- [x] 算法设计文档
- [x] 配置文件模板
- [ ] MindYOLO YOLOv8 集成（需要引入 MindYOLO 三方依赖）
- [ ] Tile inference 实现
- [ ] Curriculum augmentation pipeline
- [ ] Ascend NPU 实测

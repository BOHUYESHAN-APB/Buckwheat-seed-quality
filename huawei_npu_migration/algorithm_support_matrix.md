# Algorithm Support Matrix — Huawei Ascend / MindSpore

> 记录可用于迁移的 MindSpore 算法及其对荞麦籽质检任务的适配优先级。

## 阶段规划

| 阶段 | 算法 | 框架 | 说明 |
|------|------|------|------|
| Phase 1 | MindYOLO (YOLOv5/v8) | MindYOLO | 成熟 COCO 检测器，作为迁移基线 |
| Phase 2 | MindCV SSD | MindCV | 与 MindYOLO 对比，评估 SSD 在小目标上的表现 |
| Phase 2 | MindCV DeepLabV3 | MindCV | 语义分割基线，用于探索像素级定位 |
| Phase 1 | ColonySeedNet-v1 | 自定义 | 基于 MindYOLO YOLOv8 的小目标优化算法 |

## 算法详情

### MindYOLO Detection

- **模型**：YOLOv5, YOLOv8
- **数据格式**：COCO JSON annotation
- **设备**：Ascend NPU
- **状态**：可用，推荐作为 Phase 1 基线
- **优势**：成熟的 YOLO 生态，社区支持丰富

### MindCV SSD

- **模型**：SSD (Single Shot MultiBox Detector)
- **数据格式**：COCO JSON annotation
- **设备**：Ascend NPU
- **状态**：Phase 2 对比实验用
- **备注**：需要评估其在 384×384 小目标场景下的表现

### MindCV DeepLabV3

- **模型**：DeepLabV3
- **数据格式**：COCO JSON annotation (需像素级标注)
- **设备**：Ascend NPU
- **状态**：Phase 2 探索性实验
- **备注**：需要额外的像素级标注，适合探索性分析

### MindSpore CocoDataset

- **组件**：MindSpore 内置 COCO 数据集加载器
- **数据格式**：标准 COCO JSON annotation
- **设备**：Ascend NPU
- **状态**：所有检测算法的数据层基础

### ColonySeedNet-v1（自定义）

- **基线**：MindYOLO YOLOv8
- **优化**：小目标检测增强 + 分阶段课程学习
- **数据格式**：COCO JSON annotation
- **设备**：Ascend NPU
- **详细设计**：见 `algorithms/colony_seednet_v1.md`

## 数据兼容性

所有算法均兼容 COCO-style 数据布局：

```
dataset_root/
├── train/
│   ├── annotations/
│   │   └── instances_train.json
│   └── images/
│       └── *.jpg
└── val/
    ├── annotations/
    │   └── instances_val.json
    └── images/
        └── *.jpg
```

## 类别定义

荞麦籽质检任务定义 4 个类别：

| 类别 ID | 名称 | 说明 |
|---------|------|------|
| 1 | seeda | 饱满籽粒 A 型 |
| 2 | seedb | 饱满籽粒 B 型 |
| 3 | seedc | 杂质/不饱满 |
| 4 | seedd | 其他/背景类 |

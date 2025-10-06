# 快速开始 - ONNX 模型验证结果

## 🎯 现在就查看标注效果！

### 第一步：查看关键标注图

打开以下文件，对比 Paddle 与 ONNX 的检测效果：

```
📁 android-app/output/
  📄 paddle_reference.png              ← Paddle 基准（24检测，绿框）
  📄 annotated_opset14_no_fallback.png ← ONNX opset14（23检测，红框）✅推荐
```

**期望看到什么？**
- 绿框（Paddle）和红框（ONNX）位置基本一致
- 框准确圈出种子位置
- **没有**大量不相关的竖横直线（已修复）

---

### 第二步：了解集成方法

阅读 Android 集成指南：

```
📁 app/src/main/assets/models/
  📄 README.md    ← Android 集成完整指南
  📄 model.onnx   ← 已准备好的 ONNX 模型（opset 14）
  📄 labels.json  ← 类别标签配置
```

**关键信息**:
- 输入: `[1, 3, 800, 800]` + `[1, 2]` scale_factor
- 输出: `[300, 6]` 格式 `[class, score, x1, y1, x2, y2]`
- 后处理: 应用 score >= 0.5 过滤
- **坐标已缩放**，无需额外处理

---

### 第三步：查看完整报告

详细测试数据和分析：

```
📁 android-app/output/
  📄 comparison_report.md ← 完整对比报告（所有测试结果）

📁 android-app/
  📄 VALIDATION_SUMMARY.md ← 验证总结（问题诊断、文件清单）
  📄 VISUAL_CHECKLIST.md   ← 可视化检查清单（逐图验证指南）
```

---

## 📊 关键数据速览

| 指标 | Paddle 基准 | ONNX opset14 | 状态 |
|------|------------|--------------|------|
| 检测数 | 24 | 23 | ✅ |
| 精度偏差 | - | < 5% | ✅ |
| 坐标准确性 | - | 基本一致 | ✅ |
| Android 兼容性 | N/A | 纯 ONNX | ✅ |

---

## 🚀 立即可做的事

### 选项 A：视觉验证（推荐先做）
1. 打开 `android-app/output/paddle_reference.png`
2. 打开 `android-app/output/annotated_opset14_no_fallback.png`
3. 对比两图，确认检测框位置一致

### 选项 B：了解集成细节
1. 阅读 `app/src/main/assets/models/README.md`
2. 查看后处理代码示例（Java 伪代码）
3. 了解输入输出格式和坐标系统

### 选项 C：深入了解测试过程
1. 阅读 `android-app/output/comparison_report.md`
2. 了解不同 opset 版本的测试结果
3. 查看 score 分布统计和类别分布

---

## ✅ 验证清单

在开始 Android 开发前，确认：

- [ ] 查看了 Paddle 基准标注图（绿框）
- [ ] 查看了 ONNX opset14 标注图（红框）
- [ ] 确认框位置基本一致，无明显偏差
- [ ] 确认**没有**大量不相关的直线（早期问题已修复）
- [ ] 阅读了 Android 集成指南
- [ ] 理解了输入输出格式和后处理步骤

---

## 🆘 遇到问题？

### 标注图显示异常
→ 查看 `android-app/VISUAL_CHECKLIST.md` 的详细检查步骤

### 不确定如何集成
→ 查看 `app/src/main/assets/models/README.md` 的代码示例

### 需要技术细节
→ 查看 `android-app/output/comparison_report.md` 的完整分析

---

**准备就绪？现在可以开始 Android 端集成开发了！** 🎉

**重要文件位置**:
- ONNX 模型: `app/src/main/assets/models/model.onnx`
- 标注图: `android-app/output/*.png`
- 集成指南: `app/src/main/assets/models/README.md`
- 完整报告: `android-app/output/comparison_report.md`

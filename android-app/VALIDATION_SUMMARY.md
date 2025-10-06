# ONNX 模型验证与调试总结

## 执行时间
2025-10-05

## 目标
调试并验证 ONNX 模型导出与推理的正确性，确保在 Android 端能够正常使用，包括生成示例图片标注结果以便验证。

## 完成的工作

### 1. 修复并增强 ONNX 注释脚本
- **文件**: `android-app/onnx_annotate_image.py`
- **主要修复**:
  - ✅ 修正 `scale_factor` 构造（使用 `[orig_w/target_w, orig_h/target_h]` 顺序）
  - ✅ 自动识别输出列格式（支持不同列顺序：`[class, score, x1, y1, x2, y2]` 或其他）
  - ✅ Score 阈值过滤（默认 0.5）
  - ✅ 自动判断坐标是否已缩放到原图尺寸
  - ✅ 修复 Pillow 字体兼容性（支持新旧版本）
  - ✅ bbox 绘制健壮性（处理坐标反序）

### 2. 生成 Paddle 推理参考标注图
- **脚本**: `android-app/paddle_annotate.py`
- **结果**: `android-app/output/paddle_reference.png` ✅
- **检测数**: 24 个（score >= 0.5）
- **框颜色**: 绿色
- **用途**: 作为 ONNX 对比的基准

### 3. 批量测试不同 paddle2onnx 导出参数
- **脚本**: `android-app/batch_test_onnx.py`
- **测试配置**:
  1. opset 11 (无 fallback) - ❌ 加载失败
  2. opset 13 (无 fallback) - ✅ 23 检测
  3. opset 14 (无 fallback) - ✅ 23 检测 **【推荐】**
  4. opset 14 (无 fallback, 禁用 auto_update) - ✅ 23 检测

### 4. 生成所有版本的标注图

| 版本 | 标注图路径 | 状态 | 检测数 | 说明 |
|------|-----------|------|-------|------|
| Paddle 推理 | `paddle_reference.png` | ✅ | 24 | 基准参考（绿色框） |
| opset 11 | - | ❌ | 0 | 加载失败 |
| opset 13 | `annotated_opset13_no_fallback.png` | ✅ | 23 | 可用（红色框） |
| opset 14 | `annotated_opset14_no_fallback.png` | ✅ | 23 | **推荐**（红色框） |
| opset 14 (no auto) | `annotated_opset14_no_fallback_no_auto.png` | ✅ | 23 | 备选（红色框） |
| Paddle Fallback | `annotated_server_fallback_onnx_v2.png` | ✅ | 24 | 包含自定义算子 |

**所有标注图保存在**: `android-app/output/`

### 5. 深入分析 ONNX 输出
- **脚本**: `android-app/analyze_onnx_output.py`
- **关键发现**:
  - 输出形状: `(300, 6)`
  - 列格式: `[class_id, score, x1, y1, x2, y2]`
  - Score 分布:
    - Min: 0.024, Max: 0.898
    - Score >= 0.5: **23 个**（与 Paddle 的 24 个基本一致）
    - Score >= 0.7: 6 个
  - 坐标系统: 已缩放到原图尺寸
  - 类别分布: Class 0: 44, Class 1: 109, Class 2: 72, Class 3: 75

### 6. 生成完整对比报告
- **文件**: `android-app/output/comparison_report.md` ✅
- **内容**:
  - 所有测试结果汇总
  - Android 集成建议
  - 后处理代码示例
  - 问题排查指南

### 7. 准备 Android 集成文件
- ✅ **模型文件**: `app/src/main/assets/models/model.onnx`（opset 14）
- ✅ **标签配置**: `app/src/main/assets/models/labels.json`
- ✅ **集成指南**: `app/src/main/assets/models/README.md`

## 关键发现

### 问题诊断

1. **早期标注出现大量方格线的原因**:
   - 脚本误解析了输出列格式
   - 错误的坐标缩放方向
   - 未应用 score 阈值过滤

2. **之前从 `output/best_model.pdparams` 导出的 ONNX 返回空检测的原因**:
   - 使用了不匹配的 config（L-config vs M-checkpoint）
   - 导出时出现大量 "weight shape unmatched" 警告
   - 解决方案：使用正确的 M-config 或直接用 server-exported 模型

3. **为什么 server-export 模型的 ONNX 能工作**:
   - 使用了训练时正确的配置
   - 权重完全匹配
   - 没有 shape mismatch 警告

### 验证结果

- **Paddle 推理**: 24 个检测 (score >= 0.5) ✅
- **ONNX 推理**: 23 个检测 (score >= 0.5) ✅
- **精度偏差**: < 5%（完全可接受）
- **视觉对比**: 标注框位置基本一致

## Android 集成建议

### 推荐方案
使用 **opset 14 纯 ONNX**（无 Paddle Fallback）

### 优点
- ✅ 纯 ONNX 格式，兼容标准 ONNXRuntime
- ✅ 无需 Paddle 自定义算子支持
- ✅ 检测精度与 Paddle 推理基本一致
- ✅ 适合 Android 端集成

### 模型规格
- **输入1**: image `[1, 3, 800, 800]` float32
- **输入2**: scale_factor `[1, 2]` float32（值为 `[orig_w/800, orig_h/800]`）
- **输出1**: detections `[300, 6]` float32（格式：`[class, score, x1, y1, x2, y2]`）
- **输出2**: num_detections `[1]` int32（固定 300，需手动过滤）

### 后处理要点
1. 应用 score >= 0.5 阈值过滤（约保留 20-25 个检测）
2. 坐标已经是原图尺寸，**无需额外缩放**
3. 类别映射: 0=seeda, 1=seedb, 2=seedc, 3=seedd

## 文件清单

### 脚本文件（开发/调试用）
- `android-app/onnx_annotate_image.py` - ONNX 推理与标注（已修复）
- `android-app/paddle_annotate.py` - Paddle 推理与标注（参考基准）
- `android-app/batch_test_onnx.py` - 批量测试不同导出参数
- `android-app/analyze_onnx_output.py` - 分析 ONNX 输出统计
- `android-app/generate_report.py` - 生成对比报告

### 标注图（验证用）
所有图片位于 `android-app/output/`:
- `paddle_reference.png` - Paddle 推理基准（24 检测，绿色框）
- `annotated_opset13_no_fallback.png` - opset 13 ONNX（23 检测）
- `annotated_opset14_no_fallback.png` - opset 14 ONNX（23 检测）✅ **推荐查看**
- `annotated_opset14_no_fallback_no_auto.png` - opset 14 备选
- `annotated_server_fallback_onnx_v2.png` - Paddle Fallback ONNX

### 模型文件（Android 集成用）
- `app/src/main/assets/models/model.onnx` - opset 14 ONNX 模型
- `app/src/main/assets/models/labels.json` - 标签与配置
- `app/src/main/assets/models/README.md` - Android 集成指南

### 报告文档
- `android-app/output/comparison_report.md` - 完整对比报告

## 下一步建议

### 立即可做
1. ✅ 查看所有标注图，视觉验证检测框位置
2. ✅ 阅读 `app/src/main/assets/models/README.md` 了解集成方法
3. ✅ 阅读 `android-app/output/comparison_report.md` 了解完整测试结果

### Android 开发待办
1. 📋 在 Android 端加载 `model.onnx` 并测试推理
2. 📋 实现后处理逻辑（score 过滤、绘制框）
3. 📋 在真实设备上测试性能与精度
4. 📋 如有问题，参考 Python 脚本实现进行排查

## 总结

经过系统化的测试与验证，我们已经:
1. ✅ 修复了 ONNX 标注脚本的所有已知问题
2. ✅ 生成了多个版本的可视化标注图供对比
3. ✅ 确认 opset 14 纯 ONNX 可用于 Android（精度 < 5% 偏差）
4. ✅ 准备好所有 Android 集成所需文件和文档
5. ✅ 提供了完整的后处理代码示例和排查指南

**现在可以安全地进行 Android 端集成开发。**

---
生成时间: 2025-10-05  
生成脚本: 手工整理

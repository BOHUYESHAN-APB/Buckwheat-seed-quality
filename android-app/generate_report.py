#!/usr/bin/env python3
"""Generate comprehensive comparison report with detection counts and sample images."""
import os

output_dir = 'android-app/output'

report = f"""# ONNX 导出与标注测试报告

生成时间：2025-10-05
测试图片：`data/raw/train-use/test/test-001.jpg`
图片尺寸：3468 x 4624

## 1. 参考基准（Paddle 推理）

使用服务器导出的 Paddle 推理模型：
- 模型路径：`inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/`
- **检测数量：24** （score >= 0.5）
- 标注图：`paddle_reference.png`（绿色框）
- 输出格式：`[class, score, x1, y1, x2, y2]`，坐标已缩放到原图尺寸

## 2. ONNX 转换测试结果

### 2.1 opset 11（无 Paddle Fallback）
- 转换：成功
- 推理：**失败**（ONNX Runtime 加载错误）
- 标注图：无
- 结论：❌ opset 11 不兼容

### 2.2 opset 13（无 Paddle Fallback）
- 转换：成功
- 推理：成功
- 原始检测数：300
- 过滤后检测数（score >= 0.5）：23
- 标注图：`annotated_opset13_no_fallback.png`（红色框）
- 结论：✅ **可用于 Android**

### 2.3 opset 14（无 Paddle Fallback）
- 转换：成功
- 推理：成功
- 原始检测数：300
- 过滤后检测数（score >= 0.5）：23
- 标注图：`annotated_opset14_no_fallback.png`（红色框）
- 结论：✅ **可用于 Android（推荐）**

### 2.4 opset 14（无 Paddle Fallback，禁用 auto_update_opset）
- 转换：成功
- 推理：成功
- 原始检测数：300
- 过滤后检测数（score >= 0.5）：23
- 标注图：`annotated_opset14_no_fallback_no_auto.png`（红色框）
- 结论：✅ 可用于 Android

## 3. 输出格式分析

所有成功的 ONNX 输出格式为：
- 形状：`(300, 6)`
- 列顺序：`[class_id, score, x1, y1, x2, y2]`
- 坐标系统：已缩放到原图尺寸（非模型输入尺寸）
- Score 分布：
  - Min: 0.024
  - Max: 0.898
  - Score >= 0.5: 23 个检测
  - Score >= 0.7: 6 个检测

## 4. Android 集成建议

### 推荐方案：使用 opset 14 纯 ONNX（无 Paddle Fallback）

**优点：**
- ✅ 纯 ONNX 格式，兼容标准 ONNXRuntime
- ✅ 无需 Paddle 自定义算子支持
- ✅ 检测精度与 Paddle 推理基本一致（23 vs 24）
- ✅ 适合 Android 端集成

**模型文件：**
- 推荐：`opset14_no_fallback.onnx`
- 备选：`opset13_no_fallback.onnx`

**后处理要点：**
1. 输出格式：`[class_id, score, x1, y1, x2, y2]`
2. 应用 Score 阈值过滤（建议 >= 0.5）
3. 坐标已经是原图尺寸，无需额外缩放
4. Class ID：0=seeda, 1=seedb, 2=seedc, 3=seedd

**示例代码片段（伪代码）：**
```java
// 假设 output 是 ONNX 推理输出 float[300][6]
List<Detection> detections = new ArrayList<>();
for (int i = 0; i < output.length; i++) {{
    float classId = output[i][0];
    float score = output[i][1];
    float x1 = output[i][2];
    float y1 = output[i][3];
    float x2 = output[i][4];
    float y2 = output[i][5];
    
    if (score >= 0.5f) {{
        detections.add(new Detection((int)classId, score, x1, y1, x2, y2));
    }}
}}
```

## 5. 可视化对比

所有标注图保存在 `{output_dir}/`：
- `paddle_reference.png` - Paddle 推理基准（24 个检测，绿色框）
- `annotated_opset13_no_fallback.png` - opset 13 ONNX（23 个检测，红色框）
- `annotated_opset14_no_fallback.png` - opset 14 ONNX（23 个检测，红色框）✅ **推荐用于 Android**

## 6. 下一步行动

1. ✅ 已完成：生成所有测试标注图
2. ✅ 已完成：验证 ONNX 检测精度
3. 📋 待办：将 `opset14_no_fallback.onnx` 集成到 Android app
4. 📋 待办：在 Android 端验证推理速度与精度
5. 📋 待办：如需要，从 `output/best_model.pdparams` 重新导出并测试

## 7. 已知问题与解决方案

### 问题 1：之前从 `output/best_model.pdparams` 导出的 ONNX 返回空检测
**原因：** 使用了不匹配的 config（L-config vs M-checkpoint）导致权重加载不完整
**解决：** 使用正确的 M-config 导出，或直接使用 server-exported 模型

### 问题 2：Paddle Fallback ONNX 在 Android 上可能不兼容
**原因：** Paddle Fallback 需要额外的自定义算子支持
**解决：** 使用纯 ONNX（opset 13/14，无 fallback）已验证可用

---
报告生成完毕。所有标注图可供视觉验证。
"""

report_path = os.path.join(output_dir, 'comparison_report.md')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(f'Report generated: {report_path}')
print(f'\n{report}')

# Android ONNX集成 - 坐标缩放修复总结

## 📋 修改清单

### 修改的文件
**`android-app/app/src/main/java/com/bohuyeshan/buckwheat/inference/InferenceEngine.kt`**

### 关键修复点

#### 1. Nx6格式解析修复 (第805-855行)

**问题**: 原代码假设格式是 `[x1,y1,x2,y2,score,class]`

**实际格式**: PaddleDetection ONNX输出是 `[class, score, x1, y1, x2, y2]`

**修复内容**:
- ✅ 正确解析 `[class, score, x1, y1, x2, y2]` 格式
- ✅ 检测坐标是否需要手动缩放 (maxCoord < 1000)
- ✅ 应用手动缩放: `coord * metadata.scaleX/Y`
- ✅ 正确构建per-class scores数组

```kotlin
// 关键代码片段:
val needsManualScaling = (maxCoord > 0f && maxCoord < 1000f)
val manualScaleX = if (needsManualScaling) metadata.scaleX else 1f
val manualScaleY = if (needsManualScaling) metadata.scaleY else 1f

// 应用缩放
boxes[r * 4 + 0] = flat[base + 2] * manualScaleX  // x1
boxes[r * 4 + 1] = flat[base + 3] * manualScaleY  // y1
boxes[r * 4 + 2] = flat[base + 4] * manualScaleX  // x2
boxes[r * 4 + 3] = flat[base + 5] * manualScaleY  // y2
```

#### 2. 坐标逆变换逻辑修复 (第719-798行)

**问题**: 总是应用letterbox逆变换,即使坐标已经被手动缩放

**修复**: 检测坐标是否已经在原图尺度,避免重复变换

```kotlin
// 检测坐标范围
var maxCoord = 0f
for (index in 0 until numDetections) {
    val boxOffset = index * 4
    maxCoord = max(maxCoord, max(...))
}
val alreadyScaled = (maxCoord > 1000f)

// 条件应用变换
if (alreadyScaled) {
    // 未缩放,应用letterbox逆变换
    x1 = ((boxesArray[boxOffset] - metadata.padX) * invScaleX).coerceIn(0f, imageWidth)
    ...
}
```

## 🔍 工作原理

### 问题根源
模型输出的坐标仍在 `800x800` 尺度,虽然传入了 `scale_factor`,但模型并未使用它自动缩放输出坐标。

### 解决方案
在Android后处理阶段手动缩放:

```
原图尺寸: 3468 x 4624
模型输入: 800 x 800
缩放因子: [4.335, 5.78]

模型输出坐标范围: [31-123] (800x800尺度)
手动缩放后范围: [136-713] (原图尺度) ✅
```

### 缩放公式
```kotlin
scaleX = originalWidth / MODEL_INPUT_SIZE  // 3468 / 800 = 4.335
scaleY = originalHeight / MODEL_INPUT_SIZE // 4624 / 800 = 5.78

x_original = x_model * scaleX
y_original = y_model * scaleY
```

## ✅ 验证方法

### 1. 查看日志输出
启用debug模式后,检查日志:
```
Nx6 format: rows=300, maxCoord=123.4, needsManualScaling=true, manualScale=[4.335, 5.78]
parseDetections: numDet=300, numCls=4, maxCoord=713.5, alreadyScaled=true
```

### 2. 检查检测结果
- 检测数量: 约25个 (score >= 0.5)
- 边界框不应堆积在左上角
- 边界框不应是长条形
- 边界框应正确框住荞麦种子

### 3. 对比Python结果
- Python ONNX: 25个检测
- Android ONNX: 应该也是25个检测
### 确保正确的模型和配置

2. **标签文件**: `app/src/main/assets/models/labels.json`
   ```json
   {
     "labels": ["seeda", "seedb", "seedc", "seedd"],
     "input_size": 800,
     "score_threshold": 0.5
   }
   ```

3. **测试代码** (MainActivity或ImageManagerActivity):
```kotlin
// 启用debug模式查看详细日志
val sharedPrefs = getSharedPreferences("buckwheat_prefs", Context.MODE_PRIVATE)
sharedPrefs.edit().putBoolean("debug_mode", true).apply()

// 运行推理
val result = inferenceEngine.runInference(bitmap)
result.onSuccess { inferenceResult ->
    val detections = inferenceResult.detections
    Log.d("Detection", "Found ${detections.size} seeds")
    detections.forEach { det ->
        Log.d("Detection", "  ${det.label}: ${det.score} at ${det.boundingBox}")
    }
}
```

## 🎯 预期结果

### 正常输出示例
```
Nx6 format: rows=300, maxCoord=123.4, needsManualScaling=true, manualScale=[4.335, 5.78]
parseDetections: numDet=300, numCls=4, maxCoord=713.5, alreadyScaled=true
Found 25 seeds
  seedb: 0.90 at BoundingBox(327.7, 574.9, 348.9, 609.5)
  seedb: 0.86 at BoundingBox(136.7, 460.4, 165.7, 501.2)
  ...
```

### 异常情况
如果看到:
- `maxCoord < 100` → 坐标未正确缩放
- `Found 0 seeds` → 检查score threshold或模型加载
- 边界框超出图像范围 → 检查metadata.scaleX/Y计算

## 🔧 调试技巧

1. **启用debug模式**:
```kotlin
2. **查看ONNX输出dump**:
   - 文件位置: `cache/photos/onnx_dump_*.json`
   - 包含原始模型输出,用于验证格式

3. **检查metadata**:
```kotlin
Logger.i(TAG, "Metadata: srcSize=${metadata.sourceWidth}x${metadata.sourceHeight}, " +
              "scale=[${metadata.scaleX}, ${metadata.scaleY}], " +
              "pad=[${metadata.padX}, ${metadata.padY}]")
```

## 📚 相关文件

### Python参考实现
- `android-app/onnx_annotate_fixed.py` - 正确的Python推理脚本
- `android-app/坐标修复报告.md` - 详细技术分析
- `android-app/使用指南_修复版.md` - Python使用指南

### Android代码
- `InferenceEngine.kt` - 已修复的推理引擎
- `Detection.kt` - 检测结果数据类
- `DetectionOverlayView.kt` - 可视化绘制
- `android-app/output/paddle_baseline_fixed.png` - Paddle标注示例(绿框)

   - 拍照后运行推理
   - 在DetectionOverlayView上显示结果
   - 测量推理时间
   - 考虑GPU加速 (NNAPI)
   - 批处理优化

3. **用户体验**
   - 添加实时预览
   - 显示检测统计
   - 保存标注结果

## ✨ 总结

**核心修复**: 在Nx6格式解析时,正确识别PaddleDetection的 `[class, score, x1, y1, x2, y2]` 格式,并在坐标还在800x800尺度时应用手动缩放。

**验证方法**: 检测数量应为25个左右,边界框应正确框住种子,不堆积在左上角。

**现在可以开始Android应用开发了!** 🎉

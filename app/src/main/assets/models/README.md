# Android ONNX 模型集成指南

## 模型文件

- **模型路径**: `app/src/main/assets/models/model.onnx`
- **标签配置**: `app/src/main/assets/models/labels.json`
- **模型类型**: PPYOLOEPlus CRN-M (Speed Optimized)
- **ONNX Opset**: 14
- **模型来源**: Server exported Paddle inference model

## 模型输入输出规格

### 输入

1. **图像输入** (`image`):
   - 形状: `[1, 3, 800, 800]`
   - 数据类型: `float32`
   - 预处理步骤:
     ```java
     // 1. 调整图像大小到 800x800
     Bitmap resized = Bitmap.createScaledBitmap(original, 800, 800, true);
     
     // 2. 归一化 (除以 255.0)
     float[][][] normalized = new float[3][800][800];
     for (int y = 0; y < 800; y++) {
         for (int x = 0; x < 800; x++) {
             int pixel = resized.getPixel(x, y);
             normalized[0][y][x] = Color.red(pixel) / 255.0f;
             normalized[1][y][x] = Color.green(pixel) / 255.0f;
             normalized[2][y][x] = Color.blue(pixel) / 255.0f;
         }
     }
     
     // 3. 转换为 [1, 3, 800, 800] 张量
     FloatBuffer buffer = ...; // 填充 normalized 数据 (CHW 格式)
     ```

2. **缩放因子** (`scale_factor`):
   - 形状: `[1, 2]`
   - 数据类型: `float32`
   - 计算方式:
     ```java
     float scaleX = (float)originalWidth / 800.0f;
     float scaleY = (float)originalHeight / 800.0f;
     float[] scaleFactor = {scaleX, scaleY};
     ```

### 输出

1. **检测结果** (第一个输出):
   - 形状: `[300, 6]`
   - 数据类型: `float32`
   - 列格式: `[class_id, score, x1, y1, x2, y2]`
   - 说明:
     - `class_id`: 类别编号 (0=seeda, 1=seedb, 2=seedc, 3=seedd)
     - `score`: 置信度分数 (0.0~1.0)
     - `x1, y1, x2, y2`: 边界框坐标（**已缩放到原图尺寸**）

2. **检测数量** (第二个输出):
   - 形状: `[1]`
   - 数据类型: `int32`
   - 说明: 固定为 300（需手动根据 score 过滤）

## 后处理步骤

```java
// 解析检测结果
float[][] detections = getONNXOutput(0); // 获取第一个输出 [300, 6]

List<Detection> validDetections = new ArrayList<>();
for (int i = 0; i < detections.length; i++) {
    float classId = detections[i][0];
    float score = detections[i][1];
    float x1 = detections[i][2];
    float y1 = detections[i][3];
    float x2 = detections[i][4];
    float y2 = detections[i][5];
    
    // 应用置信度阈值过滤
    if (score >= 0.5f) {
        // 坐标已经是原图尺寸，无需额外缩放
        validDetections.add(new Detection(
            (int)classId, 
            score,
            (int)x1, (int)y1, (int)x2, (int)y2
        ));
    }
}
```

## 类别映射

```java
String[] labels = {"seeda", "seedb", "seedc", "seedd"};

for (Detection det : validDetections) {
    String className = labels[det.classId];
    System.out.println(String.format(
        "检测到 %s (置信度: %.2f) 位置: (%d,%d)-(%d,%d)",
        className, det.score, 
        det.x1, det.y1, det.x2, det.y2
    ));
}
```

## ONNXRuntime 依赖

在 `app/build.gradle` 中添加:

```gradle
dependencies {
    implementation 'com.microsoft.onnxruntime:onnxruntime-android:latest.release'
}
```

## 性能建议

1. **Score 阈值**: 建议使用 0.5（过滤后约 20-25 个有效检测）
2. **输入尺寸**: 固定为 800x800（不可更改）
3. **推理速度**: 约 100-300ms/图（取决于设备性能）
4. **线程**: 建议在后台线程执行推理，避免阻塞 UI

## 已验证的测试结果

- **测试图片**: 3468 x 4624 px
- **Paddle 推理**: 24 个检测 (score >= 0.5)
- **ONNX 推理**: 23 个检测 (score >= 0.5)
- **精度偏差**: < 5% (可接受)
- **标注图对比**: 见 `android-app/output/`
  - `paddle_reference.png` - Paddle 基准（绿色框）
  - `annotated_opset14_no_fallback.png` - ONNX 结果（红色框）

## 问题排查

### 问题1: ONNX 加载失败
- 确认 ONNXRuntime 版本 >= 1.8
- 确认模型文件完整且未损坏
- 检查 assets 路径正确

### 问题2: 推理返回空结果
- 确认预处理步骤正确（归一化、CHW 格式）
- 确认 scale_factor 计算正确
- 检查 score 阈值设置

### 问题3: 坐标不正确
- 坐标已经是原图尺寸，**无需额外缩放**
- 如果显示不正确，检查是否误用了模型输入尺寸缩放

## 参考资料

- 完整测试报告: `android-app/output/comparison_report.md`
- Python 参考实现: `android-app/onnx_annotate_image.py`
- Paddle 推理参考: `android-app/paddle_annotate.py`

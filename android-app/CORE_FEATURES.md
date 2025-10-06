# 荞麦籽粒质量检测 APP - 核心功能说明

## 📱 核心功能

### 1. 实时检测模式 (Realtime Mode)
- **功能**：使用 CameraX 进行连续的视频流分析
- **触发方式**：点击底部的 🔄 模式切换按钮，切换到 "Realtime" 模式
- **工作原理**：
  - CameraX Preview 实时显示相机画面
  - `CameraAnalyzer` 分析每一帧图像
  - `InferenceEngine` 对图像进行 ONNX 推理
  - 检测结果通过 `DetectionOverlayView` 实时叠加显示
- **性能优化**：
  - 使用 `STRATEGY_KEEP_ONLY_LATEST` 防止帧积压
  - 自动跳过过时的帧
  - 会话重建机制防止崩溃

### 2. 单张拍照检测模式 (Single Mode)
- **功能**：高分辨率单张照片捕获和分析
- **触发方式**：
  1. 点击 🔄 切换到 "Single" 模式
  2. 点击底部中央的 📷 快门按钮
- **工作原理**：
  - `ImageCapture` 捕获高分辨率 JPEG
  - 保存到缓存目录 `cache/photos/`
  - 解码并通过 `InferenceEngine.runInference(Bitmap)` 分析
  - 显示检测结果在预览画面上
- **优势**：
  - 更高分辨率（相比视频流）
  - 适合精确标注和保存
  - 支持从相册加载已有照片

### 3. 性能监控面板 🔍
- **开关方式**：**点击顶部状态栏文字**即可显示/隐藏性能面板
- **监控指标**：
  - **FPS**：每秒检测帧数（实时模式下）
  - **CPU**：当前 APP 的 CPU 使用率 (%)
  - **内存**：总 PSS 内存占用 (MB)
    - Native Heap：原生层（ONNX Runtime）内存
    - Dalvik Heap：Java/Kotlin 层内存
  - **GPU**：显示 "N/A"（Android 系统限制无法直接获取）
  - **NPU**：显示 "N/A"（需要厂商特定 API）
- **更新频率**：每 500ms 刷新一次
- **显示位置**：右上角半透明黑色面板

---

## 🎯 使用流程

### 快速开始
1. **启动 APP** → 授予相机权限
2. **实时检测**：
   - 保持默认 "Realtime" 模式
   - 对准荞麦籽粒
   - 实时显示边界框和标签
3. **拍照检测**：
   - 切换到 "Single" 模式
   - 点击快门按钮
   - 等待结果叠加显示
4. **查看性能**：
   - 点击顶部状态栏
   - 观察 FPS/CPU/内存等指标

### 高级功能
- **长按状态栏**：打开设置和诊断界面
- **长按设置按钮**：导出最新 ONNX 输入 JSON（用于调试）
- **表情符号模式**：点击 😊 按钮启用 emoji 叠加渲染
- **照片管理**：点击 📁 按钮浏览已保存的检测照片

---

## 🛠️ 技术架构

### 推理引擎 (`InferenceEngine.kt`)
- **会话管理**：
  - `initialize()`: 初始化 ONNX Runtime 会话
  - `resetSessionLocked()`: 重置会话（错误恢复）
  - `createSessionLocked()`: 创建新会话
  - `handleInferenceFailureLocked()`: 处理推理失败并自动重建会话
- **推理入口**：
  - `runInference(ImageProxy)`: 实时流处理
  - `runInference(Bitmap)`: 单张图片处理
- **重试机制**：最多 2 次尝试，第一次失败后自动重建会话
- **调试模式**：通过设置启用后可转储输入/输出张量

### 相机分析器 (`CameraAnalyzer.kt`)
- 实现 `ImageAnalysis.Analyzer` 接口
- 在协程中异步调用 `InferenceEngine`
- 自动过滤 `CancellationException`（避免 UI 错误提示）
- 完成后自动关闭 `ImageProxy`

### 性能监控器 (`PerformanceMonitor.kt`)
- **FPS 计算**：通过 `recordFrame()` 统计帧率
- **CPU 监控**：读取 `/proc/stat` 和 `/proc/[pid]/stat`
- **内存监控**：使用 `Debug.MemoryInfo` 获取 PSS 数据
- **快照导出**：`getSnapshot()` 返回完整性能指标

### 检测叠加视图 (`DetectionOverlayView.kt`)
- 自定义 `View` 用于绘制检测框
- 支持多标签、置信度显示
- 可选 emoji 渲染模式
- 自动缩放适配不同分辨率

---

## 🐛 故障排查

### "OrtSession closed" 错误
- **已修复**：现在有自动会话重建机制
- 如果仍然出现，检查日志并通过 "Restart Inference" 手动重建

### 实时检测卡顿
- 点击状态栏查看 FPS 和 CPU 使用率
- 如果 CPU > 80%，可能需要降低分辨率或优化模型
- 检查内存是否接近设备上限

### 拍照后无检测结果
- 确认切换到 "Single" 模式
- 检查 logcat 是否有推理错误
- 长按设置按钮导出 ONNX 输入查看张量数据

### 性能面板不显示
- 点击（非长按）顶部状态栏文字
- 确认 `performancePanel` visibility 切换生效
- 检查是否有 UI 绘制异常

---

## 📊 性能基准

### 测试环境
- 设备：[填入实际测试设备]
- 模型：PaddleDetection PPYOLOv2
- 输入尺寸：640×640

### 预期指标
- **FPS**：15-30 fps（取决于设备）
- **CPU**：40-70%（单核推理）
- **内存**：150-300 MB（包括相机缓冲区）
- **延迟**：30-70 ms/帧

---

## 🔄 更新日志

### v1.2.0 (2025-10-05)
- ✅ 修复会话关闭导致的崩溃问题
- ✅ 添加自动会话重建机制
- ✅ 实现完整的实时检测流程
- ✅ 实现单张拍照检测功能
- ✅ 新增性能监控面板
- ✅ 集成 FPS/CPU/内存实时显示

### v1.1.0
- 初始版本
- 基础 ONNX 推理
- CameraX 集成

---

## 📝 开发者备注

### 待优化项
1. **GPU/NPU 监控**：需要厂商 SDK 集成
2. **模型量化**：考虑 INT8 量化减少内存和延迟
3. **多线程优化**：分离预处理和推理线程
4. **批处理**：单张模式下可批量处理多张照片

### 已知限制
- GPU/NPU 使用率无法通过标准 Android API 获取
- 部分低端设备可能无法达到 15 FPS
- 高分辨率输入会显著增加内存占用

---

## 🎓 参考资料

- [ONNX Runtime for Android](https://onnxruntime.ai/docs/tutorials/mobile/)
- [CameraX Documentation](https://developer.android.com/training/camerax)
- [Android Performance Monitoring](https://developer.android.com/topic/performance)
- [PaddleDetection](https://github.com/PaddlePaddle/PaddleDetection)

# 荞麦种子检测APP - 快速上手指南

## 🚀 快速启动

### 1. 安装APK
```bash
# 构建APK
cd android-app
./gradlew assembleDebug

# 安装到设备
adb install app/build/outputs/apk/debug/app-debug.apk
```

### 2. 首次使用

1. **授予权限**
   - 打开APP后会请求相机权限
   - 点击"允许"以启用实时检测

2. **开始检测**
   - 相机预览自动启动
   - 将镜头对准荞麦种子
   - 实时检测框会自动出现

3. **查看性能**
   - 右上角显示性能监控面板
   - 实时显示 FPS、CPU、内存使用情况

---

## 📸 功能使用

### 实时检测模式
- **自动运行**: 打开APP即自动开始
- **检测结果**: 彩色边界框 + 标签 + 置信度
- **性能优化**: 每帧推理，自动降帧保持流畅

### 单张拍照检测
1. 点击屏幕底部的 📷 **拍照按钮**
2. 系统自动:
   - 捕获当前帧
   - 运行推理检测
   - 保存结果到相册 (`Pictures/BuckwheatDetections/`)
3. 查看保存的图像，包含完整检测标注

### 切换摄像头
- 点击 🔄 **切换按钮** 在前后摄像头之间切换
- 推理引擎会自动恢复，无需重启

---

## ⚙️ 高级设置

### 开启调试模式
1. 点击右上角 ⚙️ **设置按钮**
2. 勾选 **"调试模式"**
3. 启用后会导出:
   - 输入张量: `cache/photos/onnx_input_*.json`
   - 输出张量: `cache/onnx_dump_*.json`
4. 使用 `adb pull /sdcard/Android/data/com.bohuyeshan.buckwheat/cache/` 提取数据

### 性能监控说明
| 指标 | 含义 | 正常范围 |
|------|------|----------|
| **FPS** | 每秒检测帧数 | 15-30 |
| **CPU** | 进程CPU占用 | 20-40% |
| **内存** | 当前内存使用 | 100-200MB |
| **推理时间** | 单帧耗时 | 30-100ms |

---

## 🐛 常见问题

### Q1: 检测框不显示？
**A**: 
- 确认 `assets/models/best.onnx` 文件存在
- 查看日志: `adb logcat | grep InferenceEngine`
- 重启APP尝试

### Q2: FPS很低（<10）？
**A**:
- 关闭调试模式（会大幅拖慢速度）
- 检查设备性能（老旧设备可能较慢）
- 考虑使用GPU加速（需代码修改）

### Q3: APP崩溃或卡顿？
**A**:
- 已实现会话自动恢复，应能自愈
- 如持续崩溃，查看日志中的异常堆栈
- 尝试清除缓存后重启

### Q4: 拍照保存失败？
**A**:
- 确认已授予存储权限
- 检查存储空间是否充足
- 查看 Toast 提示信息

---

## 📊 性能优化建议

### 提升FPS
1. **降低推理频率**: 修改 `CameraAnalyzer` 每2帧推理1次
2. **启用GPU**: 集成 `onnxruntime-mobile-gpu` 依赖
3. **模型量化**: 将FP32模型转为INT8

### 降低内存占用
1. **缩小输入尺寸**: 当前640x640可降至320x320
2. **减少缓冲**: 调整 `ImageAnalysis` 的队列深度

---

## 🔧 开发者模式

### 查看详细日志
```bash
# 过滤关键日志
adb logcat | grep -E "InferenceEngine|PerformanceMonitor|CameraAnalyzer"

# 导出完整日志
adb logcat > app_logs.txt
```

### 提取调试数据
```bash
# 拉取张量转储
adb pull /sdcard/Android/data/com.bohuyeshan.buckwheat/cache/photos/ ./debug_data/

# 拉取检测结果图像
adb pull /sdcard/Pictures/BuckwheatDetections/ ./results/
```

### 性能分析
```bash
# CPU分析
adb shell top -n 1 | grep buckwheat

# 内存分析
adb shell dumpsys meminfo com.bohuyeshan.buckwheat
```

---

## 📞 技术支持

**遇到问题？**
1. 查看本指南的常见问题部分
2. 检查 `FEATURE_COMPLETION_REPORT.md` 了解架构
3. 收集日志并报告问题

**日志收集命令**:
```bash
adb logcat -d > full_log.txt
adb bugreport bug_report.zip
```

---

**文档版本**: v1.0  
**最后更新**: 2025-10-06  
**适用APP版本**: v1.0-beta

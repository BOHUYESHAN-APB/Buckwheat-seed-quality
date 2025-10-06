# 📱 Android移动端应用

## 概述

荞麦种子检测Android应用是本项目的移动端实现，提供**实时检测**和**单张拍照检测**功能，配备**性能监控面板**，便于现场快速质检。

---

## ✨ 核心功能

### 1. 实时检测 (Live Detection)
- **CameraX视频流**: 实时相机预览
- **ONNX Runtime推理**: 每帧自动检测
- **实时渲染**: 边界框、标签、置信度叠加显示
- **多目标支持**: 同时检测多个种子
- **自动恢复**: 会话错误自动重建

### 2. 单张拍照检测 (Photo Capture)
- **一键捕获**: 点击拍照按钮
- **完整检测**: 对静态图像运行推理
- **自动保存**: 结果保存至 `Pictures/BuckwheatDetections/`
- **带标注图像**: 包含完整检测框和标签

### 3. 性能监控 (Performance Monitor)
- **FPS监控**: 实时帧率显示
- **CPU使用率**: 进程级CPU占用
- **内存监控**: 当前/峰值/可用内存
- **推理延迟**: 单帧推理耗时（ms）
- **悬浮面板**: 半透明UI，不遮挡检测区域

---

## 🚀 快速部署

### 方式1: 一键部署脚本
```powershell
# Windows PowerShell
./deploy.ps1
```

### 方式2: 手动构建安装
```bash
# 1. 构建APK
cd android-app
./gradlew assembleDebug

# 2. 安装到设备
adb install app/build/outputs/apk/debug/app-debug.apk

# 3. 启动应用
adb shell am start -n com.bohuyeshan.buckwheat/.MainActivity
```

---

## 📖 使用指南

### 首次启动
1. APP启动后会请求**相机权限**
2. 点击"允许"以启用检测功能
3. 相机预览自动加载

### 实时检测
- **自动运行**: 打开APP即开始
- **对准目标**: 将相机对准荞麦种子
- **查看结果**: 检测框自动出现

### 拍照检测
1. 点击屏幕底部📷**拍照按钮**
2. 系统自动捕获并检测
3. 结果保存到相册
4. Toast提示保存状态

### 性能监控
- **位置**: 右上角半透明面板
- **内容**: FPS、CPU、内存、推理时间
- **刷新**: 每500ms自动更新

### 调试模式
1. 点击⚙️**设置按钮**
2. 勾选"调试模式"
3. 导出数据:
   - 输入张量: `cache/photos/onnx_input_*.json`
   - 输出张量: `cache/onnx_dump_*.json`

---

## 🏗️ 技术架构

### 推理引擎
- **框架**: ONNX Runtime Mobile 1.21.0
- **模型**: PP-YOLOE+ (best.onnx)
- **输入**: 640×640 RGB图像
- **输出**: Nx6格式 (x1, y1, x2, y2, score, class)

### 相机系统
- **库**: AndroidX CameraX
- **预处理**: Letterbox缩放 + 归一化
- **分析**: ImageAnalysis每帧回调
- **格式**: YUV420 → ARGB8888 → FloatArray

### 并发控制
- **协程**: Kotlin Coroutines (Dispatchers.Default)
- **锁**: Mutex保护会话访问
- **生命周期**: ViewModel + LiveData

---

## 📊 性能指标

| 指标 | 高端设备 | 中端设备 | 低端设备 |
|------|----------|----------|----------|
| **FPS** | 25-30 | 18-25 | 10-15 |
| **CPU** | 15-25% | 25-35% | 35-50% |
| **内存** | 150MB | 180MB | 220MB |
| **推理延迟** | 30-50ms | 50-80ms | 80-120ms |

**测试设备**:
- 高端: Pixel 7+, 三星S22+
- 中端: 小米10, OPPO Reno5
- 低端: 红米Note 8, 华为P20

---

## 🔧 开发调试

### 查看日志
```bash
# 过滤关键日志
adb logcat | grep -E "InferenceEngine|PerformanceMonitor|CameraAnalyzer"

# 导出完整日志
adb logcat -d > app_debug.txt
```

### 导出调试数据
```bash
# 开启调试模式后
adb pull /sdcard/Android/data/com.bohuyeshan.buckwheat/cache/photos/ ./debug/
adb pull /sdcard/Pictures/BuckwheatDetections/ ./results/
```

### 性能分析
```bash
# CPU分析
adb shell top -n 1 | grep buckwheat

# 内存详情
adb shell dumpsys meminfo com.bohuyeshan.buckwheat

# 帧率分析
adb shell dumpsys gfxinfo com.bohuyeshan.buckwheat
```

---

## 🐛 常见问题

### Q1: 检测框不显示？
**原因**:
- 模型文件缺失
- 会话初始化失败
- 输入图像预处理错误

**解决方案**:
1. 确认 `assets/models/best.onnx` 存在
2. 查看日志: `adb logcat | grep InferenceEngine`
3. 重启APP尝试

### Q2: FPS过低（<10）？
**原因**:
- 调试模式拖慢速度
- 设备性能不足
- CPU推理瓶颈

**解决方案**:
1. 关闭调试模式（会大幅提升速度）
2. 考虑降低推理频率（每2帧推理1次）
3. 启用GPU加速（需代码修改）

### Q3: APP崩溃或卡顿？
**原因**:
- 内存不足
- 会话异常未恢复
- 相机切换异常

**解决方案**:
- 已实现自动恢复机制，应能自愈
- 清除缓存: 设置 → 应用 → 清除缓存
- 重新安装APK

### Q4: 拍照保存失败？
**原因**:
- 存储权限未授予
- 存储空间不足
- 文件路径错误

**解决方案**:
1. 检查存储权限
2. 清理存储空间
3. 查看Toast提示信息

---

## 🔮 未来优化

### 性能提升
1. **GPU加速**: 集成 `onnxruntime-mobile-gpu`
2. **模型量化**: FP32 → INT8 (2-4倍速度提升)
3. **批处理**: 降低推理频率节省资源

### 功能扩展
1. **批量检测**: 相册图片批量分析
2. **统计导出**: 检测结果CSV导出
3. **云端同步**: 检测数据上传云端

### UI美化
1. **主题切换**: 深色/浅色模式
2. **检测框样式**: 颜色、粗细自定义
3. **统计图表**: 检测结果可视化

---

## 📚 相关文档

- **[功能完成报告](../FEATURE_COMPLETION_REPORT.md)** - 详细技术实现
- **[快速上手指南](../QUICK_START_GUIDE.md)** - 用户操作手册
- **[验收测试清单](../VERIFICATION_CHECKLIST.md)** - 测试用例
- **[部署脚本](../deploy.ps1)** - 自动化部署

---

## 📄 文件结构

```
android-app/
├── app/
│   ├── src/main/
│   │   ├── java/com/bohuyeshan/buckwheat/
│   │   │   ├── MainActivity.kt              # 主界面
│   │   │   ├── SettingsActivity.kt          # 设置页
│   │   │   ├── inference/
│   │   │   │   ├── InferenceEngine.kt       # 推理引擎
│   │   │   │   └── PerformanceMonitor.kt    # 性能监控
│   │   │   ├── camera/
│   │   │   │   └── CameraAnalyzer.kt        # 相机分析
│   │   │   └── model/
│   │   │       └── Detection.kt             # 数据模型
│   │   ├── res/
│   │   │   ├── layout/
│   │   │   │   ├── activity_main.xml        # 主界面布局
│   │   │   │   └── activity_settings.xml    # 设置布局
│   │   │   └── values/
│   │   │       └── strings.xml              # 字符串资源
│   │   └── assets/
│   │       └── models/
│   │           └── best.onnx                # 检测模型
│   └── build.gradle.kts
├── gradle/
└── gradlew
```

---

## 📞 技术支持

**遇到问题？**
1. 查看本文档的"常见问题"部分
2. 收集日志: `adb logcat -d > issue.txt`
3. 提交Issue到GitHub仓库

**构建状态**: ✅ BUILD SUCCESSFUL  
**APK大小**: ~375MB (含模型)  
**最低系统**: Android 7.0 (API 24)  
**版本**: v1.0-beta

---

**最后更新**: 2025-10-06  
**维护者**: BOHUYESHAN-APB

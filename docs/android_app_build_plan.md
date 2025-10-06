# Android APP 构建计划

面向即将开始的荞麦种子检测移动应用开发，本计划围绕「以 ONNX 推理在高通设备上实时检测」这一目标，拆解为可执行的阶段任务，并给出所需的模型资产、依赖与验收标准。

> 最新的 Android 工程骨架位于 `android-app/` 目录，可直接在 Android Studio 中导入。下述 Phase 任务默认在该工程上迭代。

## 1. 已就绪的模型与资产

- **ONNX 模型**：
  - `exports/best/ppyoloe_plus_crn_l_300e_coco/model.onnx`
  - `exports/final/ppyoloe_plus_crn_l_300e_coco/model.onnx`
- **Paddle 推理模型**（如需回查后处理逻辑）：同路径下的 `model.pdmodel`、`model.pdiparams`、`infer_cfg.yml`
- **预处理规范**（来自 `infer_cfg.yml`）：
  - 输入尺寸：`640 × 640`
  - 插值方式：`bilinear (interp=2)`
  - `keep_ratio=false` → 直接缩放，不保留纵横比；若需适配实际画面可在 APP 侧实现 letterbox + 去 padding 修正。
  - 归一化：`mean = [0, 0, 0]`，`std = [1, 1, 1]`，`norm_type=none` → 仅需除以 255 并转为 RGB CHW。
- **导出限制**：ONNX 图包含 `multiclass_nms3`，仅支持 `batch=1`。移动端推理需一帧一推。
- **Sanity Check 脚本**：`sandbox_scripts/onnx_sanity_check.py` 可用于后续回归测试。

## 2. 技术栈与依赖

| 模块 | 建议技术/库 | 说明 |
| ---- | ----------- | ---- |
| 开发语言 | Kotlin (Android Studio Giraffe+) | 便于使用 CameraX 与协程 |
| 相机管线 | CameraX Preview + ImageAnalysis | 支持 30fps 帧流，易于控制分辨率与旋转 |
| AI 推理 | ONNX Runtime Mobile (NNAPI EP 优先) | 通过 Gradle `ai.onnxruntime:onnxruntime-android` 引入；启用 NNAPI，fallback 至 GPU/CPU |
| 图像处理 | OpenCV Android SDK *(可选)* / RenderScript Intrinsics *(已废弃)* / 自实现 | 需完成 Resize、通道交换、归一化；优先使用 ByteBuffer + Intrinsics 以减少拷贝 |
| UI 框架 | Jetpack Compose *(推荐)* 或传统 View | Compose 更易构建实时 overlays；若团队更熟悉 XML 亦可 |
| 性能监控 | AndroidX Benchmark、`Choreographer` FPS 统计 | 与 `docs/performance_validation_plan.md` 对齐 |
| 构建系统 | Gradle + Kotlin DSL | 便于集中管理依赖与构建变体 |

## 3. 开发阶段划分

### 3.1 Phase 0 — 项目初始化（1~2 天）

- 创建 Android Studio 工程，`minSdk=26`，`targetSdk=34`。
- 在 `app` module 的 `build.gradle.kts` 中添加：

  ```kotlin
  implementation("ai.onnxruntime:onnxruntime-android:1.18.0")
  implementation("androidx.camera:camera-camera2:1.3.2")
  implementation("androidx.camera:camera-lifecycle:1.3.2")
  implementation("androidx.camera:camera-view:1.3.2")
  implementation("androidx.camera:camera-mlkit-vision:1.3.2") // 可选
  implementation("androidx.compose.ui:ui:1.7.0") // 仅在使用 Compose 时
  ```

- 将 `exports/best/.../model.onnx` 放入 `app/src/main/ml/`（或下载时动态写入 `filesDir`），并记录版本号。
- 配置 `assets/` 中的标签映射（若后续需要自定义类名，可参考训练集标签）。

### 3.2 Phase 1 — 推理封装（2~3 天）

- 编写 `OrtInferenceSession` 封装类，负责：
  - 初始化 ONNX Runtime，`OrtEnvironment` + `OrtSession.SessionOptions`，启用 `NNAPIExecutionProvider`，并在失败时 fallback 至 `GPU`/`CPU`。
  - 预加载 `model.onnx`，缓存输入/输出 `OnnxTensor`。
  - 暴露 `suspend fun run(frame: ImageProxy): DetectionResult` 接口。
- 实现预处理：
  - `ImageProxy` → `ByteBuffer`
  - Resize to 640×640（可先 letterbox 以保持比例，再在绘制时扣除 padding）。
  - BGR → RGB，归一化到 `[0,1]`，转 Float32 CHW。
- 实现后处理：
  - 解析 `multiclass_nms3` 输出（`boxes`, `scores`）。
  - 反算到原图坐标，考虑 letterbox 或非等比缩放。
  - 按置信度阈值筛选，最多 100 框，附带分类标签。

### 3.3 Phase 2 — UI 与交互（2~3 天）

- CameraX 预览 + Overlay：
  - 使用 `PreviewView`（XML）或 Compose `AndroidView`。
  - `ImageAnalysis` 设置 `OUTPUT_IMAGE_FORMAT_YUV_420_888`、`backpressureStrategy=KEEP_ONLY_LATEST`。
- 在 Overlay 上绘制检测框与标签，显示推理时间 / FPS / 当前 EP。
- 添加模式切换：NNAPI / GPU / CPU 三档（若 GPU/NNAPI 不可用，自动灰显）。

### 3.4 Phase 3 — 性能与稳定性验证（3~4 天）

- 按 `docs/performance_validation_plan.md` 执行：
  - 在目标设备（高通）上测 `warm-up`, `steady-state FPS`, `端到端延迟`。
  - 记录功耗温度（可选）。
- 走查内存占用（`adb shell dumpsys meminfo`）。
- 完成崩溃监控（Crashlytics/Firebase 可选）。

### 3.5 Phase 4 — 进阶功能（按需）

- 批量拍照与导出结果。
- 评分/质量分级 UI。
- 本地数据库存储与同步（Room + WorkManager）。
- 多模型切换（final 与 best）。

## 4. 验收与交付物

| 里程碑 | 验收标准 | 交付物 |
| ------ | -------- | ------ |
| MVP Demo | 可在 1 台高通设备上实时推理 ≥15 FPS，支持 NNAPI 优先 | APK + 操作说明 + 性能报告（基于 `performance_validation_plan`） |
| Beta | 稳定运行 1 小时无明显内存泄漏，提供基本导出/分享功能 | APK + QA 报告 + 问题清单 |
| RC | UI 完成度 ≥90%，支持多模型/模式切换，性能数据入库 | APK + Release Note + 使用视频 |

## 5. 开发前检查清单

- [ ] 导出目录内容（ONNX + Paddle 模型）同步至应用仓库或 OSS。
- [ ] 确认模型标签顺序与 Android 端使用的标签文件一致。
- [ ] 样例图像与期望输出准备完毕，用于回归测试。
- [ ] Android Studio、SDK、NDK）版本已对齐团队规范。
- [ ] QA 设备列表整理完成（至少 1 台高通，1 台中端机型）。

## 6. 后续迭代建议

1. **模型轻量化**：并行准备 PP-YOLOE+ M/S 版本，便于在部分设备上回退。
2. **INT8 量化**：配合 Paddle Slim / FastDeploy 工具，探索 INT8 + NNAPI acceleration 的可行性。
3. **自动化测试**：使用 Firebase Test Lab 或 Appetize 进行多机回归；引入截图对比自动化。
4. **CI 集成**：在仓库 CI 中接入导出脚本与 ONNX Sanity Check，保证每次提交都能获得最新推理资产。

---

> 若开始实施，请在 `docs/` 新建执行日志或看板，并同步到《Buckwheat Improvement Roadmap》，保持整体路线一致。

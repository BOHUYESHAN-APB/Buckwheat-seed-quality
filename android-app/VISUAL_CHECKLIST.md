# 标注图检查清单

请按顺序打开并查看以下标注图，验证检测框是否准确标注种子位置。

## 1. Paddle 推理基准（绿色框）

**文件**: `android-app/output/paddle_reference.png`  
**检测数**: 24 个（score >= 0.5）  
**框颜色**: 绿色  
**用途**: 作为对比基准，这是使用 Paddle 原生推理生成的标注图

✅ **检查要点**:
- 绿色框是否准确圈出每个种子
- 标签是否显示正确的类别和置信度
- 是否有明显的漏检或误检

---

## 2. ONNX 推理结果（红色框）

### 2.1 opset 13（推荐用于 Android）

**文件**: `android-app/output/annotated_opset13_no_fallback.png`  
**检测数**: 23 个（score >= 0.5）  
**框颜色**: 红色  
**状态**: ✅ 可用

✅ **检查要点**:
- 红色框位置是否与 Paddle 基准（绿色框）基本一致
- 检测数 23 vs 24，差异是否可接受
- 是否有异常的长直线或错位框

### 2.2 opset 14（**强烈推荐用于 Android**）

**文件**: `android-app/output/annotated_opset14_no_fallback.png`  
**检测数**: 23 个（score >= 0.5）  
**框颜色**: 红色  
**状态**: ✅ **推荐** - 这是准备集成到 Android app 的模型

✅ **检查要点**:
- 红色框位置是否与 Paddle 基准（绿色框）基本一致
- 这个标注图应该与 opset 13 版本几乎相同
- 确认没有大量不相关的竖线或横线

### 2.3 opset 14（禁用 auto_update，备选）

**文件**: `android-app/output/annotated_opset14_no_fallback_no_auto.png`  
**检测数**: 23 个（score >= 0.5）  
**框颜色**: 红色  
**状态**: ✅ 备选方案

✅ **检查要点**:
- 应该与上面的 opset 14 版本几乎相同
- 作为备选验证，确认转换参数差异不影响结果

### 2.4 Paddle Fallback ONNX（包含自定义算子）

**文件**: `android-app/output/annotated_server_fallback_onnx_v2.png`  
**检测数**: 24 个（未过滤原始输出）  
**框颜色**: 红色  
**状态**: ✅ 可用，但可能在 Android 端不兼容

ℹ️ **说明**:
- 这个版本使用了 Paddle Fallback 自定义算子
- 检测数与 Paddle 推理一致（24 个）
- 在 Android 端可能需要额外的 runtime 支持
- **不推荐用于 Android**，仅作参考对比

---

## 3. 早期问题版本（已修复）

### 3.1 出现方格线的版本

**文件**: 用户上传的附件（含大量竖横直线）  
**问题**: 脚本误解析输出格式，导致错误绘制

✅ **对比要点**:
- 新版本标注图应该**没有**大量不相关的长直线
- 框应该紧贴种子周围，不是整图网格

---

## 4. 验证总结

### 预期结果

查看上述标注图后，应该满足：

1. ✅ **Paddle 基准图**（绿色框）显示清晰的种子检测
2. ✅ **ONNX opset 14 图**（红色框）与 Paddle 基准基本一致
3. ✅ 检测数差异在 1-2 个以内（23 vs 24）
4. ✅ **无大量竖横直线**或网格状错误标注
5. ✅ 框位置准确，类别标签正确

### 如果出现问题

如果标注图显示异常：
- 检查 `android-app/output/comparison_report.md` 的详细分析
- 查看 `app/src/main/assets/models/README.md` 的排查指南
- 运行 `android-app/analyze_onnx_output.py` 分析 ONNX 输出统计

---

## 5. 下一步

确认所有标注图正确后：

1. 📋 阅读 `app/src/main/assets/models/README.md` - Android 集成指南
2. 📋 阅读 `android-app/output/comparison_report.md` - 完整测试报告
3. 📋 在 Android app 中加载 `app/src/main/assets/models/model.onnx`
4. 📋 实现后处理逻辑并在设备上测试

---

**所有标注图路径**: `android-app/output/`  
**Android 模型路径**: `app/src/main/assets/models/model.onnx`  
**集成指南**: `app/src/main/assets/models/README.md`

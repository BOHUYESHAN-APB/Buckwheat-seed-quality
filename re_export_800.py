#!/usr/bin/env python3
"""重新导出ONNX模型为800x800输入"""

import paddle2onnx
import onnx
from pathlib import Path

# 源模型路径
model_dir = r"E:\CODE\Buckwheat-seed-quality\inference_model\ppyoloe_plus_crn_m_300e_speed_optimized"
model_file = Path(model_dir) / "model.pdmodel"
params_file = Path(model_dir) / "model.pdiparams"

# 输出路径
output_file = r"E:\CODE\Buckwheat-seed-quality\android-app\app\src\main\assets\models\model_800x800.onnx"

print(f"📂 源模型: {model_dir}")
print(f"📤 输出到: {output_file}")
print()

# 读取Paddle模型
with open(model_file, 'rb') as f:
    model_content = f.read()
with open(params_file, 'rb') as f:
    params_content = f.read()

print("🔄 转换中...")

# 转换,指定输入形状
onnx_model_bytes = paddle2onnx.export(
    model_file=str(model_file),
    params_file=str(params_file),
    opset_version=11,
    enable_onnx_checker=True,
    input_shape_dict={"image": [1, 3, 800, 800], "scale_factor": [1, 2]}
)

# 保存
with open(output_file, 'wb') as f:
    f.write(onnx_model_bytes)

print(f"✅ 导出成功! 大小: {len(onnx_model_bytes) / 1024 / 1024:.2f} MB")

# 验证
model = onnx.load(output_file)
for inp in model.graph.input:
    dims = [d.dim_value if d.dim_value > 0 else d.dim_param for d in inp.type.tensor_type.shape.dim]
    print(f"📊 输入 '{inp.name}': {dims}")

print("\n✅ 模型输入尺寸已修正为800x800!")

#!/usr/bin/env python3
"""
使用ONNX API直接修改模型的输入形状
从640x640改为800x800
"""

import onnx
from onnx import helper, TensorProto
from pathlib import Path

# 源模型
source_model = r"E:\CODE\Buckwheat-seed-quality\android-app\app\src\main\assets\models\model.onnx"
output_model = r"E:\CODE\Buckwheat-seed-quality\android-app\app\src\main\assets\models\model_800x800.onnx"

print("📂 加载ONNX模型...")
model = onnx.load(source_model)

print("\n📊 当前输入形状:")
for inp in model.graph.input:
    dims = [d.dim_value if d.dim_value > 0 else d.dim_param for d in inp.type.tensor_type.shape.dim]
    print(f"   {inp.name}: {dims}")

print("\n🔧 修改输入形状...")

# 修改每个输入的维度
for inp in model.graph.input:
    shape = inp.type.tensor_type.shape
    if inp.name == "image":
        # 修改为800x800
        if len(shape.dim) == 4:
            shape.dim[2].dim_value = 800  # height
            shape.dim[3].dim_value = 800  # width
            print(f"   ✅ {inp.name}: 修改为 [1, 3, 800, 800]")

print("\n📊 新输入形状:")
for inp in model.graph.input:
    dims = [d.dim_value if d.dim_value > 0 else d.dim_param for d in inp.type.tensor_type.shape.dim]
    print(f"   {inp.name}: {dims}")

# 保存
print(f"\n💾 保存到: {output_model}")
onnx.save(model, output_model)

# 验证
print("\n🔍 验证新模型...")
try:
    onnx.checker.check_model(output_model)
    print("✅ 模型验证通过!")
except Exception as e:
    print(f"⚠️  验证警告: {e}")

# 显示文件大小
size = Path(output_model).stat().st_size / 1024 / 1024
print(f"📦 文件大小: {size:.2f} MB")

print("\n✅ 完成!")
print("\n下一步:")
print(f"1. 将新模型重命名:")
print(f"   {output_model}")
print(f"   -> E:\\CODE\\Buckwheat-seed-quality\\android-app\\app\\src\\main\\assets\\models\\model.onnx")
print(f"2. 回退代码中的强制800修改 (因为现在模型自己声明800了)")
print(f"3. 重新编译APK并测试")

#!/usr/bin/env python3
"""调整ONNX模型中的常量Reshape尺寸, 将640网格更新为800对应的网格"""
import onnx
from onnx import numpy_helper
from pathlib import Path

MODEL_PATH = Path(r"E:\\CODE\\Buckwheat-seed-quality\\android-app\\app\\src\\main\\assets\\models\\model.onnx")
BACKUP_PATH = MODEL_PATH.with_name("model_before_shape_adjust.onnx")

print(f"📂 读取模型: {MODEL_PATH}")
model = onnx.load(str(MODEL_PATH))

# 需要替换的映射: 原值 -> 新值
replacements = {
    400: 625,   # 20x20 -> 25x25
    1600: 2500, # 40x40 -> 50x50
    6400: 10000 # 80x80 -> 100x100
}

changed = 0
for node in model.graph.node:
    if node.op_type != "Constant":
        continue
    for attr in node.attribute:
        if attr.name != "value":
            continue
        arr = numpy_helper.to_array(attr.t)
        if arr.size == 0:
            continue
        updated = False
        flat = arr.flatten()
        for old_val, new_val in replacements.items():
            matches = flat == old_val
            if matches.any():
                flat[matches] = new_val
                updated = True
        if updated:
            new_arr = flat.reshape(arr.shape)
            new_tensor = numpy_helper.from_array(new_arr, attr.t.name or node.output[0])
            attr.t.CopyFrom(new_tensor)
            print(f"✅ 更新常量 {node.output[0]} : {arr} -> {new_arr}")
            changed += 1

if changed == 0:
    print("⚠️ 未找到需要更新的常量, 模型未修改。")
else:
    if not BACKUP_PATH.exists():
        MODEL_PATH.replace(BACKUP_PATH)
        print(f"🗂️ 已备份原模型到 {BACKUP_PATH}")
        save_path = MODEL_PATH
    else:
        save_path = MODEL_PATH
    onnx.save(model, str(save_path))
    print(f"💾 已保存修改后的模型到 {save_path}")

    # 校验
    onnx.checker.check_model(str(save_path))
    print("🔍 ONNX 检查通过")

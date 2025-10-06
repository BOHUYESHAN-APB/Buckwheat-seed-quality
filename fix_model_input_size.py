#!/usr/bin/env python3
"""
重新导出ONNX模型,修正输入尺寸为800x800

问题: 当前model.onnx定义输入为640x640,但模型训练使用800x800
解决: 使用Paddle2ONNX重新导出,强制指定输入形状为800x800
"""

import os
import sys
import subprocess
from pathlib import Path

def find_paddle_model():
    """查找Paddle模型文件"""
    search_paths = [
        "inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized",
        "output",
        "."
    ]
    
    for base in search_paths:
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.endswith('.pdmodel'):
                    model_path = Path(root) / f
                    param_path = model_path.with_suffix('.pdiparams')
                    if param_path.exists():
                        return model_path.parent / model_path.stem
    return None

def export_onnx_with_800():
    """使用Paddle2ONNX重新导出模型,指定800x800输入"""
    
    # 查找Paddle模型
    model_prefix = find_paddle_model()
    if not model_prefix:
        print("❌ 未找到Paddle模型文件(.pdmodel + .pdiparams)")
        print("\n请手动指定模型路径,或确保以下目录存在模型文件:")
        print("  - inference_model/server_export/output_inference/")
        print("  - output/")
        return False
    
    print(f"✅ 找到Paddle模型: {model_prefix}")
    
    # 准备输出路径
    output_dir = Path("android-app/app/src/main/assets/models")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model_800x800.onnx"
    
    # 构建Paddle2ONNX命令
    cmd = [
        "paddle2onnx",
        "--model_dir", str(model_prefix.parent),
        "--model_filename", f"{model_prefix.name}.pdmodel",
        "--params_filename", f"{model_prefix.name}.pdiparams",
        "--save_file", str(output_path),
        "--opset_version", "11",
        "--enable_onnx_checker", "True",
        "--input_shape_dict", '{"image":[1,3,800,800],"scale_factor":[1,2]}'
    ]
    
    print("\n🔧 执行命令:")
    print(" ".join(cmd))
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print(f"\n✅ 成功导出模型到: {output_path}")
        print(f"📦 文件大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # 验证输出
        try:
            import onnx
            model = onnx.load(str(output_path))
            dims = [str(d.dim_value) if d.dim_value > 0 else str(d.dim_param) 
                   for d in model.graph.input[0].type.tensor_type.shape.dim]
            print(f"✅ 验证新模型输入形状: {' x '.join(dims)}")
            
            if '800' in dims:
                print("\n✅ 输入尺寸修正成功!")
                print(f"\n下一步:")
                print(f"1. 将新模型重命名: {output_path} -> {output_dir / 'model.onnx'}")
                print(f"2. 重新编译APK")
                print(f"3. 安装到设备测试")
                return True
            else:
                print(f"\n⚠️ 输入尺寸仍然不是800: {dims}")
                return False
                
        except ImportError:
            print("⚠️ 无法验证(需要安装onnx: pip install onnx)")
            print(f"请手动检查: {output_path}")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 导出失败:")
        print(e.stderr)
        print("\n可能的解决方案:")
        print("1. 安装paddle2onnx: pip install paddle2onnx")
        print("2. 检查Paddle模型文件是否完整")
        print("3. 尝试手动运行上述命令")
        return False
    except FileNotFoundError:
        print("❌ paddle2onnx 未安装")
        print("\n安装命令: pip install paddle2onnx")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("修正ONNX模型输入尺寸: 640x640 -> 800x800")
    print("=" * 60)
    print()
    
    success = export_onnx_with_800()
    sys.exit(0 if success else 1)

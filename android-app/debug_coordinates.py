#!/usr/bin/env python3
"""
调试脚本:对比Paddle和ONNX的原始输出数据
"""
import numpy as np
import onnxruntime as ort
from PIL import Image
import paddle.inference as paddle_infer

def preprocess_image(img_path, target_size=800):
    """统一的预处理"""
    img = Image.open(img_path).convert('RGB')
    orig_w, orig_h = img.size
    
    # 调整大小
    img_resized = img.resize((target_size, target_size), Image.LANCZOS)
    
    # 转换为numpy数组并归一化
    img_array = np.array(img_resized, dtype='float32')
    img_array = img_array / 255.0
    
    # HWC -> CHW
    img_array = img_array.transpose((2, 0, 1))
    
    # 添加batch维度
    img_array = img_array[np.newaxis, :]
    
    return img_array, orig_w, orig_h

def run_paddle_inference(model_dir, img_path):
    """运行Paddle推理并返回原始输出"""
    print("\n=== Paddle推理 ===")
    
    # 配置
    config = paddle_infer.Config(
        f"{model_dir}/model.pdmodel",
        f"{model_dir}/model.pdiparams"
    )
    config.enable_use_gpu(1000, 0)
    config.switch_use_feed_fetch_ops(False)
    config.switch_ir_optim(True)
    
    predictor = paddle_infer.create_predictor(config)
    
    # 预处理
    img_array, orig_w, orig_h = preprocess_image(img_path)
    
    # 准备输入
    input_names = predictor.get_input_names()
    
    # image输入
    input_tensor = predictor.get_input_handle(input_names[0])
    input_tensor.copy_from_cpu(img_array)
    
    # scale_factor输入
    scale_factor = np.array([[orig_w / 800.0, orig_h / 800.0]], dtype='float32')
    scale_tensor = predictor.get_input_handle(input_names[1])
    scale_tensor.copy_from_cpu(scale_factor)
    
    print(f"原始图像尺寸: {orig_w}x{orig_h}")
    print(f"Scale factor: {scale_factor}")
    
    # 推理
    predictor.run()
    
    # 获取输出
    output_names = predictor.get_output_names()
    output_tensor = predictor.get_output_handle(output_names[0])
    output_data = output_tensor.copy_to_cpu()
    
    print(f"输出shape: {output_data.shape}")
    print(f"输出前5行:\n{output_data[:5]}")
    
    return output_data, orig_w, orig_h

def run_onnx_inference(onnx_path, img_path):
    """运行ONNX推理并返回原始输出"""
    print("\n=== ONNX推理 ===")
    
    # 加载模型
    session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
    
    # 预处理
    img_array, orig_w, orig_h = preprocess_image(img_path)
    
    # 准备输入
    scale_factor = np.array([[orig_w / 800.0, orig_h / 800.0]], dtype='float32')
    
    print(f"原始图像尺寸: {orig_w}x{orig_h}")
    print(f"Scale factor: {scale_factor}")
    
    # 推理
    outputs = session.run(None, {
        'image': img_array,
        'scale_factor': scale_factor
    })
    
    output_data = outputs[0]
    print(f"输出shape: {output_data.shape}")
    print(f"输出前5行:\n{output_data[:5]}")
    
    return output_data, orig_w, orig_h

def analyze_detections(detections, orig_w, orig_h, name=""):
    """分析检测结果"""
    print(f"\n=== {name} 检测分析 ===")
    
    # 找出score列
    score_col = None
    for i in range(detections.shape[1]):
        col = detections[:, i]
        if np.all(col >= -1e-6) and np.nanmax(col) <= 1.0 + 1e-6:
            score_col = i
            break
    
    if score_col is None:
        print("❌ 无法识别score列")
        return
    
    print(f"Score列: 第{score_col}列")
    
    # 过滤有效检测
    valid_mask = detections[:, score_col] >= 0.5
    valid_dets = detections[valid_mask]
    
    print(f"有效检测数量 (score>=0.5): {len(valid_dets)}")
    
    if len(valid_dets) == 0:
        return
    
    # 假设格式: [class, score, x1, y1, x2, y2]
    print("\n前5个有效检测:")
    for i, det in enumerate(valid_dets[:5]):
        if score_col == 1:  # [class, score, x1, y1, x2, y2]
            cls_id = int(det[0])
            score = det[1]
            x1, y1, x2, y2 = det[2], det[3], det[4], det[5]
        else:  # 其他格式
            print(f"  {i+1}. {det}")
            continue
        
        # 检查坐标范围
        print(f"  {i+1}. class={cls_id}, score={score:.3f}")
        print(f"      原始坐标: x1={x1:.1f}, y1={y1:.1f}, x2={x2:.1f}, y2={y2:.1f}")
        print(f"      宽高: w={x2-x1:.1f}, h={y2-y1:.1f}")
        
        # 检查坐标是否在合理范围内
        if x1 < 0 or y1 < 0 or x2 > orig_w * 1.5 or y2 > orig_h * 1.5:
            print(f"      ⚠️ 坐标超出合理范围 (图像尺寸: {orig_w}x{orig_h})")
        
        if x2 <= x1 or y2 <= y1:
            print(f"      ❌ 无效边界框 (x2<=x1 或 y2<=y1)")

if __name__ == '__main__':
    # 测试图像
    img_path = 'output/test-001.jpg'
    
    # Paddle模型路径
    paddle_model = '../inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/ppyoloe_plus_crn_m_300e_speed_optimized'
    
    # ONNX模型路径
    onnx_model = 'output/opset14_no_fallback.onnx'
    
    # 运行Paddle推理
    paddle_output, orig_w, orig_h = run_paddle_inference(paddle_model, img_path)
    analyze_detections(paddle_output, orig_w, orig_h, "Paddle")
    
    # 运行ONNX推理
    onnx_output, orig_w, orig_h = run_onnx_inference(onnx_model, img_path)
    analyze_detections(onnx_output, orig_w, orig_h, "ONNX")
    
    # 对比前5个有效检测
    print("\n" + "="*60)
    print("对比分析")
    print("="*60)
    
    # 找出有效检测
    paddle_valid = paddle_output[paddle_output[:, 1] >= 0.5]
    onnx_valid = onnx_output[onnx_output[:, 1] >= 0.5]
    
    print(f"\nPaddle有效检测: {len(paddle_valid)}")
    print(f"ONNX有效检测: {len(onnx_valid)}")
    
    if len(paddle_valid) > 0 and len(onnx_valid) > 0:
        print("\n坐标范围对比:")
        print(f"Paddle - X范围: [{paddle_valid[:, 2].min():.1f}, {paddle_valid[:, 4].max():.1f}]")
        print(f"Paddle - Y范围: [{paddle_valid[:, 3].min():.1f}, {paddle_valid[:, 5].max():.1f}]")
        print(f"ONNX   - X范围: [{onnx_valid[:, 2].min():.1f}, {onnx_valid[:, 4].max():.1f}]")
        print(f"ONNX   - Y范围: [{onnx_valid[:, 3].min():.1f}, {onnx_valid[:, 5].max():.1f}]")

#!/usr/bin/env python3
"""
修正坐标缩放问题
"""
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

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
    
    return img_array, img, orig_w, orig_h

def run_onnx_with_manual_scaling(onnx_path, img_path, score_thresh=0.5):
    """运行ONNX推理并手动缩放坐标"""
    print("\n=== ONNX推理 (手动缩放坐标) ===")
    
    # 加载模型
    session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
    
    # 预处理
    img_array, orig_img, orig_w, orig_h = preprocess_image(img_path)
    
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
    
    # 过滤有效检测
    valid_mask = output_data[:, 1] >= score_thresh
    valid_dets = output_data[valid_mask]
    
    print(f"有效检测数量 (score>={score_thresh}): {len(valid_dets)}")
    
    if len(valid_dets) > 0:
        print("\n检查前3个检测的坐标:")
        for i in range(min(3, len(valid_dets))):
            det = valid_dets[i]
            cls_id = int(det[0])
            score = det[1]
            x1, y1, x2, y2 = det[2], det[3], det[4], det[5]
            
            print(f"  {i+1}. class={cls_id}, score={score:.3f}")
            print(f"      模型输出坐标: x1={x1:.1f}, y1={y1:.1f}, x2={x2:.1f}, y2={y2:.1f}")
            
            # 手动缩放坐标
            x1_scaled = x1 * scale_factor[0, 0]
            y1_scaled = y1 * scale_factor[0, 1]
            x2_scaled = x2 * scale_factor[0, 0]
            y2_scaled = y2 * scale_factor[0, 1]
            
            print(f"      手动缩放后: x1={x1_scaled:.1f}, y1={y1_scaled:.1f}, x2={x2_scaled:.1f}, y2={y2_scaled:.1f}")
            print(f"      宽高: w={x2_scaled-x1_scaled:.1f}, h={y2_scaled-y1_scaled:.1f}")
    
    # 绘制标注图像 (手动缩放坐标)
    draw = ImageDraw.Draw(orig_img)
    
    # 尝试加载字体
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    class_names = ['seeda', 'seedb', 'seedc', 'seedd']
    
    for det in valid_dets:
        cls_id = int(det[0])
        score = det[1]
        x1, y1, x2, y2 = det[2], det[3], det[4], det[5]
        
        # 手动缩放坐标到原图尺寸
        x1 = x1 * scale_factor[0, 0]
        y1 = y1 * scale_factor[0, 1]
        x2 = x2 * scale_factor[0, 0]
        y2 = y2 * scale_factor[0, 1]
        
        # 确保顺序正确
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # 绘制边界框 (红色)
        draw.rectangle([x1, y1, x2, y2], outline='red', width=3)
        
        # 绘制标签
        label = f"{class_names[cls_id]}: {score:.2f}"
        
        # 使用textbbox而不是getsize
        bbox = draw.textbbox((x1, y1), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 绘制标签背景
        draw.rectangle([x1, y1 - text_height - 4, x1 + text_width + 4, y1], fill='red')
        draw.text((x1 + 2, y1 - text_height - 2), label, fill='white', font=font)
    
    # 保存
    output_path = 'output/manual_scaled_annotation.png'
    orig_img.save(output_path)
    print(f"\n✅ 已保存手动缩放坐标的标注图像: {output_path}")
    
    return orig_img

if __name__ == '__main__':
    img_path = 'output/test-001.jpg'
    onnx_model = 'output/opset14_no_fallback.onnx'
    
    run_onnx_with_manual_scaling(onnx_model, img_path)

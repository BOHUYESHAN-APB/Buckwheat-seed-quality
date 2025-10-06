#!/usr/bin/env python3
"""
ONNX模型推理 - 修复版 (坐标手动缩放)
"""
import sys
import os
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

def annotate_image_with_onnx(model_path, image_path, output_path='output/annotated_fixed.png', score_thresh=0.5):
    """
    使用ONNX模型进行推理并标注图像
    
    关键修复: 手动缩放坐标到原图尺寸
    """
    # 1. 加载模型
    print(f"加载模型: {model_path}")
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
    
    # 2. 读取并预处理图像
    img = Image.open(image_path).convert('RGB')
    orig_w, orig_h = img.size
    print(f"原图尺寸: {orig_w} x {orig_h}")
    
    # 调整到模型输入尺寸 (800x800)
    target_size = 800
    img_resized = img.resize((target_size, target_size), Image.LANCZOS)
    
    # 归一化
    img_array = np.array(img_resized, dtype='float32') / 255.0
    
    # HWC -> CHW
    img_array = img_array.transpose((2, 0, 1))
    
    # 添加batch维度
    img_array = img_array[np.newaxis, :]
    
    # 3. 准备scale_factor输入
    scale_factor = np.array([[orig_w / target_size, orig_h / target_size]], dtype='float32')
    print(f"Scale factor: {scale_factor[0]}")
    
    # 4. 运行推理
    print("运行推理...")
    outputs = session.run(None, {
        'image': img_array,
        'scale_factor': scale_factor
    })
    
    detections = outputs[0]
    print(f"输出shape: {detections.shape}")
    
    # 5. 过滤有效检测 (score >= threshold)
    # 格式: [class_id, score, x1, y1, x2, y2]
    valid_mask = detections[:, 1] >= score_thresh
    valid_dets = detections[valid_mask]
    
    print(f"有效检测数量 (score >= {score_thresh}): {len(valid_dets)}")
    
    if len(valid_dets) == 0:
        print("⚠️ 没有检测到对象")
        img.save(output_path)
        return img
    
    # 6. 检查坐标是否需要缩放
    max_coord = max(
        valid_dets[:, 2].max(),  # x1
        valid_dets[:, 3].max(),  # y1
        valid_dets[:, 4].max(),  # x2
        valid_dets[:, 5].max()   # y2
    )
    
    needs_scaling = (max_coord < 1000)  # 如果最大坐标 < 1000,说明还在800x800尺度
    
    if needs_scaling:
        print(f"⚠️ 检测到坐标未缩放 (最大坐标={max_coord:.1f})")
        print(f"将手动缩放到原图尺寸...")
        sf_x = scale_factor[0, 0]
        sf_y = scale_factor[0, 1]
    else:
        print(f"✓ 坐标已缩放 (最大坐标={max_coord:.1f})")
        sf_x = 1.0
        sf_y = 1.0
    
    # 7. 绘制标注
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()
    
    class_names = ['seeda', 'seedb', 'seedc', 'seedd']
    
    for det in valid_dets:
        cls_id = int(det[0])
        score = det[1]
        x1, y1, x2, y2 = det[2], det[3], det[4], det[5]
        
        # 应用缩放
        x1 = x1 * sf_x
        y1 = y1 * sf_y
        x2 = x2 * sf_x
        y2 = y2 * sf_y
        
        # 确保顺序正确
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # 限制在图像范围内
        x1 = max(0, min(orig_w, x1))
        x2 = max(0, min(orig_w, x2))
        y1 = max(0, min(orig_h, y1))
        y2 = max(0, min(orig_h, y2))
        
        # 绘制边界框
        draw.rectangle([x1, y1, x2, y2], outline='red', width=4)
        
        # 绘制标签
        label = f"{class_names[cls_id]}: {score:.2f}"
        bbox = draw.textbbox((x1, y1), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        draw.rectangle([x1, y1 - text_h - 4, x1 + text_w + 4, y1], fill='red')
        draw.text((x1 + 2, y1 - text_h - 2), label, fill='white', font=font)
    
    # 8. 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"✅ 已保存标注图像: {output_path}")
    
    return img

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python onnx_annotate_fixed.py <model.onnx> <image.jpg> [output.png] [score_threshold]")
        sys.exit(1)
    
    model_path = sys.argv[1]
    image_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else 'output/annotated_fixed.png'
    score_thresh = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    
    annotate_image_with_onnx(model_path, image_path, output_path, score_thresh)

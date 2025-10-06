#!/usr/bin/env python3
"""
Paddle模型推理 - 参考基准
"""
import sys
import numpy as np
import paddle.inference as paddle_infer
from PIL import Image, ImageDraw, ImageFont

def annotate_with_paddle(model_dir, image_path, output_path='output/paddle_baseline.png', score_thresh=0.5):
    """使用Paddle模型推理并标注"""
    # 1. 配置Paddle predictor
    print(f"加载Paddle模型: {model_dir}")
    config = paddle_infer.Config(
        f"{model_dir}/model.pdmodel",
        f"{model_dir}/model.pdiparams"
    )
    config.enable_use_gpu(1000, 0)
    config.switch_use_feed_fetch_ops(False)
    config.switch_ir_optim(True)
    
    predictor = paddle_infer.create_predictor(config)
    
    # 2. 读取并预处理图像
    img = Image.open(image_path).convert('RGB')
    orig_w, orig_h = img.size
    print(f"原图尺寸: {orig_w} x {orig_h}")
    
    target_size = 800
    img_resized = img.resize((target_size, target_size), Image.LANCZOS)
    
    img_array = np.array(img_resized, dtype='float32') / 255.0
    img_array = img_array.transpose((2, 0, 1))
    img_array = img_array[np.newaxis, :]
    
    # 3. 准备输入
    input_names = predictor.get_input_names()
    
    # image
    input_tensor = predictor.get_input_handle(input_names[0])
    input_tensor.copy_from_cpu(img_array)
    
    # scale_factor
    scale_factor = np.array([[orig_w / target_size, orig_h / target_size]], dtype='float32')
    print(f"Scale factor: {scale_factor[0]}")
    
    scale_tensor = predictor.get_input_handle(input_names[1])
    scale_tensor.copy_from_cpu(scale_factor)
    
    # 4. 运行推理
    print("运行Paddle推理...")
    predictor.run()
    
    # 5. 获取输出
    output_names = predictor.get_output_names()
    output_tensor = predictor.get_output_handle(output_names[0])
    detections = output_tensor.copy_to_cpu()
    
    print(f"输出shape: {detections.shape}")
    
    # 6. 过滤有效检测
    valid_mask = detections[:, 1] >= score_thresh
    valid_dets = detections[valid_mask]
    
    print(f"有效检测数量 (score >= {score_thresh}): {len(valid_dets)}")
    
    if len(valid_dets) == 0:
        print("[WARN] No detections")
        img.save(output_path)
        return img
    
    # 检查坐标范围
    max_coord = max(
        valid_dets[:, 2].max(),
        valid_dets[:, 3].max(),
        valid_dets[:, 4].max(),
        valid_dets[:, 5].max()
    )
    print(f"最大坐标: {max_coord:.1f}")
    
    # 7. 绘制标注 (绿色,以区别于ONNX)
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
        
        # Paddle输出的坐标应该已经缩放到原图尺寸
        # 但我们也检查一下
        if max_coord < 1000:
            # 需要手动缩放
            x1 *= scale_factor[0, 0]
            y1 *= scale_factor[0, 1]
            x2 *= scale_factor[0, 0]
            y2 *= scale_factor[0, 1]
        
        # 确保顺序正确
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # 限制范围
        x1 = max(0, min(orig_w, x1))
        x2 = max(0, min(orig_w, x2))
        y1 = max(0, min(orig_h, y1))
        y2 = max(0, min(orig_h, y2))
        
        # 绘制边界框 (绿色)
        draw.rectangle([x1, y1, x2, y2], outline='green', width=4)
        
        # 绘制标签
        label = f"{class_names[cls_id]}: {score:.2f}"
        bbox = draw.textbbox((x1, y1), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        draw.rectangle([x1, y1 - text_h - 4, x1 + text_w + 4, y1], fill='green')
        draw.text((x1 + 2, y1 - text_h - 2), label, fill='white', font=font)
    
    # 8. 保存
    img.save(output_path)
    print(f"[OK] Saved Paddle annotation: {output_path}")
    
    return img

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python paddle_annotate_fixed.py <model_dir> <image.jpg> [output.png]")
        sys.exit(1)
    
    model_dir = sys.argv[1]
    image_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else 'output/paddle_baseline.png'
    
    annotate_with_paddle(model_dir, image_path, output_path)

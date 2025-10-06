#!/usr/bin/env python3
"""Use Paddle inference predictor to generate reference annotated image."""
import os
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

try:
    import paddle.inference as paddle_infer
except Exception as e:
    print("Failed to import paddle.inference:", e)
    sys.exit(1)

model_dir = 'inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/ppyoloe_plus_crn_m_300e_speed_optimized'
image_path = 'data/raw/train-use/test/test-001.jpg'
output_path = 'android-app/output/paddle_reference.png'

# Find model files
model_file = None
params_file = None
for name in os.listdir(model_dir):
    if name.endswith('.pdmodel'):
        model_file = os.path.join(model_dir, name)
    if name.endswith('.pdiparams'):
        params_file = os.path.join(model_dir, name)

print(f'Model: {model_file}')
print(f'Params: {params_file}')

# Build predictor
config = paddle_infer.Config(model_file, params_file)
config.disable_gpu()
config.switch_ir_optim(True)
predictor = paddle_infer.create_predictor(config)

# Read and preprocess image
img = cv2.imread(image_path)
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
orig_h, orig_w = img_rgb.shape[:2]
target_size = (800, 800)

img_resized = cv2.resize(img_rgb, target_size)
inp = img_resized.astype('float32') / 255.0
inp = inp.transpose((2, 0, 1))
inp = np.expand_dims(inp, axis=0)

print(f'Input shape: {inp.shape}, orig size: {orig_w}x{orig_h}')

# Feed inputs
input_names = predictor.get_input_names()
input_handle = predictor.get_input_handle(input_names[0])
input_handle.copy_from_cpu(inp)

if len(input_names) > 1:
    sf = np.array([float(orig_w) / target_size[0], float(orig_h) / target_size[1]], dtype='float32').reshape((1, 2))
    sf_handle = predictor.get_input_handle(input_names[1])
    sf_handle.copy_from_cpu(sf)
    print(f'Scale factor: {sf}')

# Run inference
predictor.run()

# Get outputs
out_names = predictor.get_output_names()
out0_handle = predictor.get_output_handle(out_names[0])
detections = out0_handle.copy_to_cpu()

print(f'Detections shape: {detections.shape}')
print(f'First 3 rows:\n{detections[:3]}')

# Draw on PIL image
pil_img = Image.fromarray(img_rgb)
draw = ImageDraw.Draw(pil_img)
try:
    font = ImageFont.load_default()
except:
    font = None

score_thresh = 0.5
count = 0

for row in detections:
    if len(row) < 6:
        continue
    
    # Parse detection row - assuming format from Paddle export
    # Typical format: [cls, score, x1, y1, x2, y2] or [batch_id, score, x1, y1, x2, y2]
    # Check if first column is batch index (usually 0 or low number)
    if row[0] < 10 and 0 <= row[1] <= 1.0:
        # [batch_or_cls, score, x1, y1, x2, y2]
        cls = int(row[0])
        score = float(row[1])
        x1, y1, x2, y2 = [float(x) for x in row[2:6]]
    else:
        # [x1, y1, x2, y2, score, cls]
        x1, y1, x2, y2 = [float(x) for x in row[0:4]]
        score = float(row[4])
        cls = int(row[5])
    
    if score < score_thresh:
        continue
    
    # Coords might already be in original scale (check magnitude)
    if max(x1, y1, x2, y2) > max(orig_w, orig_h) * 0.9:
        # Already scaled
        pass
    else:
        # Scale from model input to original
        x1 *= float(orig_w) / target_size[0]
        x2 *= float(orig_w) / target_size[0]
        y1 *= float(orig_h) / target_size[1]
        y2 *= float(orig_h) / target_size[1]
    
    x1 = max(0, min(orig_w, x1))
    x2 = max(0, min(orig_w, x2))
    y1 = max(0, min(orig_h, y1))
    y2 = max(0, min(orig_h, y2))
    
    x0, x1c = min(x1, x2), max(x1, x2)
    y0, y1c = min(y1, y2), max(y1, y2)
    
    draw.rectangle([x0, y0, x1c, y1c], outline='green', width=3)
    label = f'cls{cls} {score:.2f}'
    
    try:
        if font and hasattr(font, 'getsize'):
            tw, th = font.getsize(label)
        else:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
    except:
        tw, th = len(label) * 6, 10
    
    draw.rectangle([x0, y0-th, x0+tw, y0], fill='green')
    draw.text((x0, y0-th), label, fill='white', font=font)
    count += 1

os.makedirs(os.path.dirname(output_path), exist_ok=True)
pil_img.save(output_path)
print(f'Saved {count} detections to {output_path}')

#!/usr/bin/env python3
"""Analyze detection scores from ONNX outputs."""
import sys
import numpy as np
import onnxruntime as ort
from PIL import Image

onnx_path = sys.argv[1] if len(sys.argv) > 1 else 'android-app/output/opset14_no_fallback.onnx'
image_path = 'data/raw/train-use/test/test-001.jpg'

print(f'Analyzing: {onnx_path}')
sess = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
inputs = sess.get_inputs()

img = Image.open(image_path).convert('RGB')
orig_w, orig_h = img.size

shape = inputs[0].shape
s = [int(x) if isinstance(x, int) else None for x in shape]
H = s[-2] or 800
W = s[-1] or 800

arr = np.array(img.resize((W, H))).astype('float32') / 255.0
arr = (arr - np.array([0.0, 0.0, 0.0])) / np.array([1.0, 1.0, 1.0])
arr = arr.transpose(2, 0, 1)[None, :, :, :]

feeds = {inputs[0].name: arr.astype('float32')}
for i in inputs[1:]:
    sf = np.array([float(orig_w)/W, float(orig_h)/H], dtype='float32').reshape((1,2))
    feeds[i.name] = sf

outs = sess.run(None, feeds)
det = np.array(outs[0])

print(f'Output shape: {det.shape}')
print(f'First 5 rows:\n{det[:5]}')

# Find score column
score_col = None
for i in range(det.shape[1]):
    col = det[:, i]
    if np.all(col >= -1e-6) and np.nanmax(col) <= 1.0 + 1e-6:
        score_col = i
        print(f'Score column: {i}')
        break

if score_col is not None:
    scores = det[:, score_col]
    print(f'\nScore statistics:')
    print(f'  Min: {np.min(scores):.4f}')
    print(f'  Max: {np.max(scores):.4f}')
    print(f'  Mean: {np.mean(scores):.4f}')
    print(f'  Median: {np.median(scores):.4f}')
    
    # Count by threshold
    for thresh in [0.1, 0.3, 0.5, 0.7, 0.9]:
        count = np.sum(scores >= thresh)
        print(f'  >= {thresh:.1f}: {count}')
else:
    print('Could not find score column')

# Check class distribution
cls_col = 0 if score_col != 0 else det.shape[1] - 1
classes = det[:, cls_col]
print(f'\nClass column {cls_col} distribution:')
unique, counts = np.unique(classes.astype(int), return_counts=True)
for cls, cnt in zip(unique, counts):
    print(f'  Class {cls}: {cnt}')

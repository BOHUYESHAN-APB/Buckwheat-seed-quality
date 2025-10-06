#!/usr/bin/env python3
"""Load ONNX model, run inference on an image, draw detections (if any) and save annotated image.
Usage: python onnx_annotate_image.py /path/to/model.onnx /path/to/image.jpg [output.png]
"""
import sys
import os
import numpy as np

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

model_path = sys.argv[1] if len(sys.argv) > 1 else None
image_path = sys.argv[2] if len(sys.argv) > 2 else None
out_path = sys.argv[3] if len(sys.argv) > 3 else 'output/annotated.png'
if not model_path or not os.path.exists(model_path):
    print('MODEL_NOT_FOUND', model_path)
    sys.exit(2)
if not image_path or not os.path.exists(image_path):
    print('IMAGE_NOT_FOUND', image_path)
    sys.exit(2)

try:
    import onnxruntime as ort
except Exception as e:
    print('NO_ONNXRUNTIME', e)
    sys.exit(3)

from PIL import Image, ImageDraw, ImageFont

os.makedirs(os.path.dirname(out_path), exist_ok=True)

print('Loading model:', model_path)
sess = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
inputs = sess.get_inputs()
print('Model inputs:', [i.name + str(i.shape) for i in inputs])
print('Model outputs:', [o.name + str(o.shape) for o in sess.get_outputs()])

# read image
img = Image.open(image_path).convert('RGB')
orig_w, orig_h = img.size

# determine main input shape
input_name = inputs[0].name
shape = inputs[0].shape
bs = 1
c = 3
h = 640
w = 640
try:
    s = [int(x) if isinstance(x, (int, np.integer)) else None for x in shape]
    if len(s) >= 4:
        w = s[-1] or w
        h = s[-2] or h
        c = s[-3] or c
except Exception:
    pass

# resize image to model expected size
resized = img.resize((w, h))
arr = np.array(resized).astype(np.float32) / 255.0
arr = (arr - MEAN) / STD
arr = np.transpose(arr, (2,0,1))
inp = arr[np.newaxis,:,:,:]
feeds = {input_name: inp}
for i in inputs[1:]:
    lname = i.name.lower()
    if 'scale' in lname and 'factor' in lname:
        # follow PaddleDetection convention: feed [orig_w/target_w, orig_h/target_h]
        try:
            sf_x = float(orig_w) / float(w)
            sf_y = float(orig_h) / float(h)
            val = np.array([sf_x, sf_y], dtype=np.float32)
        except Exception:
            val = np.array([1.0, 1.0], dtype=np.float32)
        target = i.shape
        if target and len(target) == 2 and (target[1] == 2 or target[1] is None):
            feeds[i.name] = val.reshape((1,2)).astype(np.float32)
        else:
            feeds[i.name] = val.astype(np.float32)
    else:
        t = i.shape
        if t is None or len(t) == 0:
            feeds[i.name] = np.array([1.0], dtype=np.float32)
        else:
            shp = tuple([1 if (x is None) else int(x) for x in t])
            feeds[i.name] = np.ones(shp, dtype=np.float32)

print('Running session...')
try:
    out = sess.run(None, feeds)
except Exception as e:
    print('RUNTIME_ERROR', e)
    sys.exit(4)

print('Outputs count:', len(out))
for idx, o in enumerate(out):
    arr = np.array(o)
    print(f'out[{idx}] shape={arr.shape} dtype={arr.dtype} head={arr.flatten()[:10]}')

draw = ImageDraw.Draw(img)
# Interpret detection output (robust to different column orders)
det = np.array(out[0]) if len(out) > 0 else np.zeros((0,6), dtype=np.float32)

if det.size == 0 or det.shape[0] == 0:
    print('NO_DETECTIONS')
    img.save(out_path)
    print('Saved', out_path)
    sys.exit(0)

draw = ImageDraw.Draw(img)
try:
    font = ImageFont.load_default()
except Exception:
    font = None

score_thresh = 0.5
# heuristics to find columns: score_col is column where values are in [0,1]
score_col = None
cols = det.shape[1]
for i in range(cols):
    col = det[:, i]
    if np.all(col >= -1e-6) and np.nanmax(col) <= 1.0 + 1e-6:
        score_col = i
        break

# find bbox columns: choose columns with values much larger than 1 (likely coordinates)
coord_cols = [i for i in range(cols) if np.nanmax(det[:, i]) > 1.1]

for row in det:
    if row.size < 6:
        continue
    # default parsing
    score = None
    cls = None
    bbox = None

    if score_col is not None:
        score = float(row[score_col])
        # class index likely in first or last col
        other_cols = [i for i in range(cols) if i != score_col]
        # pick bbox as 4 cols among other_cols that have large values
        cand = [i for i in other_cols if i in coord_cols]
        if len(cand) >= 4:
            cand = sorted(cand)[:4]
            bbox = [float(row[i]) for i in cand]
            # class is remaining
            rem = [i for i in other_cols if i not in cand]
            if rem:
                cls = int(row[rem[0]])
        else:
            # fallback: assume order [cls, score, x1,y1,x2,y2]
            cls = int(row[0])
            score = float(row[1])
            bbox = [float(x) for x in row[2:6]]
    else:
        # no obvious score column: assume [x1,y1,x2,y2,score,cls]
        score = float(row[4]) if cols > 4 else 0.0
        cls = int(row[5]) if cols > 5 else 0
        bbox = [float(x) for x in row[0:4]]

    if score is None:
        continue
    if score < score_thresh:
        continue

    # bbox might already be in original image coords or in model coords
    x1, y1, x2, y2 = bbox[:4]
    # determine if coords are in original image scale by comparing magnitudes
    max_coord = max(x1, y1, x2, y2)
    if max_coord > max(orig_w, orig_h) * 0.9:
        # already scaled to original
        sx = 1.0
        sy = 1.0
    else:
        # need to scale from model input size to original
        sx = float(orig_w) / float(w)
        sy = float(orig_h) / float(h)

    x1 = max(0, min(orig_w, x1 * sx))
    x2 = max(0, min(orig_w, x2 * sx))
    y1 = max(0, min(orig_h, y1 * sy))
    y2 = max(0, min(orig_h, y2 * sy))

    x0, x1c = min(x1, x2), max(x1, x2)
    y0, y1c = min(y1, y2), max(y1, y2)
    draw.rectangle([x0, y0, x1c, y1c], outline='red', width=2)
    label = f'{int(cls) if cls is not None else -1} {score:.2f}'
    try:
        if font is not None and hasattr(font, 'getsize'):
            text_w, text_h = font.getsize(label)
        else:
            bbox_txt = draw.textbbox((0, 0), label, font=font)
            text_w = bbox_txt[2] - bbox_txt[0]
            text_h = bbox_txt[3] - bbox_txt[1]
    except Exception:
        text_w, text_h = (len(label) * 6, 10)
    draw.rectangle([x0, y0-text_h, x0+text_w, y0], fill='red')
    draw.text((x0, y0-text_h), label, fill='white', font=font)

img.save(out_path)
print('Saved annotated image to', out_path)


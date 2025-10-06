#!/usr/bin/env python3
"""Run model with multiple preprocessing variants and save results.
Usage: python onnx_annotate_gridtest.py /path/to/model.onnx /path/to/image.jpg
"""
import sys, os
from pathlib import Path
import numpy as np
from PIL import Image

MODEL = sys.argv[1]
IMAGE = sys.argv[2]
OUTDIR = Path('output/gridtest')
OUTDIR.mkdir(parents=True, exist_ok=True)

import onnxruntime as ort

def preprocess(img, target=(640,640), letterbox=False, do_norm=True, to_bgr=False):
    orig_w, orig_h = img.size
    if letterbox:
        # simple center padding to keep aspect
        img = img.copy()
        img = img.resize(target)
    else:
        img = img.resize(target)
    arr = np.array(img).astype(np.float32) / 255.0
    if to_bgr:
        arr = arr[..., ::-1]
    if do_norm:
        arr = (arr - np.array([0.485,0.456,0.406])) / np.array([0.229,0.224,0.225])
    arr = np.transpose(arr, (2,0,1))[np.newaxis,:,:,:].astype(np.float32)
    return arr, (orig_w, orig_h)

sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])
inputs = sess.get_inputs()
img = Image.open(IMAGE).convert('RGB')

variants = []
for do_norm in [True, False]:
    for to_bgr in [False, True]:
        for letter in [False]:
            variants.append((do_norm, to_bgr, letter))

for idx, (do_norm, to_bgr, letter) in enumerate(variants):
    inp, (ow,oh) = preprocess(img, target=(640,640), letterbox=letter, do_norm=do_norm, to_bgr=to_bgr)
    feeds = {inputs[0].name: inp}
    # build scale_factor as [scale_h, scale_w]
    scale_h = 640/oh
    scale_w = 640/ow
    for i in inputs[1:]:
        lname = i.name.lower()
        if 'scale' in lname and 'factor' in lname:
            feeds[i.name] = np.array([[scale_h, scale_w]], dtype=np.float32)
        else:
            t = i.shape
            if t is None or len(t)==0:
                feeds[i.name] = np.array([1.0], dtype=np.float32)
            else:
                shp = tuple([1 if (x is None) else int(x) for x in t])
                feeds[i.name] = np.ones(shp, dtype=np.float32)

    try:
        out = sess.run(None, feeds)
    except Exception as e:
        (OUTDIR / f'run_{idx}_error.txt').write_text(str(e))
        continue

    det = np.array(out[0]) if len(out)>0 else np.zeros((0,6), dtype=np.float32)
    log = f'variant={idx} do_norm={do_norm} to_bgr={to_bgr} letter={letter} det_shape={det.shape}\n'
    (OUTDIR / f'run_{idx}.txt').write_text(log)
    # draw boxes if any
    outimg = img.copy()
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(outimg)
    try:
        font = ImageFont.load_default()
    except:
        font = None
    if det.size != 0 and det.shape[0] > 0:
        sx = ow / 640.0
        sy = oh / 640.0
        for r in det:
            if len(r) < 6: continue
            x1,y1,x2,y2,score,cls = r[:6]
            x1 = max(0,min(ow, x1 * sx))
            x2 = max(0,min(ow, x2 * sx))
            y1 = max(0,min(oh, y1 * sy))
            y2 = max(0,min(oh, y2 * sy))
            draw.rectangle([x1,y1,x2,y2], outline='lime', width=2)
            draw.text((x1, y1), f'{int(cls)} {score:.2f}', fill='lime', font=font)

    outimg.save(OUTDIR / f'run_{idx}.png')
    (OUTDIR / f'run_{idx}_meta.txt').write_text(log)

print('Grid test complete. Results in', OUTDIR)

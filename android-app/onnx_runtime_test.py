#!/usr/bin/env python3
"""Quick ONNX runtime smoke-test script.
Usage: python onnx_runtime_test.py /path/to/model.onnx [optional_image.jpg]

Tries to import onnxruntime, loads the model, builds a dummy / resized input, optionally uses image, and runs session.
Prints outputs shapes and head values.
"""
import sys
import os
import numpy as np

model_path = sys.argv[1] if len(sys.argv) > 1 else None
image_path = sys.argv[2] if len(sys.argv) > 2 else None
if not model_path or not os.path.exists(model_path):
    print('MODEL_NOT_FOUND', model_path)
    sys.exit(2)

try:
    import onnxruntime as ort
except Exception as e:
    print('NO_ONNXRUNTIME', e)
    sys.exit(3)

try:
    from PIL import Image
except Exception:
    Image = None

print('Loading model:', model_path)
sess = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
inputs = sess.get_inputs()
print('Model inputs:', [i.name + str(i.shape) for i in inputs])
print('Model outputs:', [o.name + str(o.shape) for o in sess.get_outputs()])

# Determine input name and shape
input_name = inputs[0].name
shape = inputs[0].shape
# Heuristic: expected [1,3,640,640]
bs = 1
c = 3
h = 640
w = 640
# try to infer from shape if present
try:
    # shape may contain None or 'batch' var; use ints when available
    s = [int(x) if isinstance(x, (int, np.integer)) else None for x in shape]
    # reverse search for 3 and 640
    if len(s) >= 4:
        if s[-1] is not None and s[-2] is not None and s[-3] is not None:
            w = s[-1] or w
            h = s[-2] or h
            c = s[-3] or c
except Exception:
    pass

# prepare image-based or random input
if image_path and Image is not None and os.path.exists(image_path):
    img = Image.open(image_path).convert('RGB')
    img = img.resize((w, h))
    arr = np.array(img).astype(np.float32) / 255.0
    # model expects channels-first
    arr = np.transpose(arr, (2,0,1))
    inp = arr[np.newaxis,:,:,:]
else:
    inp = np.random.rand(bs, c, h, w).astype(np.float32)

feeds = {input_name: inp}
# check for auxiliary inputs like 'scale' in names and provide defaults
for i in inputs[1:]:
    lname = i.name.lower()
    print('Aux input:', i.name, 'shape', i.shape)
    if 'scale' in lname and 'factor' in lname:
        # try produce shape compatible: either (1,2) or (2,)
        target = i.shape
        val = np.array([1.0, 1.0], dtype=np.float32)
        if target and len(target) == 2 and (target[1] == 2 or target[1] is None):
            feeds[i.name] = val.reshape((1,2)).astype(np.float32)
        else:
            feeds[i.name] = val.astype(np.float32)
    else:
        # fallback: fill ones with right size
        t = i.shape
        if t is None or len(t) == 0:
            feeds[i.name] = np.array([1.0], dtype=np.float32)
        else:
            # create ones with shape replacing None with 1
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

print('Done')

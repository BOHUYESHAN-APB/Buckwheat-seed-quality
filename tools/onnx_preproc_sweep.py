#!/usr/bin/env python3
"""
Try multiple preprocessing variants against an ONNX model and an image to see if any produce detections.
Usage: python tools/onnx_preproc_sweep.py <model.onnx> <image.jpg>
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import onnxruntime as ort

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess(img: Image.Image, target_size, div255, channel_order, mean_std):
    # resize to target_size x target_size (stretch)
    img2 = img.resize((target_size, target_size), Image.LANCZOS)
    arr = np.array(img2).astype(np.float32)
    if div255:
        arr = arr / 255.0
    if mean_std == 'imagenet':
        arr = (arr - IMAGENET_MEAN.reshape((1,1,3))) / IMAGENET_STD.reshape((1,1,3))
    elif mean_std == 'none':
        pass
    # channel order
    if channel_order == 'rgb':
        pass
    elif channel_order == 'bgr':
        arr = arr[..., ::-1]
    # to CHW
    arr = np.transpose(arr, (2,0,1))
    return arr[np.newaxis, ...].astype(np.float32)


def run_one(sess, input_name, feed_dict):
    try:
        outs = sess.run(None, feed_dict)
    except Exception as e:
        return {'error': str(e)}
    res = []
    for o in outs:
        a = np.array(o)
        res.append({'shape': a.shape, 'head': a.flatten()[:10].tolist()})
    return {'outputs': res}


def sweep(model_path, image_path):
    sess = ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])
    inputs = sess.get_inputs()
    input_name = inputs[0].name

    # infer target size
    shape = inputs[0].shape
    try:
        s = [int(x) if isinstance(x, (int, np.integer)) else None for x in shape]
        target = 800
        if len(s) >= 4 and s[-1] is not None and s[-2] is not None:
            target = s[-1]
    except Exception:
        target = 800

    img = Image.open(image_path).convert('RGB')
    combos = []
    for div255 in [True, False]:
        for channel in ['rgb', 'bgr']:
            for mean_std in ['none', 'imagenet']:
                combos.append((div255, channel, mean_std))

    results = []
    for div255, channel, mean_std in combos:
        inp = preprocess(img, target, div255, channel, mean_std)
        feeds = {input_name: inp}
        # add scale_factor if model requires
        for i in inputs[1:]:
            lname = i.name.lower()
            if 'scale' in lname and 'factor' in lname:
                # original app used [scaleY, scaleX] or [[sf_x, sf_y]]? earlier code used [scaleY, scaleX] sometimes; use orig_w/target_w etc
                sf_x = float(img.width) / float(target)
                sf_y = float(img.height) / float(target)
                feeds[i.name] = np.array([[sf_x, sf_y]], dtype=np.float32)
            else:
                t = i.shape
                if t is None or len(t) == 0:
                    feeds[i.name] = np.array([1.0], dtype=np.float32)
                else:
                    shp = tuple([1 if (x is None) else int(x) for x in t])
                    feeds[i.name] = np.ones(shp, dtype=np.float32)
        out = run_one(sess, input_name, feeds)
        det_count = 0
        if 'outputs' in out and len(out['outputs'])>0:
            a0 = out['outputs'][0]['shape']
            if len(a0) >= 1:
                det_count = int(a0[0])
        results.append({'div255': div255, 'channel': channel, 'mean_std': mean_std, 'det_count': det_count, 'out': out})
        print(f'comb div255={div255} channel={channel} mean_std={mean_std} -> dets={det_count}')

    return results


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: onnx_preproc_sweep.py <model.onnx> <image.jpg>')
        sys.exit(1)
    model = Path(sys.argv[1])
    image = Path(sys.argv[2])
    res = sweep(model, image)
    import json
    print(json.dumps(res, indent=2, ensure_ascii=False))

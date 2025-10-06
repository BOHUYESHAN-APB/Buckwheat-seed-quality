#!/usr/bin/env python3
"""
Run an ONNX model with an input tensor dumped from the Android app (JSON format created by debug mode).
Usage: python tools/run_onnx_with_input_json.py <onnx_path> <input_json_path>

JSON format expected (example produced by the app):
{
  "shape": [1, 3, 800, 800],
  "data": [ ... float values ... ]
}

This script will load the ONNX, create the input tensor(s), run onnxruntime, and print output shapes and small heads of arrays.
"""
import sys
import json
import numpy as np
import onnxruntime as ort
from pathlib import Path


def load_input(json_path):
    j = json.loads(Path(json_path).read_text())
    shape = j.get('shape')
    data = j.get('data')
    if shape is None or data is None:
        raise RuntimeError('JSON must contain shape and data fields')
    arr = np.array(data, dtype=np.float32)
    arr = arr.reshape(tuple(shape))
    return arr


def main():
    if len(sys.argv) < 3:
        print('Usage: run_onnx_with_input_json.py <onnx_path> <input_json_path>')
        return
    onnx_path = Path(sys.argv[1])
    json_path = Path(sys.argv[2])
    if not onnx_path.exists():
        print('ONNX not found:', onnx_path)
        return
    if not json_path.exists():
        print('Input JSON not found:', json_path)
        return

    inp = load_input(json_path)
    print('Loaded input shape:', inp.shape)

    sess = ort.InferenceSession(str(onnx_path))
    input_names = [i.name for i in sess.get_inputs()]
    print('Model inputs:', input_names)

    feed = {}
    # Find first input and use as image
    if len(input_names) > 0:
        feed[input_names[0]] = inp
    # Try to create scale_factor if required
    for name in input_names[1:]:
        if 'scale' in name.lower() and 'factor' in name.lower():
            # app uses shape [1,2] (scaleY, scaleX) according to code
            feed[name] = np.array([[1.0, 1.0]], dtype=np.float32)
        else:
            # fill with ones matching the input shape
            info = sess.get_inputs()[input_names.index(name)]
            s = [d if d is not None and d > 0 else 1 for d in info.shape]
            feed[name] = np.ones(tuple(s), dtype=np.float32)

    print('Running inference...')
    outs = sess.run(None, feed)
    print('Got', len(outs), 'outputs')
    for i, o in enumerate(outs):
        arr = np.array(o)
        print(f'out[{i}] shape={arr.shape} dtype={arr.dtype} head={arr.flatten()[:10]}')


if __name__ == '__main__':
    main()

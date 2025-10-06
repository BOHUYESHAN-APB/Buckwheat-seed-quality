import os
import sys

# ensure workspace root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import numpy as np
from app.ui import Detector

img_path = 'data/raw/train-use/test/test-001.jpg'
img_bgr = cv2.imread(img_path)
if img_bgr is None:
    raise SystemExit(f'Unable to read image: {img_path}')

img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
orig_size = (img_bgr.shape[1], img_bgr.shape[0])

d = Detector('inference_model/ppyoloe_plus_crn_m_300e_speed_optimized')

inp, _ = d.preprocess(img_rgb)
input_handle = d.predictor.get_input_handle(d.input_names[0])
input_handle.reshape(inp.shape)
input_handle.copy_from_cpu(inp)
if len(d.input_names) > 1:
    sf = np.array([[1.0, 1.0]], dtype='float32')
    sf_handle = d.predictor.get_input_handle(d.input_names[1])
    sf_handle.reshape(sf.shape)
    sf_handle.copy_from_cpu(sf)

d.predictor.run()
raw_outputs = [d.predictor.get_output_handle(name).copy_to_cpu() for name in d.output_names]
bbox_array = raw_outputs[0]
np.set_printoptions(precision=4, suppress=True)
print('shape:', bbox_array.shape)
print('row0:', bbox_array[0])
bbox_num = None
if len(raw_outputs) > 1:
    bbox_num = raw_outputs[1]
print('bbox_num:', bbox_num)
if bbox_array.shape[0] > 1:
    print('row1:', bbox_array[1])
if bbox_array.shape[0] > 2:
    print('row2:', bbox_array[2])
print('unique labels:', np.unique(bbox_array[:,0])[:10])
print('score range:', float(bbox_array[:,1].min()), float(bbox_array[:,1].max()))
print('counts:',
    '>0.9', int((bbox_array[:,1] > 0.9).sum()),
    '>0.8', int((bbox_array[:,1] > 0.8).sum()),
    '>0.7', int((bbox_array[:,1] > 0.7).sum()),
    '>0.6', int((bbox_array[:,1] > 0.6).sum()),
    '>0.5', int((bbox_array[:,1] > 0.5).sum()))

boxes_post = d.postprocess(raw_outputs, orig_size)
print(f'postprocess -> {len(boxes_post)} boxes (threshold={d.score_threshold})')
print('top5 parsed boxes:', boxes_post[:5])

vis_rgb = d.detect_image(img_rgb)
out_path = 'inference_results/test-001_preview.jpg'
cv2.imwrite(out_path, cv2.cvtColor(vis_rgb, cv2.COLOR_RGB2BGR))
print('saved preview to', out_path)

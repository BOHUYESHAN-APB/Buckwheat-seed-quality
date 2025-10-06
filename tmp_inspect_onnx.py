import onnxruntime as ort
import numpy as np
from PIL import Image
sess = ort.InferenceSession('inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/model_fallback.onnx')
inputs = sess.get_inputs()
img = Image.open('data/raw/train-use/test/test-001.jpg').convert('RGB')
orig_w, orig_h = img.size
shape = inputs[0].shape
s = [int(x) if isinstance(x, (int,)) else None for x in shape]
H = s[-2] or 800
W = s[-1] or 800
arr = np.array(img.resize((W,H))).astype('float32')/255.0
arr = (arr - np.array([0.0,0.0,0.0]))/np.array([1.0,1.0,1.0])
arr = arr.transpose(2,0,1)[None,:,:,:]
feeds = {inputs[0].name: arr.astype('float32')}
for i in inputs[1:]:
    feeds[i.name] = np.array([H/orig_h, W/orig_w], dtype='float32').reshape((1,2)).astype('float32')
outs = sess.run(None, feeds)
print('out0 shape:', outs[0].shape)
print('first 5 rows:\n', outs[0][:5])
print('out1:', outs[1])

import onnxruntime as ort
import numpy as np
import sys
mf = r"e:\CODE\Buckwheat-seed-quality\inference_model\temp_output_inference\model.onnx"
print('Loading', mf)
sess = ort.InferenceSession(mf)
print('Inputs:')
for i in sess.get_inputs():
    print(i.name, i.shape, i.type)
print('Outputs:')
for o in sess.get_outputs():
    print(o.name, o.shape, o.type)
# run dummy
input_name = sess.get_inputs()[0].name
shape = sess.get_inputs()[0].shape
shape = [1 if (x is None or isinstance(x, str)) else x for x in shape]
print('Using dummy shape:', shape)
dummy = np.random.rand(*shape).astype(np.float32)
res = sess.run(None, {input_name: dummy})
print('Ran inference, output count:', len(res))
for r in res[:3]:
    if hasattr(r, 'shape'):
        print('out shape', r.shape)
    else:
        print(type(r))
print('Done')

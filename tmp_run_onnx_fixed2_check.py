import onnxruntime as ort
import numpy as np
mf = r"e:\CODE\Buckwheat-seed-quality\inference_model\temp_output_inference\model_opset14_fixed2.onnx"
print('Loading', mf)
sess = ort.InferenceSession(mf)
print('Inputs:')
for i in sess.get_inputs():
    print(i.name, i.shape)
shape = [1 if (x is None or isinstance(x, str)) else x for x in sess.get_inputs()[0].shape]
print('Using dummy shape', shape)
dummy = np.random.rand(*shape).astype('float32')
res = sess.run(None, {sess.get_inputs()[0].name: dummy})
print('OK, outputs:', len(res))
for r in res[:3]:
    try:
        print('out shape', r.shape)
    except Exception:
        print(type(r))
print('Done')

import onnxruntime as ort
import numpy as np
mf = r"e:\CODE\Buckwheat-seed-quality\inference_model\temp_output_inference\model_opset14_fixed2.onnx"
sess = ort.InferenceSession(mf)
image_name = sess.get_inputs()[0].name
scale_name = sess.get_inputs()[1].name
shape = [1 if (x is None or isinstance(x, str)) else x for x in sess.get_inputs()[0].shape]
dummy = np.random.rand(*shape).astype('float32')
scale = np.array([1.0, 1.0], dtype='float32')
res = sess.run(None, {image_name: dummy, scale_name: scale})
print('Ran, outputs:', len(res))
for i,r in enumerate(res[:5]):
    try:
        print(i, 'out shape', r.shape)
    except Exception:
        print(i, type(r))
print('Done')

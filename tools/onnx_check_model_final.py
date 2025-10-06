import onnxruntime as ort
import numpy as np
mf = r"e:\CODE\Buckwheat-seed-quality\inference_model\exports\model_final\model.onnx"
print('Loading', mf)
sess = ort.InferenceSession(mf)
print('Inputs:', [ (i.name, i.shape) for i in sess.get_inputs() ])
image_name = sess.get_inputs()[0].name
scale_name = sess.get_inputs()[1].name
shape = [1 if (x is None or isinstance(x, str)) else x for x in sess.get_inputs()[0].shape]
dummy_image = np.random.rand(*shape).astype('float32')
dummy_scale = np.array([1.0,1.0], dtype='float32')
res = sess.run(None, {image_name: dummy_image, scale_name: dummy_scale})
print('Ran OK, outputs count', len(res))
for i,r in enumerate(res[:3]):
    try:
        print(i, r.shape)
    except Exception:
        print(i, type(r))
print('Done')

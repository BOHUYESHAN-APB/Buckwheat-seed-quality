import onnxruntime as ort, numpy as np
paths = [
    r'e:\CODE\Buckwheat-seed-quality\inference_model\exports\model_final\model.onnx',
    r'e:\CODE\Buckwheat-seed-quality\inference_model\exports\best\model.onnx'
]
for path in paths:
    print('Checking', path)
    sess = ort.InferenceSession(path)
    inputs = sess.get_inputs()
    print(' inputs', [(i.name,i.shape) for i in inputs])
    img_name = inputs[0].name
    scale_name = inputs[1].name
    shape = [1 if (x is None or isinstance(x,str)) else x for x in inputs[0].shape]
    img = np.random.rand(*shape).astype('float32')
    scale = np.array([[1.0,1.0]], dtype='float32')
    try:
        res = sess.run(None, {img_name:img, scale_name:scale})
        print(' OK, outputs', len(res))
        for r in res[:2]:
            try:
                print('  out shape', r.shape)
            except:
                print('  out type', type(r))
    except Exception as e:
        print(' FAIL', e)
    print('---')

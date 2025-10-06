import onnxruntime as ort
mf = r"e:\CODE\Buckwheat-seed-quality\inference_model\temp_output_inference\model_opset14.onnx"
print('Loading', mf)
sess = ort.InferenceSession(mf)
print('Loaded OK')
for i in sess.get_inputs():
    print('IN', i.name, i.shape)
for o in sess.get_outputs():
    print('OUT', o.name, o.shape)

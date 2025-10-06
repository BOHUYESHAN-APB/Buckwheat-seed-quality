import onnx
from pathlib import Path
p = Path(r'e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/apk_extracted_model.onnx')
print('Loading', p)
model = onnx.load(str(p))
# find node named Reshape.53 or op_type Reshape with that name
found = []
for i,n in enumerate(model.graph.node):
    inputs_outputs = list(n.input) + list(n.output)
    if n.op_type=='Reshape' and (n.name=="Reshape.53" or any('Reshape.53' in str(x) for x in inputs_outputs)):
        found.append((i,n))
print('Found', len(found), 'reshape nodes matching')
for idx,n in found:
    print('Node idx', idx, 'name', n.name)
    print(' inputs:', n.input)
    print(' outputs:', n.output)
# print initializer values for ints around 6400
inits = {init.name: init for init in model.graph.initializer}
# search initializers containing 6400
import numpy as np
hits = []
for name,init in inits.items():
    arr = onnx.numpy_helper.to_array(init)
    if np.any(arr==6400) or np.any(arr==10000):
        hits.append((name, arr.shape, np.unique(arr)[:10]))
print('Initializers containing 6400 or 10000:')
for h in hits:
    print(h[0], 'shape', h[1], 'unique sample', h[2])
# print initializer used directly by Reshape node (second input commonly)
for idx,n in found:
    for inp in n.input:
        if inp in inits:
            arr = onnx.numpy_helper.to_array(inits[inp])
            print('Reshape input initializer', inp, 'shape', arr.shape, 'vals sample', arr.flatten()[:20])
print('Done')

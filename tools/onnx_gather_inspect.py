import onnx
import sys
from pathlib import Path
p = Path('e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/model_opset14.onnx')
print('Loading', p)
model = onnx.load(str(p))
print('Graph nodes:', len(model.graph.node))
init_names = {i.name: i for i in model.graph.initializer}
print('Initializers:', len(init_names))
# list all gather nodes
for idx, node in enumerate(model.graph.node):
    if node.op_type == 'Gather':
        print('----')
        print('Node', idx, 'name', node.name)
        print('Inputs:', node.input)
        for inp in node.input:
            if inp in init_names:
                tensor = init_names[inp]
                dims = list(tensor.dims)
                print('  initializer', inp, 'dims', dims)
            else:
                print('  not initializer', inp)
# also check for any initializer with rank 0
for name, t in init_names.items():
    if len(t.dims)==0:
        print('Initializer scalar:', name)
print('Done')

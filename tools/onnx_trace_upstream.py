import onnx
from pathlib import Path
p = Path('e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/model_opset14.onnx')
model = onnx.load(str(p))
from onnx import shape_inference
inf = shape_inference.infer_shapes(model)
# build maps
node_by_output = {}
for n in inf.graph.node:
    for o in n.output:
        node_by_output[o]=n
val_shapes = {}
for vi in list(inf.graph.value_info) + list(inf.graph.input) + list(inf.graph.output):
    try:
        shape = [d.dim_value if (d.dim_value>0) else None for d in vi.type.tensor_type.shape.dim]
    except Exception:
        shape = None
    val_shapes[vi.name]=shape

targets=['Squeeze.4','Squeeze.6']
for t in targets:
    print('\n== Trace for', t)
    # find node that outputs t
    if t in node_by_output:
        n = node_by_output[t]
        print('Node', n.name, 'op', n.op_type)
        print('inputs:', n.input)
        for inp in n.input:
            print('  inp', inp, 'shape', val_shapes.get(inp))
            # find producer node
            prod = node_by_output.get(inp)
            if prod:
                print('   produced by', prod.name, 'op', prod.op_type, 'inputs', prod.input)
                for ii in prod.input:
                    print('     upstream', ii, 'shape', val_shapes.get(ii))
    else:
        print('No node produces', t)
print('\nDone')

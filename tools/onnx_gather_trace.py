import onnx
from pathlib import Path
p = Path('e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/model_opset14.onnx')
print('Loading', p)
model = onnx.load(str(p))
print('Running shape inference...')
from onnx import shape_inference
inferred = shape_inference.infer_shapes(model)
# build map from value name to shape
val_shapes = {}
for vi in list(inferred.graph.value_info) + list(inferred.graph.input) + list(inferred.graph.output):
    name = vi.name
    shape = None
    try:
        shape = [d.dim_value if (d.dim_value>0) else None for d in vi.type.tensor_type.shape.dim]
    except Exception:
        shape = None
    val_shapes[name]=shape

# helper: find nodes by op type Gather
for idx,node in enumerate(inferred.graph.node):
    if node.op_type=='Gather':
        print('Node', idx, node.name)
        for inp in node.input:
            s = val_shapes.get(inp, None)
            print('  input', inp, 'shape=', s)
        for out in node.output:
            s = val_shapes.get(out, None)
            print('  output', out, 'shape=', s)
print('Done')

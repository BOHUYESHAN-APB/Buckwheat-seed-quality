import onnx
from pathlib import Path
p = Path('e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/model_opset14.onnx')
model = onnx.load(str(p))
from onnx import shape_inference
inf = shape_inference.infer_shapes(model)
# map output->node index
out_to_idx = {}
for i,n in enumerate(model.graph.node):
    for o in n.output:
        out_to_idx[o]=i
# find Squeeze nodes with scalar outputs
to_remove_idx = []
replacements = []  # (old_out, new_in)
for i,n in enumerate(model.graph.node):
    if n.op_type=='Squeeze':
        out = n.output[0]
        # get inferred shape
        shape = None
        for vi in list(inf.graph.value_info)+list(inf.graph.output)+list(inf.graph.input):
            if vi.name==out:
                try:
                    shape = [d.dim_value if (d.dim_value>0) else None for d in vi.type.tensor_type.shape.dim]
                except Exception:
                    shape=None
                break
        if shape==[] or shape is None:
            # reroute consumers to use the squeeze's input instead
            new_in = n.input[0]
            replacements.append((out, new_in))
            to_remove_idx.append(i)
            print('Will reroute', out, '->', new_in)
# Apply replacements across nodes
for old_out, new_in in replacements:
    for node in model.graph.node:
        for j, inp in enumerate(node.input):
            if inp==old_out:
                node.input[j]=new_in
# Remove the squeeze nodes (do it by rebuilding node list)
new_nodes = []
for idx,n in enumerate(model.graph.node):
    if idx in to_remove_idx:
        print('Removing node', n.name)
        continue
    new_nodes.append(n)
model.graph.ClearField('node')
model.graph.node.extend(new_nodes)
# Save
outp = p.parent / 'model_opset14_fixed2.onnx'
onnx.save(model, str(outp))
print('Saved', outp)

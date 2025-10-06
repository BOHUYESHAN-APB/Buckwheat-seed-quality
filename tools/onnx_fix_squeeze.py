import onnx
from onnx import helper, TensorProto
from pathlib import Path
p = Path('e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/model_opset14.onnx')
model = onnx.load(str(p))
print('Loaded model, nodes:', len(model.graph.node))
# find Squeeze nodes whose output has no dims per shape inference
from onnx import shape_inference
inf = shape_inference.infer_shapes(model)
val_shapes = {vi.name: [d.dim_value if (d.dim_value>0) else None for d in vi.type.tensor_type.shape.dim]
              for vi in list(inf.graph.value_info)+list(inf.graph.input)+list(inf.graph.output)}
# Map output name -> node index
out_to_node = {}
for i,n in enumerate(model.graph.node):
    for o in n.output:
        out_to_node[o]=i

added = 0
new_nodes = []
for i,n in enumerate(model.graph.node):
    if n.op_type=='Squeeze':
        out = n.output[0]
        shape = val_shapes.get(out)
        if shape==[] or shape is None:
            # create an Unsqueeze node that unsqueezes axis 0
            new_name = out + '_unsq'
            unsq_node = helper.make_node('Unsqueeze', inputs=[out], outputs=[new_name], axes=[0], name= out + '_unsq_node')
            print('Inserting Unsqueeze after', n.name, 'for output', out)
            new_nodes.append((i, unsq_node))
            added += 1
# Insert new nodes immediately after the corresponding squeeze nodes
# Adjust downstream nodes: replace occurrences of original out by new_name
for idx, unsq in reversed(new_nodes):
    model.graph.node.insert(idx+1, unsq)
    old_out = unsq.input[0]
    new_out = unsq.output[0]
    for node in model.graph.node:
        for j, inp in enumerate(node.input):
            if inp==old_out:
                node.input[j]=new_out
print('Inserted', added, 'unsqueeze nodes. Saving fixed model...')
outp = p.parent / 'model_opset14_fixed.onnx'
onnx.save(model, str(outp))
print('Saved', outp)

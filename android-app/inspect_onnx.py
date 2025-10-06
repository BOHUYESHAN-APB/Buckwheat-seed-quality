import sys
try:
    import onnx
except Exception as e:
    print('NO_ONNX', e)
    sys.exit(2)

m=onnx.load('buckwheat_model.onnx')
print('graph inputs:', [i.name for i in m.graph.input])
print('graph outputs:', [o.name for o in m.graph.output])
print('graph initializers count:', len(m.graph.initializer))
print('initializers sample names:', [init.name for init in m.graph.initializer][:100])
# find nodes with op_type Split and print their inputs
for n in m.graph.node:
    if n.op_type == 'Split':
        print('Split node:', n.name, 'inputs=', list(n.input), 'attrs=', [(a.name, list(a.ints) if a.ints else None) if hasattr(a,'ints') else (a.name, None) for a in n.attribute])

# look for any name containing 'scale'
scale_names = [init.name for init in m.graph.initializer if 'scale' in init.name.lower()]
print('initializers with scale in name:', scale_names)

# print node names referencing 'scale' text
nodes_with_scale = [n for n in m.graph.node if any('scale' in s.lower() for s in n.input)]
print('nodes referencing scale in inputs:', [(n.name, list(n.input)) for n in nodes_with_scale])

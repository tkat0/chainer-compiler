import chainer

import onnx
import onnx.helper as oh
from onnx import TensorProto
from onnx import ModelProto

import elichika.parser.core as core
import elichika.parser.graphs as graph
import elichika.parser.values as values
import elichika.parser.nodes as nodes
import elichika.parser.functions_builtin as functions_builtin
import elichika.parser.values_builtin as values_builtin

import numpy as np
import collections

def size2d(x):
    if isinstance(x, collections.Iterable):
        return x
    return (x, x)

assigned_names = []

def generate_onnx_value_name(value : 'values.Value', none_name = ''):
    base_name = ''

    if value.generator != None:
        base_name = value.name + '_' + str(value.generator.lineprop)
    base_name = value.name

    if base_name == '':
        base_name = none_name

    ind = 0
    name = base_name
    while (name in assigned_names):
        ind+=1
        name = base_name + '_' + str(ind)

    assigned_names.append(name)
    return name

def generate_onnx_node_name(node : 'nodes.Node'):
    base_name = str(node)

    ind = 0
    name = base_name
    while (name in assigned_names):
        ind+=1
        name = base_name + '_' + str(ind)

    assigned_names.append(name)
    return name

def assign_onnx_name_to_value(value : 'values.Value', none_name = ''):
    if value.onnx_name == '':
        value.onnx_name = generate_onnx_value_name(value, none_name)

    if isinstance(value, values.TupleValue):
        tupleValue = value # type : values.TupleValue
        for value_ in tupleValue.values:
            assign_onnx_name_to_value(value_.get_value(), tupleValue.onnx_name)


def assign_onnx_name(graph : 'graphs.Graph'):
    for node in graph.nodes:
        for input in node.inputs:
            assign_onnx_name_to_value(input)
            
        for output in node.outputs:
            assign_onnx_name_to_value(output)

        node.onnx_name = generate_onnx_node_name(node)

        for subgraph in node.subgraphs:
            assign_onnx_name(subgraph)

def convert_onnx_chainer_linear(onnx_graph : 'ONNXGraph', node : 'nodes.Node'):
    chainer_inst = node.func.owner.inst # type: chainer.links.Linear
    onnx_name = node.onnx_name

    x = onnx_graph.tensors[node.inputs[0].onnx_name]
    o = onnx_graph.tensors[node.outputs[0].onnx_name]
    w = onnx_graph.new_tensor_with_np(chainer_inst.W.data, onnx_name + '/W')

    x_shape = onnx_graph.new_empty_tensor(['TODO'], np.float32, onnx_name + '/x_shape')
    batch_size_1 = onnx_graph.new_empty_tensor(['TODO'], np.float32, onnx_name + '/batch_size_1')
    batch_size_2 = onnx_graph.new_empty_tensor(['TODO'], np.float32, onnx_name + '/batch_size_2')
    mat_shape = onnx_graph.new_empty_tensor(['TODO'], np.float32, onnx_name + '/mat_shape')
    x_reshape = onnx_graph.new_empty_tensor(['TODO'], np.float32, onnx_name + '/x_reshape')
    
    onnx_graph.add_node(
        'Shape', 
        [x.name], 
        [x_shape.name],
        str(node.lineprop))

    onnx_graph.add_node(
        'Gather', 
        [x_shape.name, onnx_graph.new_tensor_with_np(np.array(0, dtype=np.int64), onnx_name + '/Zero').name], 
        [batch_size_1.name],
        str(node.lineprop))

    onnx_graph.add_node(
        'Unsqueeze', 
        [batch_size_1.name], 
        [batch_size_2.name],
        str(node.lineprop),
        axes=[0])

    onnx_graph.add_node(
        'Concat',
        [batch_size_2.name, onnx_graph.new_tensor_with_np(np.array([-1], dtype=np.int64), onnx_name + '/Minus1').name], 
        [mat_shape.name],
        str(node.lineprop),
        axis=0)

    onnx_graph.add_node(
        'Reshape', 
        [x.name, mat_shape.name], 
        [x_reshape.name],
        str(node.lineprop))

    x = x_reshape

    if chainer_inst.b is not None:
        b = onnx_graph.new_tensor_with_np(chainer_inst.b.data, onnx_name + '/B')
    
        onnx_graph.add_node(
            'Gemm', 
            [x.name, w.name, b.name], 
            [o.name],
            str(node.lineprop),
            transA=0,
            transB=1)
    else:
        temp = onnx_graph.new_empty_tensor(['TODO'], np.float32, onnx_name + '/Temp')
        onnx_graph.add_node(
            'Transpose', 
            [w.name], 
            [temp.name],
            str(node.lineprop),
            perm=[1, 0])

        onnx_graph.add_node(
            'MatMul', 
            [x.name, temp.name], 
            [o.name],
            str(node.lineprop))

def convert_onnx_chainer_convolution2d(onnx_graph : 'ONNXGraph', node : 'nodes.Node'):
    chainer_inst = node.func.owner.inst # type: chainer.links.Convolution2D
    onnx_name = node.onnx_name

    ksize = size2d(chainer_inst.ksize)
    stride = size2d(chainer_inst.stride)
    ps = size2d(chainer_inst.pad)
    pads = ps + ps

    x = onnx_graph.tensors[node.inputs[0].onnx_name]
    o = onnx_graph.tensors[node.outputs[0].onnx_name]
    w = onnx_graph.new_tensor_with_np(chainer_inst.W.data, onnx_name + '/W')
    b = None

    if chainer_inst.b is not None:
        b = onnx_graph.new_tensor_with_np(chainer_inst.b.data, onnx_name + '/b')

    onnx_graph.add_node(
        'Conv', 
        [x.name, w.name] + ([] if b is None else [b.name]), 
        [o.name],
        str(node.lineprop),
        kernel_shape=ksize,
        pads=pads,
        strides=stride)


class ONNXInitrializer:
    def __init__(self):
        self.node = None
        self.name = NameError
        self.dt = 0
        self.shape = ()

class ONNXGraph:
    def __init__(self):
        self.nodes = []
        self.input_tensor = []
        self.output_tensor = []
        self.tensors = {}
        self.initializers = {}

    def new_empty_tensor(self, dims, dtype, name):
        dt = onnx.mapping.NP_TYPE_TO_TENSOR_TYPE[np.dtype(dtype)]
        tensor = oh.make_tensor_value_info(name, dt, dims)
        self.tensors[name] = tensor
        return tensor

    def new_empty_tensor_with_value(self, value):
        if isinstance(value, values.TensorValue) and len(value.shape) > 0:
            shape = list(value.shape)
            shape = [x if x != -1 else 'Undefined' for x in shape]
            return self.new_empty_tensor(shape, np.float32, value.onnx_name)

        return self.new_empty_tensor(['Undefined'], np.float32, value.onnx_name)

    def new_tensor_with_np(self, ndarray_, name):
        dt = onnx.mapping.NP_TYPE_TO_TENSOR_TYPE[np.dtype(ndarray_.dtype)]
        tensor = oh.make_tensor(name, dt, ndarray_.shape, ndarray_.flat)
        initializer = ONNXInitrializer()
        initializer.name = name
        initializer.node = tensor
        initializer.dt = dt
        initializer.shape = ndarray_.shape

        self.initializers[name] = initializer
        return tensor

    def add_node(self, optype, inputs, outputs, name, **kwargs):
        # check types
        assert(len([i for i in inputs if not isinstance(i, str)]) == 0)
        assert(len([i for i in outputs if not isinstance(i, str)]) == 0)

        node = oh.make_node(optype, inputs, outputs, name, **kwargs)
        self.nodes.append(node)

    def set_input(self, input):
        self.input_tensor = [self.tensors[x.onnx_name] for x in input]

    def set_output(self, output):
        self.output_tensor = [self.tensors[x.onnx_name] for x in output]

    def generate_graph(self, name : 'str'):

        input_tensor_and_initializer = self.input_tensor.copy()
        initializers = []

        # add constants
        for v in self.initializers.values():
            if v.node in self.input_tensor:
                continue
            if v.node in self.output_tensor:
                continue
            
            initializers.append(v.node)

            tensor = oh.make_tensor_value_info(v.name, v.dt, v.shape)
            input_tensor_and_initializer.append(tensor)

        return oh.make_graph(self.nodes, name, input_tensor_and_initializer, self.output_tensor, initializer=initializers)

class ONNXGenerator:
    def __init__(self):
        self.onnx_graphs = []
        self.onnx_tensors = {}

    def generate_graph(self, inputs, outputs, graph : 'graphs.Graph'):
        onnx_graph = ONNXGraph()
        
        for node in graph.nodes:
            
            for input in node.inputs:
                if not (input.onnx_name in self.onnx_tensors.keys()):
                    tensor = onnx_graph.new_empty_tensor_with_value(input)
                    self.onnx_tensors[input.onnx_name] = tensor

            for output in node.outputs:
                if not (output.onnx_name in self.onnx_tensors.keys()):
                    tensor = onnx_graph.new_empty_tensor_with_value(output)
                    self.onnx_tensors[output.onnx_name] = tensor

            if isinstance(node, nodes.NodeCall):

                if isinstance(node.func, functions_builtin.ReluFunction):
                    # relu
                    onnx_node = oh.make_node("Relu", [node.inputs[0].onnx_name], [node.outputs[0].onnx_name])
                    onnx_graph.nodes.append(onnx_node)

                if isinstance(node.func, functions_builtin.SoftmaxFunction):
                    # softmax
                    onnx_node = oh.make_node(
                        "Softmax", 
                        [node.inputs[0].onnx_name], 
                        [node.outputs[0].onnx_name],
                        str(node.lineprop),
                        axis = node.inputs[1].number)

                    onnx_graph.nodes.append(onnx_node)

                if isinstance(node.func, values_builtin.ChainerLinkFunction):
                    original_inst = node.func.owner.inst

                    if isinstance(original_inst, chainer.links.Linear):
                        convert_onnx_chainer_linear(onnx_graph, node)

                    if isinstance(original_inst, chainer.links.Convolution2D):
                        convert_onnx_chainer_convolution2d(onnx_graph, node)

        onnx_graph.set_input(inputs)
        onnx_graph.set_output(outputs)

        return onnx_graph.generate_graph('main')

    def generate_model(self, inputs, outputs, graph)-> 'ModelProto':
        # assign names
        assigned_names.clear()
        assign_onnx_name(graph)

        graph_ = self.generate_graph(inputs, outputs, graph)
        model = oh.make_model(graph_, producer_name="elichika", producer_version="0.1")
        return model

class ONNXModel:
    def __init__(self):
        self.model = None
        self.inputs = []
        self.outputs = []

def compile_model(model, inputs) -> 'ONNXModel':
    inputs_, outputs_, graph_ = core.convert_model(model, inputs)

    generator = ONNXGenerator()
    model = generator.generate_model(inputs_, outputs_, graph_)

    onnx_model = ONNXModel()
    onnx_model.model = model
    onnx_model.inputs = inputs_
    onnx_model.outputs = outputs_
    return onnx_model

def save_model(path : 'str', model : 'ModelProto'):
    with open(path, "wb") as f:
        f.write(model.SerializeToString())

def save_model_as_text(path : 'str', model : 'ModelProto'):
    with open(path, "w") as f:
        print(model, file=f)
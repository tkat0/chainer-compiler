#pragma once

#include <onnx/onnx_pb.h>

namespace oniku {

void MakeHumanReadableValue(onnx::TensorProto* tensor);

void StripLargeValue(onnx::TensorProto* tensor, int num_elements);

void StripONNXGraph(onnx::GraphProto* graph);

void StripONNXModel(onnx::ModelProto* model);

}  // namespace oniku
